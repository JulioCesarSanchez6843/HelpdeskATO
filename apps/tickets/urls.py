from django.urls import path

from . import views, views_configuracion, views_respaldos


urlpatterns = [
    path("", views.lista_tickets, name="lista_tickets"),

    path("respaldos/", views_respaldos.lista_respaldos, name="lista_respaldos"),

    path("respaldos/crear/", views_respaldos.crear_respaldo, name="crear_respaldo"),

    path("respaldos/subir/", views_respaldos.subir_respaldo, name="subir_respaldo"),

    path("respaldos/restaurar/<str:nombre>/", views_respaldos.restaurar_respaldo, name="restaurar_respaldo"),

    path("respaldos/descargar/<str:nombre>/", views_respaldos.descargar_respaldo, name="descargar_respaldo"),

    path("respaldos/api/", views_respaldos.api_lista, name="api_respaldos"),

    path("respaldos/api/<str:nombre>/", views_respaldos.api_descargar, name="api_respaldo_descargar"),

    path("nuevo/", views.nuevo_ticket, name="nuevo_ticket"),

    path("mis-asignados/", views.mis_asignados, name="mis_asignados"),

    path("adjuntos/<int:pk>/", views.ver_adjunto, name="ver_adjunto"),

    path("confirmar/<str:token>/", views.confirmar_cierre, name="confirmar_cierre"),

    path("en-proceso/<str:token>/", views.marcar_en_proceso, name="marcar_en_proceso"),

    path("acceso/<str:token>/", views.acceso_directo, name="acceso_directo"),

    path("notificaciones/", views.lista_notificaciones, name="lista_notificaciones"),

    path(
        "notificaciones/leer-todas/",
        views.notificaciones_leer_todas,
        name="notificaciones_leer_todas",
    ),

    path(
        "notificaciones/<int:pk>/abrir/",
        views.abrir_notificacion,
        name="abrir_notificacion",
    ),

    path(
        "notificaciones/<int:pk>/leer/",
        views.marcar_notificacion_leida,
        name="marcar_notificacion_leida",
    ),

    path(
        "configuracion/",
        views_configuracion.configuracion_sistema,
        name="configuracion_sistema",
    ),

    path("<int:pk>/", views.detalle_ticket, name="detalle_ticket"),

    path("<int:pk>/responder-cierre/", views.responder_cierre, name="responder_cierre"),

    path("<int:pk>/forzar-cierre/", views.forzar_cierre, name="forzar_cierre"),

    path("<int:pk>/reabrir/", views.reabrir_ticket, name="reabrir_ticket"),

    path("<int:pk>/encuesta/", views.responder_encuesta, name="responder_encuesta"),

    path("<int:pk>/comentar/", views.comentar_ticket, name="comentar_ticket"),

    path("<int:pk>/tomar/", views.tomar_ticket, name="tomar_ticket"),

    path("<int:pk>/asignar/", views.asignar_ticket, name="asignar_ticket"),

    path("<int:pk>/escalar/", views.escalar_ticket, name="escalar_ticket"),
]