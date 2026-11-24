from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista, name="lista_manuales"),
    path("gestion/", views.gestion, name="gestion_manuales"),
    path("nuevo/", views.nuevo, name="nuevo_manual"),
    path("<int:pk>/", views.ver, name="ver_manual"),
    path("<int:pk>/editar/", views.editar, name="editar_manual"),
    path("<int:pk>/eliminar/", views.eliminar, name="eliminar_manual"),
    path("<int:pk>/aprobar/", views.aprobar, name="aprobar_manual"),
    path("<int:pk>/cancelar/", views.cancelar, name="cancelar_manual"),
    path("<int:pk>/solicitar-eliminacion/", views.solicitar_eliminacion, name="solicitar_eliminacion"),
    path("<int:pk>/rechazar-solicitud/", views.rechazar_solicitud, name="rechazar_solicitud"),
]