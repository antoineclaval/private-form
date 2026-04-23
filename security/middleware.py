"""
Security middleware:
- PIIScrubMiddleware: strips POST body from error pages, scrubs sensitive data from logs
- StripClientIPMiddleware: removes client IP from gunicorn/wsgi environ so it never
  reaches Django's logger. Caddy is configured separately to not log IPs.
"""

import re

_PHONE_RE = re.compile(r"\b(\+?1?\s?[-.]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})\b")
_SIGNAL_RE = re.compile(r"@[\w.]+")

# WSGI environ keys that contain client IP
_IP_ENVIRON_KEYS = (
    "REMOTE_ADDR",
    "HTTP_X_FORWARDED_FOR",
    "HTTP_X_REAL_IP",
    "HTTP_CF_CONNECTING_IP",
)

_REDACTED = "0.0.0.0"  # noqa: S104 — intentional placeholder, not a binding


class PIIScrubMiddleware:
    """
    Prevents PII from appearing in Django error pages and server logs.

    On POST to non-admin paths:
    - Replaces all POST values with [REDACTED] before exception handling runs,
      so Django's debug page / Sentry / any logger never sees form data.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        if request.method == "POST" and not request.path.startswith("/admin/"):
            # Mutate the QueryDict copy so exception reporters see only [REDACTED]
            scrubbed = request.POST.copy()
            for key in list(scrubbed.keys()):
                scrubbed[key] = "[REDACTED]"
            request.POST = scrubbed
        return None


class StripClientIPMiddleware:
    """
    Overwrites client IP environ keys with 0.0.0.0 for all public-form requests.
    Admin paths are left intact (needed for django-axes brute-force tracking).

    This is a second line of defence. Primary protection is Caddy not logging IPs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/admin/"):
            for key in _IP_ENVIRON_KEYS:
                if key in request.META:
                    request.META[key] = _REDACTED

        return self.get_response(request)
