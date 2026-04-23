r"""
One-time import of CSV.

Usage (run from inside the toolbox):
    python manage.py stuff-to-import.csv

All PII is encrypted at rest on import.
"""

import csv
import sys
from datetime import UTC, datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from requests_app.models import AidRequest, Requester

# Map existing "Type" values to our RequestType choices
TYPE_MAP = {
    "entrega de comida": AidRequest.RequestType.FOOD_DELIVERY,
    "escuela": AidRequest.RequestType.SCHOOL,
    "trabajo": AidRequest.RequestType.WORK,
    "visitas al medico / legales": AidRequest.RequestType.MEDICAL_LEGAL,
    "visitas al médico / legales": AidRequest.RequestType.MEDICAL_LEGAL,
    "otro (por favor explique abajo)": AidRequest.RequestType.OTHER,
    "otro": AidRequest.RequestType.OTHER,
}

STATUS_MAP = {
    "complete": AidRequest.Status.COMPLETE,
    "sent to childcare": AidRequest.Status.CHILDCARE,
    "follow-up needed": AidRequest.Status.FOLLOW_UP,
    "unable to contact": AidRequest.Status.NO_CONTACT,
    "sent to dispatch": AidRequest.Status.DISPATCHED,
    "food request": AidRequest.Status.DISPATCHED,
    "urgent": AidRequest.Status.URGENT,
}


def _parse_date(value: str):
    if not value:
        return None
    for fmt in ("%m/%d/%Y %I:%M%p", "%m/%d/%Y %H:%M", "%m/%d/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _parse_date_only(value: str):
    if not value:
        return None
    dt = _parse_date(value)
    return dt.date() if dt else None


def _normalize_phone(phone: str) -> str:
    cleaned = phone.strip().lstrip("'")
    return cleaned if cleaned else ""


class Command(BaseCommand):
    help = "Import CSV."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to the CSV file.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate without writing to the database.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"File not found: {csv_path}")

        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no data will be written."))

        imported = 0
        skipped = 0
        errors = []

        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.stdout.write(f"Found {len(rows)} rows. Importing...")

        with transaction.atomic():
            for i, row in enumerate(rows, start=1):
                rr_num_raw = row.get("RR#", "").strip()
                if not rr_num_raw:
                    skipped += 1
                    continue

                try:
                    rr_num = int(rr_num_raw)
                except ValueError:
                    errors.append(f"Row {i}: invalid RR# '{rr_num_raw}'")
                    skipped += 1
                    continue

                # Skip if already imported
                if AidRequest.objects.filter(request_number=rr_num).exists():
                    skipped += 1
                    continue

                # -- Requester --
                phone = _normalize_phone(row.get("Phone #", ""))
                signal_raw = row.get("signal @username", "").strip()

                requester = Requester.find_by_phone(phone) if phone else None
                if requester is None:
                    requester = Requester()

                if phone:
                    requester.phone = phone
                if signal_raw:
                    requester.signal_username = signal_raw

                if not dry_run:
                    requester.save()

                # -- AidRequest --
                raw_type = row.get("Type", "").strip().lower()
                request_type = TYPE_MAP.get(raw_type, AidRequest.RequestType.OTHER)

                raw_status = row.get("Status", "").strip().lower()
                status = STATUS_MAP.get(raw_status, AidRequest.Status.NEW)

                additional = []
                extra_raw = row.get("Additional Request", "").strip().lower()
                if "baby" in extra_raw or "supplies" in extra_raw:
                    additional.append("baby_supplies")
                if "food" in extra_raw:
                    additional.append("food")
                if "carseat" in extra_raw or "car seat" in extra_raw:
                    additional.append("carseat")
                if "legal" in extra_raw:
                    additional.append("legal")
                if "diaper" in extra_raw:
                    additional.append("diapers")

                notes = row.get("Anything else you want to tell us?", "").strip()
                dispatcher_notes = row.get("DISPATCH NOTES", "").strip()
                contacted = bool(row.get("Contacted", "").strip())

                date_needed = _parse_date_only(row.get("Date of Appt", "") or row.get("Date 2", ""))

                time_pref = (
                    row.get("Time Pref", "").strip()
                    or row.get(
                        "SOLO PROVISIONES: ¿A qué hora le gustaría que le entreguemos las provisiones?", ""
                    ).strip()
                )

                pickup_loc = row.get("Pick-up Location", "").strip()
                pickup_nbhd = row.get("Pick up Neighborhood", "").strip()
                dropoff_loc = row.get("Drop-off Location", "").strip()
                dropoff_nbhd = row.get("Drop Off Neighborhood", "").strip()

                round_trip_raw = row.get("round-trip ?", "").strip()
                is_round_trip = bool(round_trip_raw) if round_trip_raw else None

                recurring_raw = (
                    row.get("Reoccuring Ride?", "").strip()
                    or row.get("Is this a reoccuring ride request? i.e M-F or every Tues", "").strip()
                )
                is_recurring = bool(recurring_raw) if recurring_raw else None
                recurring_schedule = recurring_raw if recurring_raw and len(recurring_raw) > 3 else ""

                delivery_day = (
                    row.get("Delivery Day Pref", "").strip()
                    or row.get("What day would you like a ride or supply drop off?", "").strip()
                )
                delivery_time = row.get(
                    "Supplies: What time would you like supplies dropped off?", ""
                ).strip()

                dispatch_status = row.get("Dispatch Status:", "").strip()

                if not dry_run:
                    aid = AidRequest(
                        requester=requester,
                        request_type=request_type,
                        status=status,
                        date_needed=date_needed,
                        additional_requests=additional,
                        notes=notes,
                        pickup_location=pickup_loc,
                        pickup_neighborhood=pickup_nbhd,
                        dropoff_location=dropoff_loc,
                        dropoff_neighborhood=dropoff_nbhd,
                        is_round_trip=is_round_trip,
                        is_recurring=is_recurring,
                        recurring_schedule=recurring_schedule,
                        time_preference=time_pref,
                        delivery_day_preference=delivery_day,
                        delivery_time_preference=delivery_time,
                        contacted=contacted,
                        dispatcher_notes=dispatcher_notes,
                        dispatch_status=dispatch_status,
                    )
                    # Override auto-incrementing request_number with the existing RR#
                    aid.request_number = rr_num
                    # Use save() but skip the _next_request_number logic
                    AidRequest.objects.bulk_create([aid])

                imported += 1

            if dry_run:
                # Roll back so nothing is written
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(f"Done. Imported: {imported}  Skipped: {skipped}  Errors: {len(errors)}")
        )
        for err in errors:
            self.stderr.write(f"  {err}")

        if errors:
            sys.exit(1)
