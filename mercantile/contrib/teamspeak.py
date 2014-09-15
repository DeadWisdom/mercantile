from fabric.decorators import task
from fabric.api import env, sudo, cd, settings, local

@task
def build():
    try:
        import pyquery
    except ImportError:
        print "PyQuery not found."
        return -1

    print env.user

    ## Add User 
    with settings(warn_only=True):
        sudo("useradd -m -U %s -c \"%s\"" % ("ts", "Teamspeak 3"))

        with cd("/home/%s/" % "ts"):
            # Change the Shell to Bash
            sudo("chsh -s /bin/bash %s" % "ts")

    ## Get Latest Url
    url = get_latest_ts3_url()
    filename = url.rsplit('/', 1)[-1]

    print "TEAMSPEAK:", url, filename

    print "Installing..."

    ## Install
    with cd("/home/ts"):
        sudo("wget %s" % url, user="ts")
        sudo("tar xzf %s" % filename, user="ts")
    
    ## Restart
    with cd("/home/ts/teamspeak3-server_linux-amd64"):
        with settings(warn_only=True):
            sudo("./ts3server_startscript.sh stop", user="ts") 
        sudo("./ts3server_startscript.sh start", user="ts")


### Helpers ###
def get_latest_ts3_url(root="http://teamspeak.gameserver.gamed.de/ts3/releases"):
    from pyquery import PyQuery as pq

    doc = pq(url=root)
    versions = []
    for e in doc("td.n a"):
        if e.text.startswith('3'):
            try:
                tup = e.text.split('.')
                versions.append( tuple(int(x) for x in tup) )
            except:
                continue

    versions.sort(reverse=True)

    for version in versions:
        version = ".".join(str(x) for x in version)
        print "%s/%s/" % (root, version)
        try:
            doc = pq(url="%s/%s/" % (root, version))
        except:
            continue
        target = "teamspeak3-server_linux-amd64-%s.tar.gz" % version
        #target = "teamspeak3-server_linux-x86-%s.tar.gz" % version
        for e in doc("td.n a"):
            print e.text.strip(), target
            if e.text.strip() == target:
                return "%s/%s/%s" % (root, version, target)

    return None