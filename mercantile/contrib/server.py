import os
from fabric.decorators import task
from fabric.tasks import execute
from fabric.api import env, cd, settings, sudo, run, put, hide, show
from fabric.contrib.files import append
from cStringIO import StringIO

from mercantile.config import config, required, string_list, contents_of_path, default_file, default


conf = config.add_group('servers', {
    'name': unicode | required,                         # Name of the server. (Required)
    'description': unicode,                             # Description of the server.
    'host': unicode,                                    # IP or host name for the server.
    'identity': unicode,                                # The path to a private key / identity file for root.
    'users': string_list,                               # A list of users to install
    'packages': string_list,                            # A list of packages to install
    'aws': unicode,                                     # The key of an aws config to use.
    'service_root': unicode | default('/srv'),          # Directory root to the services.
    'mysql_root_password': unicode,                     # Sets the root mysql password.
    'root_login': unicode | default('root'),            # Root login
    'root_password': unicode,                           # Password for root, if available.
    'language': unicode | default("LANG=en_US.UTF-8"),  # English
    'motd.txt': unicode | default_file("motd.txt"),     # MOTD Template
})


### Helpers ###
env.server = None
def activate(name):
    global conf
    env.server = conf = conf[name]
    if conf.identity:
        env.key_filename = env.server.identity
    if conf.host:
        env.hosts = [env.server.host]
    if conf.aws:
        import aws
        aws.activate(env.server.aws)
    if conf.root_password:
        env.user = conf.root_login
        env.password = env.server.root_password


def put_template(local, remote, context, **kwargs):
    from jinja2 import Template
    template = Template(contents_of_path(local))
    io = StringIO(template.render(**context).encode("ascii"))
    put( io, remote, **kwargs )


### Tasks ###
@task
def build(name=None):
    """
    Builds the server.
    """
    import user
    
    if name is not None:
        activate(name)

    if conf.aws:
        import aws
        aws.build_if_needed()

    env.user = env.server.root_login

    ensure_sudo()
    update()
    install_essential_packages()
    #install_packages()
    install_gems()
    set_hostname()
    set_language()
    set_motd()

    for k in conf.users:
        user.build(k)


@task
def fix_dpkg():
    "If the dpkg was interupted, this will fix it."
    print "Fixing package manager..."
    env.user = env.server.root_login

    sudo("dpkg --configure -a")


@task
def update():
    "Updates the system / upgrades the distribution if available."
    print "Updating system..."
    env.user = env.server.root_login

    sudo("apt-get -qy update")
    sudo("apt-get -qy --force-yes dist-upgrade")
    sudo("apt-get -qy --force-yes upgrade")


@task
def resize_fs(dev='/dev/xvda1'):
    "Resize the filesystem on the given device."
    print "Resizing filesystem..."
    env.user = env.server.root_login

    sudo('resize2fs %s' % dev)


@task
def ensure_sudo():
    "Installs sudo if it's not already installed."
    try:
        with hide('running', 'stdout', 'stderr', 'status', 'aborts'):
            sudo("ls")   # Check for sudo / access.
    except:
        prev_user, env.user = env.user, env.server.root_login
        prev_password, env.password = env.password, env.server.root_password
        run("apt-get -qy update")
        run("apt-get -qy install sudo")
        env.user = prev_user
        env.password = prev_password

@task
def install_essential_packages():
    "Installs essential packages."
    print "Installing essential packages..."
    env.user = env.server.root_login

    packages = [
        "sudo",
        "git",
        "libjpeg62-dev",
        "python-dev python-setuptools",
        "supervisor",
        "mercurial",
        "libcurl3-openssl-dev",
        "screen",
        "redis-server",
        "libevent-dev",
        "libpcre3 libpcre3-dev libssl-dev",
        "build-essential psmisc libxml2 libxml2-dev libxslt1.1 libxslt1-dev",
        "libmysqlclient-dev",
        "ruby",
    ]

    sudo("apt-get -qy --force-yes install %s" % " ".join(packages))
    sudo("easy_install virtualenv")


@task 
def install_packages(packages=None):
    "Installs the given packages."
    env.user = env.server.root_login

    packages = packages or env.server.packages
    if packages:
        sudo("apt-get -qy install %s" % packages)


@task
def set_hostname(host=None):
    "Sets the hostname to the given ``host`` or the config host."
    host = host or env.server.host
    env.user = env.server.root_login

    print "Setting hostname to %r..." % host
    sudo("hostname %s" % host)


@task
def set_language(lang=None):
    "Sets the language for the server to the given ``lang`` or the language in the config."
    lang = lang or env.server.language
    env.user = env.server.root_login

    print "Setting language to %r..." % lang
    append("/etc/environment", lang, use_sudo=True)


@task
def set_motd(motd=None):
    "Sets the Message of the Day for the server to the given ``motd`` or the 'motd.txt' in the config."
    print "Setting MOTD..."
    env.user = env.server.root_login

    motd = motd or env.server['motd.txt']
    put_template( motd, "/etc/motd", env.server, use_sudo=True)


@task
def install_gems(gems=None):
    "Install the given ruby gems."
    env.user = env.server.root_login

    if env.project.gems or gems:
        sudo("apt-get install ruby")
    
    if env.project.gems:
        sudo("gem install %s" % " ".join(env.project.gems))

    if gems:
        sudo("gem install %s" % " ".join(gems))
