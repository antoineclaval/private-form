import os

from .base import *  # noqa: F401, F403

DEBUG = False

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

ALLOWED_HOSTS = os.environ["ALLOWED_HOSTS"].split(",")

# Admin POSTs are HTTPS from outside, proxied to gunicorn over HTTP inside the
# pod. Django's CSRF origin check needs the public scheme+host explicitly.
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h and h != "*"]

# Read encryption keys (comma-separated, newest first)
ENCRYPTION_KEYS = os.environ["ENCRYPTION_KEYS"].split(",")
PHONE_HASH_SALT = os.environ["PHONE_HASH_SALT"]

# HTTPS enforcement
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True

# No cookies for anonymous users on the public form is handled per-view.
# Sessions are only used for the admin.

# Content Security Policy (django-csp)
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "style-src": ["'self'"],
        "script-src": ["'none'"],
        "img-src": ["'self'"],
        "font-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "form-action": ["'self'"],
        "base-uri": ["'self'"],
    }
}
