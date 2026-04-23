from django.db import models
from django.utils.translation import gettext_lazy as _


class SecurityConfig(models.Model):
    """
    Runtime security configuration. Only one row should exist.
    Managed via Django admin by superusers only.
    """

    deadman_enabled = models.BooleanField(default=False, verbose_name=_("Dead Man Switch Enabled"))
    deadman_warn_days = models.PositiveIntegerField(
        default=7,
        verbose_name=_("Warn after N days without admin login"),
    )
    deadman_wipe_days = models.PositiveIntegerField(
        default=14,
        verbose_name=_("Wipe after N days without admin login"),
    )
    # Remote wipe token: SHA-256 of an offline-generated secret.
    # Generate with: manage.py generate_wipe_token
    remote_wipe_token_hash = models.CharField(
        max_length=128,
        blank=True,
        verbose_name=_("Remote Wipe Token Hash"),
        help_text=_("SHA-256 of the offline wipe token. Generate with: manage.py generate_wipe_token"),
    )

    class Meta:
        verbose_name = _("Security Configuration")
        verbose_name_plural = _("Security Configuration")

    def __str__(self):
        return "Security Configuration"
