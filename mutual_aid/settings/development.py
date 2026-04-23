from .base import *  # noqa: F401, F403

DEBUG = True

SECRET_KEY = "django-insecure-dev-only-do-not-use-in-production"

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]  # noqa: S104

# Use a local data dir for dev
from pathlib import Path  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "data" / "dev.sqlite3",
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON;",
        },
    }
}

# Encryption keys for development (not secret)
ENCRYPTION_KEYS = ["j8msxCYY6LJgAga277OzTlA6JwnSASSIEnYjUVhfhXQ="]
PHONE_HASH_SALT = "dev-salt-not-secret"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
