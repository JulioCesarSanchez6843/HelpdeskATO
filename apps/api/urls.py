from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login, name="api_login"),
    path("logout/", views.logout, name="api_logout"),
    path("me/", views.me, name="api_me"),
]