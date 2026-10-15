"""WSGI entry point: gunicorn --chdir services/http app:app (install .[web] first)."""
from terralink_core.web import create_app

app=create_app()
