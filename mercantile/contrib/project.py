import posixpath

from fabric.api import env, cd, prefix
from fabric import state
from fabric.decorators import task


### Config ###
from mercantile.config import config, required, string_list

conf = config.add_group('projects', {
    'user': unicode | required,         # The username to use as the owner. (Required)
    'root': unicode,                    # Root to the directory of the project.
    'git': unicode,                     # Location of the git repository.
    'data_transient': bool,             # Flag if the data can be killed and rebuilt without warning.
    'server': unicode,                  # The key of a server config.
    'domains': string_list,             # A list of domain names to route to this.
    'wsgi': unicode,                    # Marks this a wsgi app with the given application location.
    'gems': string_list,                # Gems to install when creating the project.
})


def project_required(fn):
    def project_wrapper(*args, **kwargs):
        if not getattr(env, 'project', None):
            print "You must select a project first, e.g.\n> fab qa ..."
            return -1
        return fn(*args, **kwargs)
    project_wrapper.func_name = fn.func_name
    return project_wrapper

env.project = None
def activate_project(key):
    env.project = conf[key]

    if env.project.server:
        import server
        server.activate(env.project.server)

    if not env.project.root:
        env.project.root = posixpath.join(env.server.service_root, env.project.key)

    if env.project.user:
        env.user = env.project.user

def project_task(key):
    def _task():
        activate_project(key)
    _task.__doc__ = "Selects this project for the next commands."
    return task(name=key)(_task)

@config.on_load
def add_project_tasks():
    for k in conf.keys():
        state.commands[k] = project_task(k)

def root(*next):
    if not env.project.root:
        env.project.root = posixpath.join(env.server.root, env.project.key)
    return posixpath.join(env.project.root, *next)

def cd_src():
    return cd(root('src'))

def prefix_env():
    return prefix("source %s" % root('env/bin/activate'))


