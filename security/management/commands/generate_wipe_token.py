"""
Generate a remote wipe token. Run this once, store the token offline,
and paste the hash into SecurityConfig.remote_wipe_token_hash in the admin.

Usage:
    python manage.py generate_wipe_token

Output:
    TOKEN (keep offline, treat like a private key):  abc123...
    HASH  (paste into SecurityConfig in the admin):  sha256:def456...
"""

import hashlib
import secrets

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generate a one-time remote wipe token and its SHA-256 hash."

    def handle(self, *args, **options):
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.WARNING("REMOTE WIPE TOKEN — KEEP OFFLINE"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"\nTOKEN (keep secret, store offline):\n  {token}\n")
        self.stdout.write(f"HASH  (paste into SecurityConfig → Remote Wipe Token Hash):\n  {token_hash}\n")
        self.stdout.write("=" * 60)
        self.stdout.write(
            f"\nTo trigger a remote wipe:\n  curl -X POST https://yourdomain.org/security/wipe/{token}/\n"
        )
        self.stdout.write("=" * 60 + "\n")
