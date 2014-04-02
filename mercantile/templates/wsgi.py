"""
WSGI config for the DFA.
"""

# Setup the environment
from settings import setup_environ
setup_environ("settings.{{key}}")

# Setup the application
from django.core.wsgi import get_wsgi_application
app = application = get_wsgi_application()
