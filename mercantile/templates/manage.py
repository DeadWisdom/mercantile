#!/www/{{key}}/env/bin/python
import sys

if __name__ == "__main__":
    from settings import setup_environ
    setup_environ("settings.{{key}}")

    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
