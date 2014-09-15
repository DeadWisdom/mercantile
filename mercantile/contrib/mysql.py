from datetime import datetime
from fabric.api import env, run, sudo, cd, hide, prefix, prompt, settings
from fabric.contrib.files import append, sed
from fabric.decorators import task

from mercantile.config import config, default_file, default
from project import root, cd_src, prefix_env

config.add('projects', {
    'mysql_root_user': unicode | default("root"),       # Root user to create the database (optional)
    'mysql_root_password': unicode | default(None),     # Root password to create the database (optional)
    'mysql_host': unicode | default(None),              # Host, defaults to local
    'mysql_port': unicode | default(3306),              # Port, defaults to 
    'mysql_transient': unicode | default(False),        # Can this be reset without pause? i.e. the data here is not important.
    'mysql_user': unicode | default(None),              # Project/application specific user, not root
    'mysql_password': unicode | default(None),          # Project/application specific password, not the root password
    'mysql_name': unicode | default(None),              # Project/application specific database name
})

def args():
    args = [
        '--user=%s' % env.project.mysql_root_user,
        '--password=%s' % env.project.mysql_root_password,
    ]
    if env.project.mysql_host:
        args.extend([
            '--host=%s' % env.project.mysql_host,
            '--port=%s' % env.project.mysql_port,
        ])
    return " ".join(args)

@task
def build():
    env.user = env.server.root_login
    root_password = env.server.mysql_root_password

    print "Installing mysql..."
    sudo("apt-get -qu install debconf-utils")  # Ensures debconf-set-selections exists.

    sudo("echo 'mysql-server mysql-server/root_password select %s' | debconf-set-selections" % root_password)
    sudo("echo 'mysql-server mysql-server/root_password_again select %s' | debconf-set-selections" % root_password)
    sudo("apt-get -qy install mysql-server mysql-client libmysqlclient15-dev")

@task
def deploy():
    config = env.project
    if config.mysql_name:
        print "", "Creating MySQL database..."
        with settings(warn_only=True):
            run("mysql %s --execute=\"CREATE DATABASE %s\"" % (args(), config.mysql_name))
            run("mysql %s --execute=\"GRANT ALL ON %s.* TO '%s'@'%%' IDENTIFIED BY '%s'\"" %
                 (args(), config.mysql_name, config.mysql_user, config.mysql_password))

@task
def backup():
    now = datetime.now().strftime("%Y-%m-%d-%H%I")

    with settings(warn_only=True):
        run("mkdir %s" % root('db'))

    print "Backing up data to %s..." % root('db')
    run(
        "mysqldump %s %s | gzip > %s/%s.sql.gz" % (
            args(),
            env.project.mysql_name,
            root('db'),
            now,
        )
    )

    return "%s%s.sql.gz" % (root('db'), now)


@task
def reset():
    config = env.project
    if config.mysql_name:                               # Todo: move to mysql.py
        print "", "Destroying MySQL database..."
        with settings(warn_only=True):
            run("mysql %s --execute=\"DROP DATABASE %s\"" % (args(), config.mysql_name))
    
    deploy()

