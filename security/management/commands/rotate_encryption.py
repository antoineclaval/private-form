"""
Re-encrypt all PII fields with the newest key in ENCRYPTION_KEYS.

Run this after adding a new key to ENCRYPTION_KEYS (newest first):
    python manage.py rotate_encryption

After rotation, remove the old key from ENCRYPTION_KEYS and restart.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Re-encrypt all PII fields using the newest key in ENCRYPTION_KEYS."

    def handle(self, *args, **options):
        from cryptography.fernet import MultiFernet

        from requests_app.models import Requester
        from security.encryption import _get_fernet, decrypt, encrypt

        fernet = _get_fernet()
        if not isinstance(fernet, MultiFernet):
            self.stdout.write("Only one key configured — nothing to rotate.")
            return

        count = 0
        errors = 0

        for requester in Requester.objects.all():
            changed = False
            try:
                if requester.phone_encrypted:
                    phone = decrypt(bytes(requester.phone_encrypted))
                    requester.phone_encrypted = encrypt(phone)
                    changed = True
                if requester.signal_username_encrypted:
                    sig = decrypt(bytes(requester.signal_username_encrypted))
                    requester.signal_username_encrypted = encrypt(sig)
                    changed = True
                if changed:
                    requester.save(update_fields=["phone_encrypted", "signal_username_encrypted"])
                    count += 1
            except Exception as e:  # noqa: BLE001
                self.stderr.write(f"Error on Requester {requester.id}: {e}")
                errors += 1

        self.stdout.write(self.style.SUCCESS(f"Rotation complete. Updated: {count}  Errors: {errors}"))
        if errors == 0:
            self.stdout.write(
                "You can now remove the old key from ENCRYPTION_KEYS and restart the container."
            )
