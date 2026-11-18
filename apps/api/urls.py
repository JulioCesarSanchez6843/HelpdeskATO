from django.urls import path

from . import views, views_gestion

urlpatterns = [
    path("login/", views.login, name="api_login"),
    path("logout/", views.logout, name="api_logout"),
    path("me/", views.me, name="api_me"),
    path("tickets/", views.tickets_lista, name="api_tickets"),
    path("tickets/nuevo/", views_gestion.ticket_nuevo, name="api_ticket_nuevo"),
    path("tickets/<int:pk>/", views.ticket_detalle, name="api_ticket_detalle"),
    path("tickets/<int:pk>/comentarios/", views.ticket_comentar, name="api_ticket_comentar"),
    path("tickets/<int:pk>/tomar/", views.ticket_tomar, name="api_ticket_tomar"),
    path("tickets/<int:pk>/asignar/", views_gestion.ticket_asignar, name="api_ticket_asignar"),
    path("tickets/<int:pk>/opciones/", views_gestion.ticket_opciones, name="api_ticket_opciones"),
]