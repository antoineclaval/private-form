import hashlib

from django.http import HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import SecurityConfig


@csrf_exempt
@require_POST
def remote_wipe_view(request, token: str):
    """
    Remote wipe endpoint. Triggered by POSTing to /security/wipe/<token>/.
    The token is compared against SecurityConfig.remote_wipe_token_hash.
    Single-use: after a successful wipe the token hash is cleared.

    This endpoint has no authentication — the token IS the credential.
    Keep it offline and treat it like a private key.
    """
    config = SecurityConfig.objects.first()
    if not config or not config.remote_wipe_token_hash:
        return HttpResponseForbidden("Not configured.")

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    if not config.remote_wipe_token_hash == token_hash:
        return HttpResponseForbidden("Invalid token.")

    # Clear token first (make it single-use even if wipe fails partway)
    config.remote_wipe_token_hash = ""
    config.save(update_fields=["remote_wipe_token_hash"])

    from django.core.management import call_command

    call_command("wipe_data")

    return JsonResponse({"status": "wiped"})
