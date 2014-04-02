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
    'mysql_root_password': unicode,                     # Sets the root mysql password.
    'root_password': unicode,                           # Password for root, if available.
    'language': unicode | default("LANG=en_US.UTF-8"),  # English
    # Templates
    'motd.txt': unicode | default_file("motd.txt"),
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
        env.user = 'root'
        env.password = env.server.root_password

def build_if_needed():
    print "Looking for server..."

    if env.server.aws:
        import aws
        if aws.exists():
            return
    else:
        try:
            with hide('running', 'stdout', 'stderr', 'status', 'aborts'):
                run("ls")
            return
        except:
            pass

    save_user, env.user = env.user, 'root'
    build()
    env.user = save_user

def put_template(local, remote, context, **kwargs):
    from django.template import Context, Template
    from django.conf import settings
    if not settings.configured:
        settings.configure()
    template = Template(contents_of_path(local))
    context = Context(context)
    io = StringIO(template.render(context).encode("ascii"))
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
    elif env.project:
        env.user = 'root'
    elif not env.project:
        abort("Build what?")
    
    if conf.aws:
        import aws
        aws.build_if_needed()

    print "Building the server..."
    try:
        with hide('running', 'stdout', 'stderr', 'status', 'aborts'):
            sudo("ls")   # Check for sudo / access.
    except:
        run("apt-get -qy update")
        run("apt-get -qy install sudo")
    
    print "Resizing filesystem..."
    with hide('running', 'stdout', 'stderr', 'status', 'aborts'):
        with settings(warn_only=True):
            sudo('resize2fs /dev/xvda1')

    print "Updating system..."
    sudo("apt-get -qy update")
    sudo("apt-get -qy dist-upgrade")
    sudo("apt-get -qy upgrade")

    if env.host:
        print "Setting hostname..."
        sudo("hostname %s" % env.host)
    
    print "Installing essential packages..."
    sudo("apt-get -qy install sudo")
    sudo("apt-get -qy install git")
    sudo("apt-get -qy install libjpeg62-dev")
    sudo("apt-get -qy install python-dev python-setuptools")
    sudo("apt-get -qy install supervisor")
    sudo("apt-get -qy install mercurial")
    sudo("apt-get -qy install libcurl3-openssl-dev")
    sudo("apt-get -qy install libxml2-dev libxslt1-dev")
    sudo("apt-get -qy install screen")
    sudo("apt-get -qy install redis-server")
    sudo("apt-get -qy install libevent-dev")
    sudo("apt-get -qy install libxml2")
    sudo("apt-get -qy install libxslt1.1")
    sudo("easy_install virtualenv pip==1.0.2")
    
    print "Setting language..."
    append("/etc/environment", conf.language, use_sudo=True)

    print "Setting MOTD..."
    put_template( conf['motd.txt'], "/etc/motd", conf, use_sudo=True)

    for k in conf.users:
        user.build(k)


@task
def fix_dpkg():
    "If the dpkg was interupted, this will fix it."
    sudo("dpkg --configure -a")

