from datetime import datetime
from fabric.api import env, run, sudo, cd, hide, prefix, prompt, settings
from fabric.contrib.files import append, sed
from fabric.decorators import task

@task
def build():
    env.user = 'root'
    root_password = env.server.mysql_root_password

    print "Installing mysql..."
    sudo("apt-get -qu install debconf-utils")  # Ensures debconf-set-selections exists.

    sudo("echo 'mysql-server mysql-server/root_password select %s' | debconf-set-selections" % root_password)
    sudo("echo 'mysql-server mysql-server/root_password_again select %s' | debconf-set-selections" % root_password)
    sudo("apt-get -qy install mysql-server mysql-client libmysqlclient15-dev")

@task
def backup():
	date = datetime.now().strftime("%Y-%m-%d")

  	with settings(warn_only=True):
		run("mkdir /www/%s/db" % env.project.key)

	print "Backing up data to /www/%s/db/..." % env.project.key
	run(
		"mysqldump -u root -p%s %s | gzip > /www/%s/db/%s.sql.gz" % (
			env.project.mysql_password,
			env.project.mysql_name,
			env.project.key,
			date,
		)
	)

