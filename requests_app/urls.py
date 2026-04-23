from django.urls import path

from . import views

app_name = "requests_app"

urlpatterns = [
    path("", views.form_view, name="form"),
    path("receipt/<int:request_number>/", views.receipt_view, name="receipt"),
]
