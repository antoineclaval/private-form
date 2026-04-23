"""
Emergency data destruction command.

Zeros all PII from Requester records, clears free-text from AidRequests,
purges history, and VACUUMs the SQLite database.

IMPORTANT: VACUUM alone is not secure deletion on SSDs — LUKS full disk
encryption is the primary guarantee. This command is defense-in-depth.
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Emergency: zero all PII and sensitive data from the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Required flag to confirm the destructive operation.",
        )

    def handle(self, *args, **options):
        if not options["confirm"]:
            self.stderr.write("This command permanently destroys data. Re-run with --confirm to proceed.")
            return

        self.stdout.write("Starting data wipe...")

        from requests_app.models import AidRequest, Requester

        # 1. Zero all PII on Requester
        count = Requester.objects.count()
        Requester.objects.update(
            phone_encrypted=None,
            phone_hash="",
            signal_username_encrypted=None,
            has_signal=False,
        )
        self.stdout.write(f"  Zeroed PII on {count} Requester records.")

        # 2. Clear free-text fields on AidRequest
        req_count = AidRequest.objects.count()
        AidRequest.objects.update(
            notes="",
            dispatcher_notes="",
            pickup_location="",
            dropoff_location="",
            recurring_schedule="",
            dispatch_status="",
        )
        self.stdout.write(f"  Cleared free-text on {req_count} AidRequest records.")

        # 3. Delete all history records
        AidRequest.history.all().delete()
        Requester.history.all().delete() if hasattr(Requester, "history") else None
        self.stdout.write("  Deleted history records.")

        # 4. VACUUM the database (rewrites file; defense-in-depth alongside LUKS)
        with connection.cursor() as cursor:
            cursor.execute("VACUUM")
        self.stdout.write("  VACUUMed SQLite database.")

        self.stdout.write(self.style.SUCCESS("Data wipe complete."))
