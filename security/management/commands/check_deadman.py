"""
Dead man switch: checks when the last admin login occurred.
Run via systemd timer every 12 hours on the production server.

If no admin has logged in within deadman_warn_days: log a warning.
If no admin has logged in within deadman_wipe_days: wipe PII.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Check dead man switch and wipe data if threshold exceeded."

    def handle(self, *args, **options):
        from security.models import SecurityConfig

        config = SecurityConfig.objects.first()
        if not config or not config.deadman_enabled:
            self.stdout.write("Dead man switch is disabled. Exiting.")
            return

        last_login = (
            User.objects.filter(is_staff=True, last_login__isnull=False)
            .order_by("-last_login")
            .values_list("last_login", flat=True)
            .first()
        )

        if last_login is None:
            self.stdout.write("No staff login recorded yet. Skipping.")
            return

        days_since = (timezone.now() - last_login).days
        self.stdout.write(f"Last admin login: {days_since} days ago.")

        if days_since >= config.deadman_wipe_days:
            self.stdout.write(
                self.style.ERROR(
                    f"DEAD MAN SWITCH TRIGGERED: {days_since} days since last login "
                    f"(threshold: {config.deadman_wipe_days}). Wiping data."
                )
            )
            from django.core.management import call_command

            call_command("wipe_data", confirm=True)

        elif days_since >= config.deadman_warn_days:
            self.stdout.write(
                self.style.WARNING(
                    f"WARNING: No admin login in {days_since} days. "
                    f"Data wipe in {config.deadman_wipe_days - days_since} days."
                )
            )
