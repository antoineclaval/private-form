import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords

from security.encryption import decrypt, encrypt, hash_phone, verify_phone_hash


class Requester(models.Model):
    """
    Represents a person who makes requests. Allows grouping multiple requests
    from the same person without auto-merging.

    PII (phone, Signal username) is Fernet-encrypted at rest. Dedup lookups
    use an Argon2id hash of the phone — not the plaintext or a fast hash.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Encrypted storage — never store plaintext PII
    phone_encrypted = models.BinaryField(blank=True, null=True)
    # Argon2id hash for dedup lookups. NOT SHA-256.
    phone_hash = models.TextField(blank=True, db_index=True)

    signal_username_encrypted = models.BinaryField(blank=True, null=True)
    has_signal = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Requester")
        verbose_name_plural = _("Requesters")

    def __str__(self):
        return f"Requester {str(self.id)[:8]}"

    # -- Phone property (decrypts on access) --

    @property
    def phone(self) -> str:
        if self.phone_encrypted:
            return decrypt(bytes(self.phone_encrypted))
        return ""

    @phone.setter
    def phone(self, value: str):
        if value:
            self.phone_encrypted = encrypt(value)
            self.phone_hash = hash_phone(value)
        else:
            self.phone_encrypted = None
            self.phone_hash = ""

    def phone_matches(self, phone: str) -> bool:
        return verify_phone_hash(phone, self.phone_hash)

    # -- Signal username property (decrypts on access) --

    @property
    def signal_username(self) -> str:
        if self.signal_username_encrypted:
            return decrypt(bytes(self.signal_username_encrypted))
        return ""

    @signal_username.setter
    def signal_username(self, value: str):
        if value:
            self.signal_username_encrypted = encrypt(value)
            self.has_signal = True
        else:
            self.signal_username_encrypted = None
            self.has_signal = False

    @classmethod
    def find_by_phone(cls, phone: str):
        """
        Find an existing Requester whose phone matches, using the Argon2id hash.
        Returns None if not found. O(n) over records with a non-empty hash,
        but the dataset is tiny (<10k) and this runs rarely.

        Note: Argon2id embeds a random salt per hash, so no two hashes of the
        same input are identical. We must verify each candidate individually.
        """
        if not phone:
            return None
        candidates = cls.objects.filter(phone_hash__gt="")
        for candidate in candidates:
            if candidate.phone_matches(phone):
                return candidate
        return None


class AidRequest(models.Model):
    """
    A single mutual aid request. One Requester may have many AidRequests.
    All admin/volunteer changes are tracked via django-simple-history.
    """

    class RequestType(models.TextChoices):
        FOOD_DELIVERY = "food", _("Entrega de Comida")
        SCHOOL = "school", _("Escuela")
        WORK = "work", _("Trabajo")
        MEDICAL_LEGAL = "medical_legal", _("Visitas al Medico / Legales")
        OTHER = "other", _("Otro")

    class Status(models.TextChoices):
        NEW = "new", _("New")
        DISPATCHED = "dispatched", _("Sent to Dispatch")
        CHILDCARE = "childcare", _("Sent to Childcare")
        FOLLOW_UP = "follow_up", _("Follow-up Needed")
        NO_CONTACT = "no_contact", _("Unable to contact")
        COMPLETE = "complete", _("Complete")
        URGENT = "urgent", _("URGENT")

    # -- Identity --
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Human-readable receipt number, continues from last RR# (244)
    request_number = models.PositiveIntegerField(unique=True, editable=False)
    requester = models.ForeignKey(
        Requester,
        on_delete=models.PROTECT,
        related_name="requests",
        verbose_name=_("Requester"),
    )

    # -- Common fields --
    request_type = models.CharField(
        max_length=20,
        choices=RequestType.choices,
        verbose_name=_("Type of Request"),
    )
    date_needed = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Date Needed"),
    )
    # Additional items needed: ["diapers", "food", "carseat", "legal", "baby_supplies"]
    additional_requests = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Additional Requests"),
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes"),
        help_text=_("Anything else you want to tell us?"),
    )

    # -- Ride / transportation fields (school, work, medical_legal, other) --
    pickup_location = models.CharField(max_length=255, blank=True, verbose_name=_("Pickup Location"))
    pickup_neighborhood = models.CharField(max_length=100, blank=True, verbose_name=_("Pickup Neighborhood"))
    dropoff_location = models.CharField(max_length=255, blank=True, verbose_name=_("Drop-off Location"))
    dropoff_neighborhood = models.CharField(
        max_length=100, blank=True, verbose_name=_("Drop-off Neighborhood")
    )
    is_round_trip = models.BooleanField(null=True, blank=True, verbose_name=_("Round Trip?"))
    is_recurring = models.BooleanField(null=True, blank=True, verbose_name=_("Recurring Ride?"))
    recurring_schedule = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Recurring Schedule"),
        help_text=_("e.g. Monday–Friday, every Tuesday"),
    )
    num_passengers = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name=_("Number of Passengers")
    )
    time_preference = models.CharField(max_length=100, blank=True, verbose_name=_("Preferred Time"))

    # -- Food / supply delivery fields --
    delivery_neighborhood = models.CharField(
        max_length=100, blank=True, verbose_name=_("Delivery Neighborhood")
    )
    delivery_day_preference = models.CharField(
        max_length=100, blank=True, verbose_name=_("Preferred Delivery Day")
    )
    delivery_time_preference = models.CharField(
        max_length=100, blank=True, verbose_name=_("Preferred Delivery Time")
    )
    diaper_sizes = models.CharField(max_length=50, blank=True, verbose_name=_("Diaper Sizes"))

    # -- Admin / operational fields (not on public form) --
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        verbose_name=_("Status"),
    )
    contacted = models.BooleanField(default=False, verbose_name=_("Contacted?"))
    dispatcher_notes = models.TextField(blank=True, verbose_name=_("Dispatcher Notes"))
    dispatch_status = models.CharField(max_length=100, blank=True, verbose_name=_("Dispatch Status"))

    # -- Metadata --
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Last Updated"))

    history = HistoricalRecords()

    class Meta:
        verbose_name = _("Aid Request")
        verbose_name_plural = _("Aid Requests")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["request_type", "status"]),
            models.Index(fields=["status"]),
            models.Index(fields=["-created_at"]),
        ]
        permissions = [
            ("can_export_pii", "Can export records with PII (phone, Signal username)"),
        ]

    def __str__(self):
        return f"RR#{self.request_number} — {self.get_request_type_display()}"

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = self._next_request_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _next_request_number() -> int:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT MAX(request_number) FROM requests_app_aidrequest")
            row = cursor.fetchone()
        last = row[0] if row and row[0] else 244  # 244 = last RR#
        return last + 1


class FormConfig(models.Model):
    """
    JSON schema defining which fields appear on the public form, in what order,
    with what labels (English and Spanish), and for which request types.

    Admins can toggle field visibility and update labels without a code deploy.
    Adding a truly new field still requires a migration + schema update.

    Only one FormConfig should be active at a time.
    """

    name = models.CharField(max_length=100, verbose_name=_("Config Name"))
    schema = models.JSONField(verbose_name=_("Form Schema"))
    is_active = models.BooleanField(default=False, verbose_name=_("Active?"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Form Configuration")
        verbose_name_plural = _("Form Configurations")
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="unique_active_form_config",
            )
        ]

    def __str__(self):
        return f"{self.name} {'(active)' if self.is_active else ''}"


# -- Proxy models for scoped admin access --


class FoodRequest(AidRequest):
    """Proxy: food/supply delivery requests only. For food volunteers."""

    class Meta:
        proxy = True
        verbose_name = _("Food / Supply Request")
        verbose_name_plural = _("Food / Supply Requests")


class TransportRequest(AidRequest):
    """Proxy: ride/transport requests only. For dispatch volunteers."""

    class Meta:
        proxy = True
        verbose_name = _("Transport Request")
        verbose_name_plural = _("Transport Requests")
