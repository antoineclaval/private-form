import logging

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from import_export import fields, resources
from import_export.admin import ExportMixin
from simple_history.admin import SimpleHistoryAdmin

from .models import AidRequest, FoodRequest, FormConfig, Requester, TransportRequest

logger = logging.getLogger(__name__)


# ── Export resources ──────────────────────────────────────────────────────────


class AidRequestSafeResource(resources.ModelResource):
    """Default export: no PII. Includes operational fields only."""

    class Meta:
        model = AidRequest
        fields = (
            "request_number",
            "request_type",
            "status",
            "contacted",
            "date_needed",
            "pickup_neighborhood",
            "dropoff_neighborhood",
            "delivery_neighborhood",
            "is_round_trip",
            "is_recurring",
            "num_passengers",
            "additional_requests",
            "dispatch_status",
            "created_at",
        )
        export_order = fields


class AidRequestPIIResource(resources.ModelResource):
    """Full export including decrypted PII. Requires can_export_pii permission."""

    phone = fields.Field()
    signal_username = fields.Field()

    class Meta:
        model = AidRequest
        fields = (
            "request_number",
            "request_type",
            "status",
            "contacted",
            "phone",
            "signal_username",
            "date_needed",
            "pickup_location",
            "pickup_neighborhood",
            "dropoff_location",
            "dropoff_neighborhood",
            "delivery_neighborhood",
            "notes",
            "dispatcher_notes",
            "dispatch_status",
            "created_at",
        )

    def dehydrate_phone(self, obj):
        return obj.requester.phone

    def dehydrate_signal_username(self, obj):
        return obj.requester.signal_username


# ── Inlines ───────────────────────────────────────────────────────────────────


class AidRequestInline(admin.TabularInline):
    model = AidRequest
    extra = 0
    fields = ("request_number", "request_type", "status", "date_needed", "created_at")
    readonly_fields = ("request_number", "request_type", "date_needed", "created_at")
    show_change_link = True
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# ── Requester admin ───────────────────────────────────────────────────────────


@admin.register(Requester)
class RequesterAdmin(admin.ModelAdmin):
    list_display = (
        "short_id",
        "phone_display",
        "signal_display",
        "has_signal",
        "request_count",
        "created_at",
    )
    list_filter = ("has_signal", "created_at")
    readonly_fields = ("id", "phone_display", "signal_display", "phone_hash", "created_at")
    inlines = [AidRequestInline]
    search_fields = ("id",)

    fieldsets = (
        (
            None,
            {
                "fields": ("id", "created_at"),
            },
        ),
        (
            _("Contact Information (encrypted)"),
            {
                "fields": ("phone_display", "signal_display", "has_signal"),
            },
        ),
    )

    def short_id(self, obj):
        return str(obj.id)[:8]

    short_id.short_description = "ID"

    def phone_display(self, obj):
        return obj.phone or "—"

    phone_display.short_description = _("Phone")

    def signal_display(self, obj):
        return obj.signal_username or "—"

    signal_display.short_description = _("Signal Username")

    def request_count(self, obj):
        return obj.requests.count()

    request_count.short_description = _("# Requests")


# ── AidRequest admin base ─────────────────────────────────────────────────────


class AidRequestAdmin(ExportMixin, SimpleHistoryAdmin):
    list_display = (
        "request_number",
        "request_type",
        "status",
        "contacted",
        "requester_phone",
        "date_needed",
        "created_at",
    )
    list_filter = ("request_type", "status", "contacted", "created_at")
    list_editable = ("status", "contacted")
    search_fields = ("request_number", "notes", "dispatcher_notes", "pickup_location", "dropoff_location")
    readonly_fields = ("id", "request_number", "requester", "created_at", "updated_at")
    date_hierarchy = "created_at"

    fieldsets = (
        (
            _("Request"),
            {
                "fields": ("request_number", "id", "requester", "request_type", "status", "date_needed"),
            },
        ),
        (
            _("Ride Details"),
            {
                "classes": ("collapse",),
                "fields": (
                    "pickup_location",
                    "pickup_neighborhood",
                    "dropoff_location",
                    "dropoff_neighborhood",
                    "is_round_trip",
                    "is_recurring",
                    "recurring_schedule",
                    "num_passengers",
                    "time_preference",
                ),
            },
        ),
        (
            _("Food / Supply Details"),
            {
                "classes": ("collapse",),
                "fields": (
                    "delivery_neighborhood",
                    "delivery_day_preference",
                    "delivery_time_preference",
                    "diaper_sizes",
                ),
            },
        ),
        (
            _("Additional"),
            {
                "fields": ("additional_requests", "notes"),
            },
        ),
        (
            _("Dispatch"),
            {
                "fields": ("contacted", "dispatcher_notes", "dispatch_status"),
            },
        ),
        (
            _("Metadata"),
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    def requester_phone(self, obj):
        return obj.requester.phone or "—"

    requester_phone.short_description = _("Phone")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("requester")

    def get_export_resource_class(self):
        return AidRequestSafeResource

    def get_export_queryset(self, request, **kwargs):
        qs = super().get_export_queryset(request, **kwargs)
        # Log every export regardless of PII level
        logger.warning(
            "CSV export by %s: %d records, resource=%s",
            request.user.username,
            qs.count(),
            self.get_export_resource_class().__name__,
        )
        return qs

    def export_admin_action(self, request, queryset):
        """Override to check PII permission and swap resource if granted."""
        if request.user.has_perm("requests_app.can_export_pii"):
            self.resource_classes = [AidRequestPIIResource]
            logger.warning(
                "PII export by %s: %d records",
                request.user.username,
                queryset.count(),
            )
        else:
            self.resource_classes = [AidRequestSafeResource]
        return super().export_admin_action(request, queryset)


# ── Registered admin classes ──────────────────────────────────────────────────


@admin.register(AidRequest)
class AllAidRequestAdmin(AidRequestAdmin):
    pass


@admin.register(FoodRequest)
class FoodRequestAdmin(AidRequestAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(request_type=AidRequest.RequestType.FOOD_DELIVERY)


@admin.register(TransportRequest)
class TransportRequestAdmin(AidRequestAdmin):
    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .filter(
                request_type__in=[
                    AidRequest.RequestType.SCHOOL,
                    AidRequest.RequestType.WORK,
                    AidRequest.RequestType.MEDICAL_LEGAL,
                    AidRequest.RequestType.OTHER,
                ]
            )
        )


@admin.register(FormConfig)
class FormConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    readonly_fields = ("created_at",)

    def save_model(self, request, obj, form, change):
        if obj.is_active:
            # Singleton: deactivate all others before activating this one
            FormConfig.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)
