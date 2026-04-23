"""
Seed the initial FormConfig with the fields derived from the existing CSV.
All fields present in the model are included; visibility is controlled per-field.
"""

from django.db import migrations

INITIAL_SCHEMA = {
    "sections": [
        {
            "id": "contact",
            "label": {"en": "Contact", "es": "Contacto"},
            "show_for_types": None,  # always visible
            "fields": [
                {
                    "name": "phone",
                    "type": "tel",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Phone Number", "es": "Número de teléfono"},
                    "help_text": {
                        "en": "Your phone number so we can reach you.",
                        "es": "Su número de teléfono para poder contactarle.",
                    },
                    "placeholder": {"en": "e.g. 504-555-1234", "es": "ej. 504-555-1234"},
                },
                {
                    "name": "signal_username",
                    "type": "text",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Signal Username", "es": "Nombre de usuario de Signal"},
                    "help_text": {
                        "en": "If you use Signal, share your username (e.g. @john.123). Download at signal.org",
                        "es": "Si usa Signal, comparta su nombre de usuario (ej. @juan.123). Descárguela en signal.org",
                    },
                    "placeholder": {"en": "@username", "es": "@usuario"},
                },
            ],
        },
        {
            "id": "request_type",
            "label": {"en": "What do you need?", "es": "¿Qué necesita?"},
            "show_for_types": None,
            "fields": [
                {
                    "name": "request_type",
                    "type": "radio",
                    "visible": True,
                    "required": True,
                    "label": {"en": "Type of Request", "es": "Tipo de solicitud"},
                    "choices": [
                        {
                            "value": "food",
                            "label": {
                                "en": "Food / Supply Delivery",
                                "es": "Entrega de Comida / Provisiones",
                            },
                        },
                        {"value": "school", "label": {"en": "School Ride", "es": "Transporte a la Escuela"}},
                        {"value": "work", "label": {"en": "Work Ride", "es": "Transporte al Trabajo"}},
                        {
                            "value": "medical_legal",
                            "label": {"en": "Medical / Legal Visit", "es": "Visita Médica / Legal"},
                        },
                        {"value": "other", "label": {"en": "Other", "es": "Otro"}},
                    ],
                },
            ],
        },
        {
            "id": "ride_details",
            "label": {"en": "Ride Details", "es": "Detalles del Viaje"},
            "show_for_types": ["school", "work", "medical_legal", "other"],
            "fields": [
                {
                    "name": "date_needed",
                    "type": "date",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Date of Appointment / Ride", "es": "Fecha de cita / viaje"},
                },
                {
                    "name": "time_preference",
                    "type": "text",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Preferred Time", "es": "Hora preferida"},
                    "placeholder": {"en": "e.g. 9:00am", "es": "ej. 9:00am"},
                },
                {
                    "name": "pickup_location",
                    "type": "text",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Pickup Address", "es": "Dirección de recogida"},
                },
                {
                    "name": "pickup_neighborhood",
                    "type": "text",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Pickup Neighborhood", "es": "Barrio de recogida"},
                    "placeholder": {
                        "en": "e.g. Kenner, Metairie, NO East",
                        "es": "ej. Kenner, Metairie, NO East",
                    },
                },
                {
                    "name": "dropoff_location",
                    "type": "text",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Drop-off Address", "es": "Dirección de destino"},
                },
                {
                    "name": "dropoff_neighborhood",
                    "type": "text",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Drop-off Neighborhood", "es": "Barrio de destino"},
                },
                {
                    "name": "is_round_trip",
                    "type": "checkbox",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Round trip?", "es": "¿Ida y vuelta?"},
                },
                {
                    "name": "num_passengers",
                    "type": "number",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Number of passengers", "es": "Número de pasajeros"},
                    "attrs": {"min": "1", "max": "20"},
                },
                {
                    "name": "is_recurring",
                    "type": "checkbox",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Is this a recurring ride?", "es": "¿Es un viaje recurrente?"},
                },
                {
                    "name": "recurring_schedule",
                    "type": "text",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Recurring schedule", "es": "Horario recurrente"},
                    "help_text": {
                        "en": "e.g. Monday–Friday, every Tuesday",
                        "es": "ej. Lunes a viernes, cada martes",
                    },
                    "placeholder": {"en": "e.g. Mon–Fri", "es": "ej. Lun–Vie"},
                },
            ],
        },
        {
            "id": "food_details",
            "label": {"en": "Delivery Details", "es": "Detalles de Entrega"},
            "show_for_types": ["food"],
            "fields": [
                {
                    "name": "delivery_neighborhood",
                    "type": "text",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Your neighborhood", "es": "Su barrio"},
                    "placeholder": {
                        "en": "e.g. Kenner, Metairie, NO East",
                        "es": "ej. Kenner, Metairie, NO East",
                    },
                },
                {
                    "name": "delivery_day_preference",
                    "type": "text",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Preferred delivery day", "es": "Día preferido de entrega"},
                    "placeholder": {"en": "e.g. Friday", "es": "ej. Viernes"},
                },
                {
                    "name": "delivery_time_preference",
                    "type": "text",
                    "visible": True,
                    "required": False,
                    "label": {"en": "Preferred delivery time", "es": "Hora preferida de entrega"},
                    "placeholder": {"en": "e.g. morning, after 3pm", "es": "ej. mañana, después de las 3pm"},
                },
                {
                    "name": "diaper_sizes",
                    "type": "text",
                    "visible": True,
                    "required": False,
                    "label": {
                        "en": "Diaper sizes needed (if any)",
                        "es": "Tallas de pañales necesitadas (si aplica)",
                    },
                    "placeholder": {"en": "e.g. Size 3, Size 5", "es": "ej. Talla 3, Talla 5"},
                },
            ],
        },
        {
            "id": "additional",
            "label": {"en": "Additional Needs", "es": "Necesidades Adicionales"},
            "show_for_types": None,
            "fields": [
                {
                    "name": "additional_requests",
                    "type": "checkboxes",
                    "visible": True,
                    "required": False,
                    "label": {
                        "en": "Do you also need any of the following?",
                        "es": "¿También necesita alguno de los siguientes?",
                    },
                    "choices": [
                        {"value": "food", "label": {"en": "Food", "es": "Comida"}},
                        {
                            "value": "baby_supplies",
                            "label": {"en": "Baby supplies", "es": "Artículos para bebé"},
                        },
                        {"value": "diapers", "label": {"en": "Diapers", "es": "Pañales"}},
                        {"value": "carseat", "label": {"en": "Car seat", "es": "Silla de auto"}},
                        {"value": "legal", "label": {"en": "Legal help", "es": "Ayuda legal"}},
                    ],
                },
                {
                    "name": "notes",
                    "type": "textarea",
                    "visible": True,
                    "required": False,
                    "label": {
                        "en": "Anything else you want to tell us?",
                        "es": "¿Algo más que quiera decirnos?",
                    },
                    "attrs": {"rows": "4"},
                },
            ],
        },
    ]
}


def seed_formconfig(apps, schema_editor):
    FormConfig = apps.get_model("requests_app", "FormConfig")
    FormConfig.objects.create(
        name="Initial Form (v1)",
        schema=INITIAL_SCHEMA,
        is_active=True,
    )


def unseed_formconfig(apps, schema_editor):
    FormConfig = apps.get_model("requests_app", "FormConfig")
    FormConfig.objects.filter(name="Initial Form (v1)").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("requests_app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_formconfig, unseed_formconfig),
    ]
