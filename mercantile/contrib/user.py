from fabric.decorators import task
from fabric.tasks import execute
from fabric.api import env, cd, settings, sudo, run, put, hide, show
from fabric.contrib.files import append
from cStringIO import StringIO


### Helpers ###
def activate_user(username):
    env.user = username


### Tasks ###
@task
def build(username=None):
    if username is None:
        for username in env.server.users:
            build(username)
        return

    user = env.config.users[username]
    print "Adding user %r..." % (username)

    env.user = "root"

    with settings(warn_only=True):
        sudo("useradd -m -U %s -c \"%s\"" % (username, user.name))

    with cd("/home/%s/" % username):
        # Change the Shell to Bash
        sudo("chsh -s /bin/bash %s" % username)
    
        # Directories
        with settings(warn_only=True):
            sudo("rm -rf .ssh")
            sudo("mkdir .ssh")
        
        # Git
        if user.name:
            sudo("git config --global user.name \"%s\"" % user.name, user=username)
        if user.email:
            sudo("git config --global user.email \"%s\"" % user.email, user=username)

    # SSH
    if (user.private_key):
        put(StringIO(user.private_key.encode('ascii') + "\n"), "/home/%s/.ssh/id_rsa" % username, use_sudo=True)
    
    if (user.public_key):
        put(StringIO(user.public_key.encode('ascii') + "\n"), "/home/%s/.ssh/authorized_keys" % username, use_sudo=True)
        put(StringIO(user.public_key.encode('ascii') + "\n"), "/home/%s/.ssh/id_rsa.pub" % username, use_sudo=True)

    if (user.authorized_keys):
        for key in user.authorized_keys:
            append( "/home/%s/.ssh/authorized_keys" % username, key + "\n", use_sudo=True)

    append("/home/%s/.ssh/config" % username, "Host github.com", use_sudo=True)
    append("/home/%s/.ssh/config" % username, "    StrictHostKeyChecking no", use_sudo=True)
    
    # Ownership / Permissions
    with cd("/home/%s/" % username):
        sudo("chown -R %s:%s ." % (username, username))
        sudo("chmod 700 .ssh")
        sudo("chmod 600 /home/%s/.ssh/*" % username)

    # Sudo
    if user.sudo:
        append("/etc/sudoers", "%s    ALL=(ALL) ALL" % username, use_sudo=True)
    
    if user.supervisor or user.sudo:
        append("/etc/sudoers", "%s    ALL=NOPASSWD:/usr/bin/supervisorctl" % username, use_sudo=True)


@task
def password(username=None):
    """Set the password on the given ``username`` or, if not provided, the current user."""
    env.user = 'root'
    with show("stdout"):
        sudo("passwd %s" % username or env.user)
