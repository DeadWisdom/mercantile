import posixpath

from fabric.api import env, run, sudo, cd, hide, prefix, prompt, settings, show, local, lcd
from fabric.tasks import execute
from fabric.contrib.files import append, sed, exists
from fabric.decorators import task

from mercantile.config import config, default_file, default
from server import put_template
from project import root, cd_src, prefix_env

## Templates ##
config.add('servers', {
    'server_nginx.conf': unicode | default_file("server_nginx.conf"),
    'nginx.init': unicode | default_file("nginx.init"),
    'nginx_src': unicode | default("http://nginx.org/download/nginx-1.7.4.tar.gz"),
    'uwsgi_src': unicode | default("http://projects.unbit.it/downloads/uwsgi-latest.tar.gz"),
    'www_owner': unicode | default("www"),
})

config.add('projects', {
    'nginx.conf': unicode | default_file("nginx.conf"),
    'supervisor.conf': unicode | default_file("supervisor.conf"),
    'uwsgi.conf': unicode | default_file("uwsgi.conf"),
    'is_django': bool | default(False),
    'static': unicode | default('/static'),
    'extra_requirements': unicode,
})


### Tasks ###
@task
def build():
    "Builds the www infrastructure."
    owner = env.server.www_owner

    install_uwsgi()
    install_nginx()
    configure_services()


@task
def install_uwsgi():
    "Builds and installs uwsgi."
    env.user = env.server.root_login

    print "Building uwsgi..."
    with settings(warn_only=True):
        run("rm -rf ~/_build")          # Delete previous build files.
        run("mkdir ~/_build")           # Create new build file directory.

    with cd("~/_build"):
        run("wget %s" % env.server.uwsgi_src)
        run("tar -xzf %s" % env.server.uwsgi_src.rsplit('/', 1)[-1])
        with cd("uwsgi*"):
            run("make")
            with settings(warn_only=True):
                sudo("rm /usr/local/sbin/uwsgi")
            sudo("cp uwsgi /usr/local/sbin")
            uwsgi_dir = run("pwd")
    
    with settings(warn_only=True):
        sudo("rm -rf ~/_build")          # Cleanup

@task
def install_nginx():
    "Builds and installs nginx."
    env.user = env.server.root_login
    
    print "Building nginx..."
    with settings(warn_only=True):
        run("rm -rf ~/_build")          # Delete previous build files.
        run("mkdir ~/_build")           # Create new build file directory.

    with cd("~/_build"):
        run("wget %s" % env.server.nginx_src)
        run("tar -xzf %s" % env.server.nginx_src.rsplit('/', 1)[-1])
        with cd("nginx*"):
            run("./configure")
            run("make")
            sudo("make install")
            sudo("cp /usr/local/nginx/sbin/nginx /usr/sbin/nginx")

    with settings(warn_only=True):
        run("rm -rf ~/_build")          # Cleanup

    print "Setting up nginx init..."
    if not exists("/etc/init.d/nginx"):
        put_template( env.server['nginx.init'], "/etc/init.d/nginx", env.server, use_sudo=True)
        sudo("chmod 755 /etc/init.d/nginx")
        sudo("chown root:root /etc/init.d/nginx")
        sudo("update-rc.d nginx defaults")

    print "Setting up nginx conf..."
    put_template( env.server['server_nginx.conf'], "/usr/local/nginx/conf/nginx.conf", env.server, use_sudo=True)


@task
def configure_services():
    "Configures services to support projects."
    env.user = env.server.root_login
    owner = env.server.www_owner

    if not exists(env.server.service_root):
        print "Creating %s..." % env.server.service_root
        sudo("mkdir %s" % env.server.service_root)
        sudo("chown -R %s:%s %s" % (owner, owner, env.server.service_root))
    
    print "Adding %s to supervisor..." % env.server.service_root
    sed("/etc/supervisor/supervisord.conf", r"files = .*", r"files = %s/*/supervisor.conf %s/supervisor.conf" % \
            (env.server.service_root, env.server.service_root), use_sudo=True)

    print "Adding %r to sudoers..." % owner
    append("/etc/sudoers", "%s ALL=NOPASSWD: /usr/sbin/service nginx restart" % owner, use_sudo=True)
    append("/etc/sudoers", "%s ALL=NOPASSWD: /usr/sbin/service supervisor restart" % owner, use_sudo=True)
    

@task
def pull(branch=None):
    "Pulls the source."
    if not exists(root()):
        run("mkdir %s" % root())
        run("mkdir %s" % root('logs'))

    if not exists(root('src')):
        run("git clone %s %s" % (env.project.git, root('src')))
    
    if branch:
        checkout(branch)

    with cd_src():
        run("git pull")


@task
def install_requirements():
    "Installs the pip requirements."
    print "", "Installing pip requirements..."
    with cd_src():
        if not exists('env'):
            run("virtualenv env")

        run("env/bin/pip install -r requirements.txt")
        run("env/bin/pip install gevent")
        if env.project.extra_requirements:
            run("env/bin/pip install %s" % env.project.extra_requirements)


@task
def build_config():
    "Builds the config files for nginx, supervisor, and nginx."
    print "Building config files..."
    for c in ["nginx.conf", "uwsgi.conf", "supervisor.conf"]:
        put_template( env.project[c], root(c), env.project)


@task
def restart_supervisor():
    "Restarts supervisor."
    print "Restarting supervisor..."
    with settings(warn_only=True):
        result = run("sudo service supervisor restart")
    
    if result.failed:
        run("sudo service supervisor restart")


@task
def restart_nginx():
    "Restarts nginx."
    print "Restarting nginx..."
    with settings(warn_only=True):
        result = run("sudo service nginx restart")
    
    if result.failed:
        run("sudo service nginx restart")


@task
def restart():
    "Restarts nginx and supervisor."
    restart_supervisor()
    restart_nginx()


@task
def checkout(revision):
    "Checkout a revision."
    print "Checking out:", revision + "..."
    with cd_src():
        print "", "Updating repo..."
        run("git fetch")
        run("git fetch --tags")
        run("git checkout %s" % revision)


@task
def up(branch=None):
    "Updates the project."

    pull()
    install_requirements()
    restart()
