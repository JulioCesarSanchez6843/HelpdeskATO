from django.conf import settings

from apps.tickets.models import ConfiguracionSistema

NOMBRES_PRIORIDAD = {
    "CRITICA": "Crítica",
    "ALTA": "Alta",
    "MEDIA": "Media",
    "BAJA": "Baja",
}


def _seccion(icono, titulo, texto="", *puntos):
    return {"icono": icono, "titulo": titulo, "texto": texto, "puntos": list(puntos)}


def _horas_sla():
    return ", ".join(
        f"{NOMBRES_PRIORIDAD.get(clave, clave)}: {horas} h"
        for clave, horas in settings.SLA_HORAS.items()
    )


def _dias_enlace():
    return settings.ACCESO_TOKEN_MAX_AGE // 86400

def _cierre_para_usuario():
    config = ConfiguracionSistema.actual()
    if not config.cierre_automatico_activo:
        return "Mientras no confirmes o rechaces, el ticket queda esperando tu respuesta."
    texto = f"Si no respondes en {config.cierre_automatico_dias} días, el sistema cierra el ticket solo."
    if config.recordatorio_activo:
        texto += f" Te avisa {config.recordatorio_dias_antes} días antes."
    return texto


def _cierre_automatico_actual():
    config = ConfiguracionSistema.actual()
    if config.cierre_automatico_activo:
        return (
            "Cierre automático: está activo. Cierra los tickets que llevan "
            f"{config.cierre_automatico_dias} días en «Por confirmar» sin respuesta."
        )
    return "Cierre automático: está desactivado. Puedes activarlo y elegir los días."

def _recordatorio_actual():
    config = ConfiguracionSistema.actual()
    if config.recordatorio_activo:
        return (
            "Recordatorio: está activo. Avisa al usuario "
            f"{config.recordatorio_dias_antes} días antes del cierre automático."
        )
    return "Recordatorio: está desactivado. El usuario no recibe aviso antes del cierre automático."

def _estados():
    return _seccion(
        "bi-signpost-split",
        "Estados de un ticket",
        "Todo ticket pasa por estos estados:",
        "Abierto: el ticket se creó y espera a que alguien de soporte lo atienda.",
        "En proceso: alguien de soporte ya está trabajando en él.",
        "En espera de materiales: falta algo para continuar. El motivo queda en el historial.",
        "Por confirmar: soporte lo resolvió y espera que quien lo creó confirme que quedó bien.",
        "Cerrado: el ticket terminó. Puede reabrirse dentro del plazo permitido.",
    )


def _sla_usuario():
    return _seccion(
        "bi-stopwatch",
        "Prioridad y tiempos de atención",
        "La prioridad la define el equipo de soporte, tú no tienes que elegirla. "
        "Según su nivel, cada ticket tiene un tiempo máximo de atención. "
        "No necesitas hacer nada: si tu ticket tarda, soporte recibe avisos automáticos.",
    )


def _sla_personal():
    return _seccion(
        "bi-stopwatch",
        "Prioridad y SLA",
        "Cada prioridad tiene un tiempo máximo de atención desde que se asigna: "
        + _horas_sla()
        + ".",
        f"Cuando se consume el {settings.SLA_AVISO_PORCENTAJE}% del tiempo se avisa por notificación y correo que el ticket está por vencer.",
        "Al vencer el tiempo se avisa de nuevo.",
        "Un ticket sin prioridad no tiene vencimiento. La prioridad se fija al asignarlo o al escalarlo.",
    )


def _notificaciones():
    return _seccion(
        "bi-bell",
        "Notificaciones y correos",
        "La campana de la barra superior muestra un número rojo cuando tienes avisos sin leer.",
        "Al abrir una notificación te lleva directo al ticket y se marca como leída.",
        "Dentro de la lista puedes marcar todas como leídas.",
        f"Los enlaces de los correos entran directo al ticket y duran {_dias_enlace()} días.",
        "En Ajustes puedes activar o desactivar los correos que recibes.",
    )


def _actividad(propia=True, alcance=""):
    if propia:
        return _seccion(
            "bi-clock-history",
            "Mi actividad",
            "Es la línea del tiempo de lo que has hecho y de lo que ha pasado con tus tickets.",
            "Puedes filtrarla por fechas y tipo de evento.",
            "También puedes exportarla.",
        )
    return _seccion(
        "bi-clock-history",
        "Actividad",
        f"Es el registro de lo que ocurre en el sistema {alcance}.",
        "Muestra quién hizo qué y cuándo: tickets, asignaciones, escaladas, cierres y cambios de usuarios.",
        "Puedes filtrar por persona, fechas y tipo de evento, y exportarla.",
    )


def _cuenta():
    return _seccion(
        "bi-person-gear",
        "Mi perfil y Ajustes",
        "Los dos están en el menú de la esquina superior derecha (las tres rayitas).",
        "Mi perfil: tu foto y los datos de tu cuenta.",
        "Ajustes: tipo de letra, tamaño, interlineado, página que se abre al iniciar sesión y qué correos recibes. Solo afecta tu cuenta y puedes restablecerlo.",
        "Si olvidas tu contraseña, usa «¿Olvidaste tu contraseña?» en la pantalla de inicio de sesión.",
    )


def _comentarios_personal():
    return _seccion(
        "bi-chat-left-text",
        "Comentarios y notas internas",
        "Dentro del ticket puedes comentar y adjuntar imágenes.",
        "Si marcas «interno», el comentario solo lo ve el personal de soporte. El usuario no lo ve.",
        "Sin marcar, el comentario lo ve también quien creó el ticket.",
        "En un ticket cerrado ya no se puede comentar.",
    )


def _gestion_personal():
    return _seccion(
        "bi-sliders2",
        "Gestionar un ticket",
        "En el detalle del ticket está el bloque de gestión:",
        "Estado: cámbialo conforme avanzas.",
        "En espera de materiales: obliga a escribir qué falta, y el usuario lo verá en el historial.",
        "Por confirmar: obliga a escribir la nota de resolución y le manda un correo al usuario para que confirme.",
        "Categoría y número de serie / Service Tag del equipo.",
        "El ticket se cierra cuando el usuario confirma. Tú no lo cierras directamente.",
    )


def _tomar_y_asignados():
    return [
        _seccion(
            "bi-hand-index-thumb",
            "Tomar un ticket",
            "Un ticket abierto y sin asignar muestra el botón «Tomar».",
            "Solo puedes tomar tickets de tu sucursal.",
            "Si otra persona lo tomó antes, ya no estará disponible.",
            "Al tomarlo queda asignado a ti.",
        ),
        _seccion(
            "bi-kanban",
            "Mis asignados",
            "Es un tablero con una columna por estado que muestra solo los tickets que tienes asignados.",
            "Cada tarjeta se ordena por vencimiento del SLA, para que veas qué atender primero.",
        ),
    ]


def _cola(sucursal=True):
    alcance = "de tu sucursal" if sucursal else "de todas las sucursales"
    return _seccion(
        "bi-ticket-perforated",
        "Cola de tickets",
        f"En Tickets ves los tickets {alcance}.",
        "Puedes buscar escribiendo y el resultado se actualiza solo.",
        "Puedes ordenarlos por vencimiento del SLA, por prioridad o por más recientes.",
        "Los tickets pendientes aparecen primero y los cerrados al final.",
    )


def _usuario():
    return {
        "intro": "Aquí reportas problemas técnicos y sigues su atención hasta que se resuelven.",
        "secciones": [
            _seccion(
                "bi-info-circle",
                "Cómo funciona el sistema",
                "Cuando algo no funciona, creas un ticket. El equipo de soporte de tu sucursal lo atiende y tú ves cada avance.",
                "Solo ves los tickets que tú creaste.",
                "Recibes avisos por la campana y por correo.",
            ),
            _seccion(
                "bi-plus-circle",
                "Crear un ticket",
                "Entra a «Mis Tickets» y pulsa «Nuevo ticket».",
                "Escribe un título corto y describe qué pasa. Entre más detalle, más rápido se resuelve.",
                "Agrega fotos o capturas de pantalla si ayudan.",
                "El ticket queda registrado en tu sucursal y área, y recibes un correo de confirmación.",
            ),
            _seccion(
                "bi-search",
                "Seguir tu ticket",
                "En «Mis Tickets» ves todos los tuyos con su estado.",
                "Al abrir uno ves quién lo atiende y su historial completo.",
                "Mientras no esté cerrado puedes comentar para dar más información o responder preguntas.",
            ),
            _estados(),
            _seccion(
                "bi-check2-circle",
                "Confirmar que quedó resuelto",
                "Cuando soporte termina, el ticket pasa a «Por confirmar» y te llega un correo y una notificación.",
                "Si quedó bien, pulsa Confirmar y el ticket se cierra.",
                "Si el problema sigue, pulsa Rechazar y escribe el motivo. El ticket vuelve a atenderse.",
                "Puedes responder desde el correo o desde el detalle del ticket.",
                _cierre_para_usuario(),
            ),
            _seccion(
                "bi-star",
                "Calificar y reabrir",
                "Con el ticket cerrado puedes calificar la atención de 1 a 5 estrellas y dejar un comentario.",
                f"Si el problema regresa, puedes reabrir el ticket dentro de los {settings.REABRIR_TICKET_DIAS} días siguientes al cierre. Debes escribir el motivo.",
                "Pasado ese plazo, crea un ticket nuevo.",
            ),
            _sla_usuario(),
            _notificaciones(),
            _actividad(propia=True),
            _cuenta(),
        ],
    }


def _becario():
    return {
        "intro": "Atiendes los tickets de tu sucursal: los tomas, los trabajas y los dejas listos para que el usuario confirme.",
        "secciones": [
            _seccion(
                "bi-info-circle",
                "Qué puedes hacer y qué no",
                "Tu trabajo es atender tickets. Puedes:",
                "Ver los tickets de tu sucursal.",
                "Tomar tickets sin asignar y trabajarlos.",
                "Comentar, dejar notas internas y cambiar estado, categoría y número de serie.",
                "No puedes crear tickets (eso lo hacen los usuarios), cambiar la prioridad, asignar a otros ni escalar. Eso lo hace un encargado.",
            ),
            _seccion(
                "bi-list",
                "El menú lateral",
                "Inicio: un resumen con tus pendientes.",
                "Tickets: la cola de tu sucursal y, dentro, tus asignados.",
                "Actividad: el registro de lo que has hecho y lo relacionado contigo.",
            ),
            _cola(sucursal=True),
            *_tomar_y_asignados(),
            _gestion_personal(),
            _comentarios_personal(),
            _estados(),
            _sla_personal(),
            _notificaciones(),
            _actividad(propia=True),
            _cuenta(),
        ],
    }


def _encargado():
    return {
        "intro": "Coordinas el soporte de tu sucursal: priorizas, asignas, escalas y administras a tu equipo.",
        "secciones": [
            _seccion(
                "bi-info-circle",
                "Qué puedes hacer",
                "Además de atender tickets como un becario, tú:",
                "Defines la prioridad y asignas tickets a tu equipo.",
                "Escalas al super administrador lo que no puedas resolver.",
                "Cierras tickets cuando el usuario no responde.",
                "Administras usuarios, áreas, categorías y puestos de tu sucursal, y consultas reportes.",
                "Todo se limita a tu sucursal. Las demás no las ves.",
            ),
            _seccion(
                "bi-list",
                "El menú lateral",
                "Inicio, Tickets, Usuarios, Áreas, Categorías, Puestos, Reportes y Actividad.",
                "Sucursales y Parámetros del sistema son solo del super administrador.",
            ),
            _cola(sucursal=True),
            *_tomar_y_asignados(),
            _gestion_personal(),
            _seccion(
                "bi-person-check",
                "Asignar y priorizar",
                "En el detalle del ticket, el bloque «Asignar a» te deja elegir a un encargado o becario activo de tu sucursal.",
                "Al asignar debes elegir la prioridad (SLA). Con eso empieza a correr el tiempo de atención.",
                "También puedes cambiar la prioridad desde el bloque de gestión.",
                "El avance del ticket queda en el historial.",
            ),
            _seccion(
                "bi-arrow-up-circle",
                "Escalar al super administrador",
                "Si un ticket rebasa lo que puede resolver tu sucursal, usa «Escalar».",
                "Elige a quién escalar, la prioridad y escribe el motivo (mínimo 10 caracteres).",
                "No se puede escalar un ticket cerrado.",
                "El usuario no ve las escaladas en el historial. Es información interna.",
            ),
            _seccion(
                "bi-x-octagon",
                "Cerrar sin confirmación",
                "Si un ticket está «Por confirmar» y el usuario no responde, puedes cerrarlo.",
                "Debes escribir una justificación (mínimo 10 caracteres).",
                "Solo funciona con tickets en «Por confirmar».",
            ),
            _comentarios_personal(),
            _estados(),
            _sla_personal(),
            _seccion(
                "bi-people",
                "Usuarios de tu sucursal",
                "En Usuarios ves y administras a las personas de tu sucursal.",
                "Puedes crear becarios y usuarios.",
                "Puedes editar sus datos, activarlos o desactivarlos.",
                "Puedes enviarles un correo para que restablezcan su contraseña.",
                "Para quitar a alguien, desactívalo en lugar de borrarlo, así se conserva su historial.",
            ),
            _seccion(
                "bi-tags",
                "Áreas, categorías y puestos",
                "Son los catálogos que se usan al registrar usuarios y clasificar tickets.",
                "Puedes crear, editar y eliminar los de tu sucursal.",
                "Las categorías ayudan a que los reportes muestren qué tipo de problemas son más comunes.",
            ),
            _seccion(
                "bi-bar-chart-line",
                "Reportes",
                "Muestran el desempeño de tu sucursal: volumen de tickets, tiempos de atención, cumplimiento de SLA y satisfacción.",
                "Puedes filtrar por fechas y exportar los tickets resueltos a Excel.",
            ),
            _notificaciones(),
            _actividad(propia=False, alcance="de tu sucursal"),
            _cuenta(),
        ],
    }


def _superadmin(usuario):
    secciones = [
        _seccion(
            "bi-info-circle",
            "Qué puedes hacer",
            "Tienes visión de todas las sucursales y administras el sistema completo.",
            "Ves y gestionas los tickets de todas las sucursales.",
            "No tomas tickets: recibes los que te escalan los encargados.",
            "Creas sucursales y usuarios, y configuras el comportamiento automático del sistema.",
        ),
        _seccion(
            "bi-list",
            "El menú lateral",
            "Inicio, Tickets, Usuarios, Sucursales, Áreas, Categorías, Puestos, Reportes y Actividad.",
            "En el menú de la esquina superior derecha está «Parámetros del sistema».",
        ),
        _cola(sucursal=False),
        _seccion(
            "bi-arrow-down-circle",
            "Tickets escalados",
            "Cuando un encargado escala un ticket, recibes notificación con el motivo y la prioridad.",
            "Puedes gestionarlo igual que cualquier ticket: cambiar estado, comentar y dejar notas internas.",
            "Puedes asignarlo a un encargado o becario de la sucursal del ticket.",
        ),
        _gestion_personal(),
        _seccion(
            "bi-person-check",
            "Asignar, priorizar y cerrar",
            "Puedes asignar cualquier ticket a un encargado o becario activo de su sucursal, y definir su prioridad.",
            "Si un ticket está «Por confirmar» y el usuario no responde, puedes cerrarlo con una justificación (mínimo 10 caracteres).",
        ),
        _comentarios_personal(),
        _estados(),
        _sla_personal(),
        _seccion(
            "bi-building",
            "Sucursales",
            "En Sucursales creas y editas cada una.",
            "Puedes subir su logo y activarla o desactivarla.",
            "Cada sucursal tiene su propio equipo y sus propios catálogos.",
            "Todo usuario que no sea super administrador necesita una sucursal asignada.",
        ),
        _seccion(
            "bi-people",
            "Usuarios",
            "Puedes crear encargados, becarios y usuarios en cualquier sucursal.",
            "Puedes editarlos, activarlos o desactivarlos y enviarles un correo para restablecer su contraseña.",
            "Para quitar a alguien, desactívalo en lugar de borrarlo, así se conserva su historial.",
        ),
        _seccion(
            "bi-tags",
            "Áreas, categorías y puestos",
            "Son los catálogos de cada sucursal. Tú puedes administrarlos en todas.",
        ),
        _seccion(
            "bi-bar-chart-line",
            "Reportes",
            "Muestran volumen, tiempos de atención, cumplimiento de SLA y satisfacción.",
            "Con el filtro de sucursal ves todo el sistema o una sola sucursal.",
            "Puedes exportar los tickets resueltos a Excel.",
        ),
        _seccion(
            "bi-sliders",
            "Parámetros del sistema",
            "Están en el menú de la esquina superior derecha.",
            _cierre_automatico_actual(),
            _recordatorio_actual(),
            f"El enlace de confirmación del correo dura {_dias_enlace()} días, así que los días de cierre no pueden ser menores.",
        ),
        _notificaciones(),
        _actividad(propia=False, alcance="de todas las sucursales"),
        _cuenta(),
    ]
    if usuario.es_maestro:
        secciones.insert(
            2,
            _seccion(
                "bi-shield-lock",
                "Cuenta maestra",
                "Tu cuenta es la maestra del sistema.",
                "Puedes crear y administrar a otros super administradores, algo que un super administrador normal no puede hacer.",
                "Si el sistema te pide cambiar la contraseña, debes hacerlo antes de seguir usando el sistema.",
            ),
        )
    return {
        "intro": "Administras todo el sistema: sucursales, usuarios, catálogos, reportes y parámetros.",
        "secciones": secciones,
    }


def ayuda_para(usuario):
    if usuario.es_superadmin:
        contenido = _superadmin(usuario)
    elif usuario.es_encargado:
        contenido = _encargado()
    elif usuario.es_becario:
        contenido = _becario()
    else:
        contenido = _usuario()
    contenido["rol_etiqueta"] = usuario.get_rol_display()
    return contenido