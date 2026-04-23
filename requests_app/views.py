import time

from django.core import signing
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import AidRequest, FormConfig, Requester

# How long a form token stays valid (seconds). 2 hours is generous for a mobile user.
FORM_TOKEN_MAX_AGE = 7200


def _get_active_config():
    return get_object_or_404(FormConfig, is_active=True)


def _make_form_token():
    """Signed token embedding a timestamp. Used instead of a CSRF cookie."""
    return signing.dumps({"t": time.time()}, salt="form-csrf")


def _validate_form_token(token):
    """Returns True if the token is valid and not expired."""
    try:
        signing.loads(token, salt="form-csrf", max_age=FORM_TOKEN_MAX_AGE)
        return True
    except signing.SignatureExpired:
        return False
    except signing.BadSignature:
        return False


def _get_language(request):
    """Return 'es' or 'en' based on the active i18n language."""
    from django.utils.translation import get_language

    lang = get_language() or "es"
    return "en" if lang.startswith("en") else "es"


def _process_form_data(post, config, lang):
    """
    Parse POST data against the FormConfig schema.
    Returns (requester_data, request_data, errors).
    """
    errors = {}
    requester_data = {}
    request_data = {}

    # Collect all field definitions from config
    all_fields = {}
    for section in config.schema["sections"]:
        for field in section["fields"]:
            all_fields[field["name"]] = field

    # Known requester fields (go to Requester model)
    requester_field_names = {"phone", "signal_username"}

    for name, field_def in all_fields.items():
        if not field_def.get("visible", True):
            continue

        field_type = field_def["type"]

        if field_type == "checkboxes":
            # Multi-select: getlist
            value = post.getlist(name)
        elif field_type == "checkbox":
            value = name in post
        else:
            value = post.get(name, "").strip()

        if field_def.get("required") and not value:
            label = field_def["label"].get(lang, field_def["label"]["es"])
            errors[name] = f"{label} es requerido." if lang == "es" else f"{label} is required."
            continue

        if name in requester_field_names:
            requester_data[name] = value
        else:
            request_data[name] = value

    return requester_data, request_data, errors


@csrf_exempt
@require_http_methods(["GET", "POST"])
def form_view(request):
    config = _get_active_config()
    lang = _get_language(request)

    if request.method == "GET":
        token = _make_form_token()
        return render(
            request,
            "requests_app/form.html",
            {
                "config": config,
                "lang": lang,
                "form_token": token,
            },
        )

    # POST — validate token first
    token = request.POST.get("_form_token", "")
    if not _validate_form_token(token):
        # Token expired or tampered — give a fresh form
        token = _make_form_token()
        return render(
            request,
            "requests_app/form.html",
            {
                "config": config,
                "lang": lang,
                "form_token": token,
                "error": "La sesión expiró. Por favor intente de nuevo."
                if lang == "es"
                else "Session expired. Please try again.",
            },
            status=400,
        )

    requester_data, request_data, errors = _process_form_data(request.POST, config, lang)

    if errors:
        token = _make_form_token()
        return render(
            request,
            "requests_app/form.html",
            {
                "config": config,
                "lang": lang,
                "form_token": token,
                "errors": errors,
                "post_data": request.POST,
            },
            status=400,
        )

    # Get or create Requester by phone (Argon2id dedup)
    phone = requester_data.get("phone", "")
    signal_username = requester_data.get("signal_username", "")

    requester = Requester.find_by_phone(phone) if phone else None
    if requester is None:
        requester = Requester()

    if phone:
        requester.phone = phone
    if signal_username:
        requester.signal_username = signal_username
    requester.save()

    # Create the AidRequest
    aid_request = AidRequest(requester=requester)

    # Map POST data onto model fields
    simple_fields = [
        "request_type",
        "time_preference",
        "pickup_location",
        "pickup_neighborhood",
        "dropoff_location",
        "dropoff_neighborhood",
        "recurring_schedule",
        "delivery_neighborhood",
        "delivery_day_preference",
        "delivery_time_preference",
        "diaper_sizes",
        "notes",
        "dispatch_status",
    ]
    for field in simple_fields:
        if field in request_data:
            setattr(aid_request, field, request_data[field])

    if "date_needed" in request_data and request_data["date_needed"]:
        from datetime import date

        try:
            aid_request.date_needed = date.fromisoformat(request_data["date_needed"])
        except ValueError:
            pass

    if "num_passengers" in request_data and request_data["num_passengers"]:
        try:
            aid_request.num_passengers = int(request_data["num_passengers"])
        except ValueError:
            pass

    aid_request.is_round_trip = request_data.get("is_round_trip", False)
    aid_request.is_recurring = request_data.get("is_recurring", False)
    aid_request.additional_requests = request_data.get("additional_requests", [])

    aid_request.save()

    # PRG: redirect to receipt to prevent double-submit on refresh
    return redirect("requests_app:receipt", request_number=aid_request.request_number)


def receipt_view(request, request_number):
    lang = _get_language(request)
    return render(
        request,
        "requests_app/receipt.html",
        {
            "request_number": request_number,
            "lang": lang,
        },
    )
