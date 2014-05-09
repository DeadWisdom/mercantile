from fabric.api import env, run, sudo, cd, hide, prefix, prompt, settings, show, local, lcd
from fabric.tasks import execute
from fabric.contrib.files import append, sed, exists
from fabric.decorators import task

from mercantile.config import config, default_file, default
from server import put_template

## Templates ##
config.add('servers', {
    'server_nginx.conf': unicode | default_file("server_nginx.conf"),
    'nginx.init': unicode | default_file("nginx.init"),
    'nginx_version': unicode | default("nginx-1.5.12.tar.gz"),
    'www_owner': unicode | default("www"),
})

config.add('projects', {
    'nginx.conf': unicode | default_file("nginx.conf"),
    'supervisor.conf': unicode | default_file("supervisor.conf"),
    'uwsgi.conf': unicode | default_file("uwsgi.conf"),
    'wsgi.py': unicode | default_file("wsgi.py"),
    'manage.py': unicode | default_file("manage.py"),
    'is_django': bool | default(False),
})


### Helpers ###
def cd_src():
    return cd("/www/%s/src" % env.project.key)


### Tasks ###
@task
def build():
    "Builds the www infrastructure."
    owner = env.server.www_owner
    env.user = 'root'

    sudo("apt-get install libpcre3 libpcre3-dev")
    sudo("apt-get update")
    sudo("apt-get install rubygems")

    if env.project.gems:
        sudo("apt-get install ruby")
        sudo("gem install %s" % " ".join(env.project.gems))

    with settings(warn_only=True):
        sudo("rm -rf /root/_build")          # Delete previous build files.
        sudo("mkdir /root/_build")           # Create new build file directory.
    
    print "Building uwsgi..."
    sudo("apt-get -qy install build-essential psmisc libxml2 libxml2-dev")
    with cd("/root/_build"):
        sudo("wget http://projects.unbit.it/downloads/uwsgi-latest.tar.gz")
        sudo("tar -xzf uwsgi-latest.tar.gz")
        with cd("uwsgi*"):
            sudo("make")
            with settings(warn_only=True):
                sudo("rm /usr/local/sbin/uwsgi")
            sudo("cp uwsgi /usr/local/sbin")
            uwsgi_dir = sudo("pwd")
    
    print "Building nginx..."
    sudo("apt-get -qy install libssl-dev")
    with cd("/root/_build"):
        sudo("wget http://nginx.org/download/%s" % env.server.nginx_version)
        sudo("tar -xzf %s" % env.server.nginx_version)
        with cd("nginx*"):
            sudo("./configure")
            sudo("make")
            sudo("make install")

    put_template( env.server['server_nginx.conf'], "/usr/local/nginx/conf/nginx.conf", env.server, use_sudo=True)
    
    append("/etc/sudoers", "%s ALL=NOPASSWD: /etc/init.d/nginx restart" % owner, use_sudo=True)
    append("/etc/sudoers", "%s ALL=NOPASSWD: /etc/init.d/nginx reload" % owner, use_sudo=True)
    
    with settings(warn_only=True):
        sudo("rm -rf /root/_build")          # Cleanup
    
    print "Creating /www..."
    with settings(warn_only=True):
        sudo("mkdir /www")
        sudo("chown -R %s:%s /www" % (owner, owner))
    
    print "Adding www to supervisor..."
    sed("/etc/supervisor/supervisord.conf", r"files = .*", r"files = /www/*/supervisor.conf /www/supervisor.conf", use_sudo=True)
    
    print "Restarting www service..."
    if exists("/etc/init.d/nginx"):
        with settings(warn_only=True):
            sudo("/etc/init.d/nginx stop")
        sudo("/etc/init.d/nginx start")
    else:
        put_template( env.server['nginx.init'], "/etc/init.d/nginx", env.server, use_sudo=True)
        run("chmod 755 /etc/init.d/nginx")
        sudo("/etc/init.d/nginx start")


@task
def deploy(name=None):
    """
    Deploy the given ``project``, or if not specified, the current project.
    """
    import server

    if name:
        activate_project(name)
    else:
        name = env.project.key
    config = env.project

    print "Installing project %r..." % name

    print "", "Cloning repo..."
    with settings(warn_only=True):
        run("mkdir /www/%s" % name)
        run("mkdir /www/%s/src" % name)
        run("git clone %s /www/%s/src" % (config.git, name))
    
    if config.mysql_name:                               # Todo: move to mysql.py
        print "", "Creating MySQL database..."
        with settings(warn_only=True):
            run("mysql --user=root --password=%s --execute=\"CREATE DATABASE %s\"" % (env.server.mysql_root_password, config.mysql_name))
            run("mysql --user=root --password=%s --execute=\"GRANT ALL ON %s.* TO '%s'@'localhost' IDENTIFIED BY '%s'\"" %
                 (env.server.mysql_root_password, config.mysql_name, config.mysql_user, config.mysql_password))
    
    with cd("/www/%s" % name):
        print "", "Updating repo..."
        with cd("src"):
            run("git pull")
        
        with settings(warn_only=True):
            run("mkdir logs")
            run("mkdir sql")

        print "", "Installing virtualenv"
        with settings(warn_only=True):
            run("virtualenv env")
    
        print "", "Installing pip requirements..."
        with settings(warn_only=True):
            run("virtualenv env")
            run("env/bin/pip install -r src/requirements.txt")
            run("env/bin/pip install mysql-python")
            #run("env/bin/pip install cython -e git+https://github.com/surfly/gevent.git#egg=gevent")

    print "Generating config files..."
    for c in ["nginx.conf", "uwsgi.conf", "supervisor.conf"]:
        server.put_template( config[c], "/www/%s/%s" % (name, c), config)

    if config['is_django']:
        print "Generating custom manage.py file..."
        server.put_template( config["manage.py"], "/www/%s/src/manage.py" % name, config)
        run("chmod 755 /www/%s/src/manage.py" % name)

        print "Generating custom wsgi.py file..."
        server.put_template( config["wsgi.py"], "/www/%s/src/wsgi.py" % name, config)

    print "Supervisorctl rereading config..."
    run("sudo supervisorctl reread")

    up()

    print "Restarting nginx..."
    run("sudo /etc/init.d/nginx restart")


@task
def checkout(revision):
    "Checkout a revision."
    print "Checking out:", revision + "..."

    with cd_src():
        print "", "Updating repo..."
        run("git fetch")
        run("git fetch --tags")
        run("git checkout %s" % revision)
        run("git pull")


@task
def pull():
    "Pulls changes to the repository, doesn't restart or anything else."

    with cd_src():
        run("git pull")


@task
def up(branch=None):
    "Updates the project."
    print "Updating project:"

    if (branch):
        checkout(branch)

    with cd_src():
        print "", "Updating repo..."
        run("git pull")

        with prefix("source /www/%s/env/bin/activate" % env.project.key):
            print "", "Installing pip requirements..."
            with settings(warn_only=True):
                run("pip install -r requirements.txt")

            if env.project['is_django']:
                run("python manage.py syncdb --noinput")
                run("python manage.py collectstatic --noinput")

    print "", "Restarting supervisor job..."
    run("sudo supervisorctl restart %s:uwsgi" % env.project.key)

@task
def syncdb():
    "Syncs the db."
    with cd_src():
        print "Syncing database..."
        with prefix("source /www/%s/env/bin/activate" % env.project.key):
            run("python manage.py syncdb")

@task
def resetdb(force=False):
    "Clears the database, recreates it."
    config = env.project

    if not force and not config.data_transient:
        raise RuntimeError("Forbidden except for projects with `data_transient = True`.")

    if config.mysql_name:
        with settings(warn_only=True):
            print "", "Dropping MySQL database..."
            run("mysql --user=root --password=%s --execute=\"DROP DATABASE %s\"" % (env.server.mysql_root_password, config.mysql_name))

            print "", "Creating MySQL database..."
            run("mysql --user=root --password=%s --execute=\"CREATE DATABASE %s\"" % (env.server.mysql_root_password, config.mysql_name))
            run("mysql --user=root --password=%s --execute=\"GRANT ALL ON %s.* TO '%s'@'localhost' IDENTIFIED BY '%s'\"" %
                 (env.server.mysql_root_password, config.mysql_name, config.mysql_user, config.mysql_password))

@task
def force():
    """Forces the project to have data_transient."""
    env.project.data_transient = True

@task 
def seed(data_branch='master', force=False):
    print "seeding..."
    "Clears the database, recreates it with the data branch."
    resetdb(force=force)
    
    dir = "/www/%s/data" % env.project.key

    #with settings(warn_only=True):
    #    run("git clone git@github.com:Dan-org/dole-data.git %s" % dir)

    #with cd(dir):
    #    print "Pulling data changes from %s..." % data_branch
    #    run('git remote update')
    #    run('git checkout %s' % data_branch)
    #    run("git pull origin %s" % data_branch)
    
    with cd_src():
        with prefix("source /www/%s/env/bin/activate" % env.project.key):
            print "Syncing database..."
            run("python manage.py syncdb --noinput")

            print "Loading fixtures..."
            #this fucking used to work, django.
            run("python manage.py loaddata %s/fixtures.json" % dir)

    with cd_src():
        print "Syncing media..."
        try:
            with hide('everything'):
                run("rsync -vaz %s/media/ /www/%s/src/media/" % (dir, env.project.key))
        except:
            print "Media corrupt; Rebuilding media..."
            run("rm -rf /www/%s/src/media/" % env.project.key)
            run("rsync -vaz %s/media/ /www/%s/src/media/" % (dir, env.project.key))


@task
def restartnginx():
    "Restarts nginx."

    print "Restarting nginx..."
    run("sudo /etc/init.d/nginx restart")


@task
def restart():
    """Restarts uwsgi and nginx"""

    print "", "Restarting supervisor..."
    run("sudo supervisorctl restart all")
    
    print "Restarting nginx..."
    run("sudo /etc/init.d/nginx restart")



@task
def pip_install():
    with cd("/www/%s" % env.project.key):
        run("env/bin/pip install -r src/requirements.txt")

