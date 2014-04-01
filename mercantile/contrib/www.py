from fabric.api import env, run, sudo, cd, hide, prefix, prompt, settings, show, local, lcd
from fabric.tasks import execute
from fabric.contrib.files import append, sed
from fabric.decorators import task

from mercantile.config import config 


### Tasks ###
@task
def build():
    "Builds the www infrastructure."
    owner = env.server.www_owner or 'www'
    env.user = 'root'

    append("/etc/apt/sources.list", "deb http://nginx.org/packages/debian/ squeeze nginx", use_sudo=True)
    append("/etc/apt/sources.list", "deb-src http://nginx.org/packages/debian/ squeeze nginx", use_sudo=True)
    
    sudo("apt-get install libpcre3 libpcre3-dev")
    sudo("apt-get update")
    sudo("apt-get -qy --force-yes install nginx")

    with settings(warn_only=True):
        sudo("rm -rf /root/_build")          # Delete previous build files.
        sudo("mkdir /root/_build")           # Create new build file directory.
    
    print "Installing mysql..."
    sudo("apt-get -qy install mysql-server")
   
    print "Building uwsgi..."
    sudo("apt-get -qy install build-essential psmisc libxml2 libxml2-dev")
    with cd("/root/_build"):
        sudo("wget http://projects.unbit.it/downloads/uwsgi-latest.tar.gz")
        sudo("tar -xzf uwsgi-latest.tar.gz")
        with cd("uwsgi*"):
            sudo("make")
            sudo("cp uwsgi /usr/local/sbin")
            uwsgi_dir = sudo("pwd")
    
    print "Building nginx..."
    sudo("apt-get -qy install libssl-dev")

    with cd("/root/_build"):
        sudo("wget http://nginx.org/download/nginx-1.4.1.tar.gz")
        sudo("tar -xzf nginx-1.4.1.tar.gz")
        with cd("nginx*"):
            sudo("./configure")
            sudo("make")
            sudo("make install")
    
    server.put_template( "fabfile/files/uwsgi_params", "/etc/nginx/conf.d/uwsgi_params", {})
    
    with settings(warn_only=True):
        sudo("mkdir /usr/local/nginx/")
    
    #sed("/etc/nginx/nginx.conf", r"include /etc/nginx/sites-enabled/\*;", "include /www/*/nginx.conf;", use_sudo=True)
    sed("/etc/nginx/nginx.conf", r"include /etc/nginx/conf\.d/\*\.conf;", "include /www/*/nginx.conf;", use_sudo=True)
    sed("/etc/nginx/nginx.conf", r"user\s+nginx;", "user %s;" % owner, use_sudo=True)
    append("/etc/sudoers", "%s ALL=NOPASSWD: /etc/init.d/nginx restart" % owner, use_sudo=True)
    
    with settings(warn_only=True):
        sudo("rm -rf /root/_build")          # Cleanup

    print "Creating /www..."
    with settings(warn_only=True):
        sudo("mkdir /www")
        sudo("chown -R %s:%s /www" % (owner, owner))

    print "Adding www to supervisor..."
    sed("/etc/supervisor/supervisord.conf", r"files = .*", r"files = /www/*/supervisor.conf /www/supervisor.conf", use_sudo=True)
    
    print "Restarting www service..."
    sudo("/etc/init.d/nginx restart")


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
    
    #server.build_if_needed()

    print env.user

    print "Installing project %r..." % name

    print "", "Cloning repo..."
    with settings(warn_only=True):
        run("mkdir /www/%s" % name)
        run("mkdir /www/%s/src" % name)
        run("git clone %s /www/%s/src" % (config.git, name))
    
    if config.mysql_name:                               # Todo: move to mysql.py
        print "", "Creating MySQL database..."
        with settings(warn_only=True):
            run("mysql --user=root --password=%s --execute=\"CREATE DATABASE %s\"" % (config.mysql_password, config.mysql_name))
            run("mysql --user=root --password=%s --execute=\"GRANT ALL ON %s.* TO '%s'@'localhost' IDENTIFIED BY '%s'\"" %
                 (config.mysql_password, config.mysql_name, config.mysql_user, config.mysql_password))
    
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
    for conf in ["nginx.conf", "uwsgi.conf", "supervisor.conf"]:
        server.put_template( "fabfile/files/%s" % conf, "/www/%s/%s" % (name, conf), config)

    print "Generating custom manage.py file..."
    server.put_template( "fabfile/files/manage.py", "/www/%s/src/manage.py" % name, config)
    run("chmod 755 /www/%s/src/manage.py" % name)

    print "Generating custom wsgi.py file..."
    server.put_template( "fabfile/files/wsgi.py", "/www/%s/src/wsgi.py" % name, config)

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
def resetdb():
    "Clears the database, recreates it."
    config = env.project

    if not config.data_transient:
        raise RuntimeError("Forbidden except for projects with `data_transient = True`.")

    if config.mysql_name:
        with settings(warn_only=True):
            print "", "Dropping MySQL database..."
            run("mysql --user=root --password=%s --execute=\"DROP DATABASE %s\"" % (config.mysql_password, config.mysql_name))

            print "", "Creating MySQL database..."
            run("mysql --user=root --password=%s --execute=\"CREATE DATABASE %s\"" % (config.mysql_password, config.mysql_name))
            run("mysql --user=root --password=%s --execute=\"GRANT ALL ON %s.* TO '%s'@'localhost' IDENTIFIED BY '%s'\"" %
                 (config.mysql_password, config.mysql_name, config.mysql_user, config.mysql_password))

@task
def force():
    """Forces the project to have data_transient."""
    env.project.data_transient = True

@task 
def seed(data_branch='master'):
    print "seeding..."
    "Clears the database, recreates it with the data branch."
    resetdb()

    if data_branch == 'test':
        print "Loading test fixtures..."
        with cd_src():
            with prefix("source /www/%s/env/bin/activate" % env.project.key):
                run("python manage.py syncdb --noinput")
                run("python manage.py loaddata testing")
            return

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
def nuke_data_on_qa(data_branch='dev'):
    """
    Sometimes you want to seed qa with data from dole-data repository, but testers have added data to qa so git complains about unmerged changes.
    This will role back qa and git rid of the new changes.
    Use with caution...
    """
    if env.project.key != 'qa':
        raise RuntimeError("Forbidden except for qa.")

    dir = "/www/%s/data" % env.project.key

    with settings(warn_only=True):
        run("git clone git@github.com:Dan-org/dole-data.git %s" % dir)

    with cd(dir):
        print "Bombs away... (qa %s)" % data_branch
        run('git fetch origin %s' % data_branch)
        run('git reset --hard FETCH_HEAD')
        run('git clean -df')
        print "Nuked"        


@task
def restartnginx():
    "Restarts nginx."

    print "Restarting nginx..."
    run("sudo /etc/init.d/nginx restart")


@task
def backup():
    "Backs up the data and media."
    apps = [        
        "analytics",
        "badges",
        "calendar",
        "feedback",
        "instruction",
        "project",
        "site",
        "interactivity",
        "laboratory",
        "quiz",
        "discourse"
    ]

    with settings(warn_only=True):
        run("mkdir /www/%s/data/" % env.project.key)
        run("ln -s /www/%s/src/media /www/%s/data/media" % (env.project.key, env.project.key))
        #with cd("/www/%s/data/" % env.project.key):
        #    run("git init")
        #    run("git remote add origin git@github.com:Dan-org/dole-data.git")
        #    run("git checkout -b %s" % env.project.key)
    
    with cd_src():
        print "Creating fixtures for these apps:"
        for app in apps:
            print "", app
    
        with prefix("source /www/%s/env/bin/activate" % env.project.key):
            app_string = " ".join(apps)
            destination = "/www/%s/data/fixtures.json" % env.project.key
            run("python manage.py cleanup")
            run("python manage.py dumpdata --indent 2 %s > %s" % (app_string, destination))
    
        # version = run("git rev-parse HEAD").strip()

    with cd("/www/%s/data/" % env.project.key):
        print "syncing media..."
        run("rsync -az /www/%s/src/media/ media" % env.project.key)
        print "saving data to git..."
        #run("git pull -s recursive -X ours origin %s" % env.project.key)
        #run("git add .")
        #with settings(warn_only=True):
        #    output = run("git commit -am 'Backup for %s'" % version)
        #if output.failed:
        #    if "nothing to commit" in output:
        #        print "no changes found"
        #        return
        #    else:
        #        abort("git commit failed")
        #run("git push origin %s --force" % env.project.key)
        #print "saved to git"


