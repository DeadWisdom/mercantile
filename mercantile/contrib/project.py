from fabric.api import env, cd
from fabric import state
from fabric.decorators import task


### Config ###
from mercantile.config import config, required, string_list

conf = config.add_group('projects', {
    'user': unicode | required,         # The username to use as the owner. (Required)
    'git': unicode,                     # Location of the git repository.
    'static': unicode,                  # Directory to alias the url: /static
    'mysql_user': unicode,              # Name of the mysql database user.
    'mysql_password': unicode,          # Password for the mysql database user.
    'mysql_name': unicode,              # Name of the mysql database.
    'data_transient': bool,             # Flag if the data can be killed and rebuilt without warning.
    'server': unicode,                  # The key of a server config.
    'django_settings': unicode,         # Marks this a django project with the given settings.
    'domains': string_list,             # A list of domain names to route to this.
    'wsgi': unicode,                    # Marks this a wsgi app with the given application location.
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

def cd_src():
    return cd("/www/%s/src" % env.project.key)

