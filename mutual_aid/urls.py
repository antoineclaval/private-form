from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from two_factor.urls import urlpatterns as tf_urls

# Admin and two-factor auth — not language-prefixed
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(tf_urls)),
    path("security/", include("security.urls")),
    path("i18n/", include("django.conf.urls.i18n")),  # set_language view
    # Root redirect → Spanish form (default language)
    path("", RedirectView.as_view(url="/es/", permanent=False)),
]

# Public form — language-prefixed (/es/ and /en/)
urlpatterns += i18n_patterns(
    path("", include("requests_app.urls")),
    prefix_default_language=True,
)
