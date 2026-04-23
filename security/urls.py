from django.urls import path

from . import views

urlpatterns = [
    path("wipe/<str:token>/", views.remote_wipe_view, name="remote_wipe"),
]
