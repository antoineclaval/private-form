from django.contrib import admin

from .models import SecurityConfig


@admin.register(SecurityConfig)
class SecurityConfigAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Dead Man Switch",
            {
                "fields": ("deadman_enabled", "deadman_warn_days", "deadman_wipe_days"),
            },
        ),
        (
            "Remote Wipe",
            {
                "fields": ("remote_wipe_token_hash",),
            },
        ),
    )

    def has_add_permission(self, request):
        # Singleton: only allow adding if none exist
        return not SecurityConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
