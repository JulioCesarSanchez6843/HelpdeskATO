from datetime import timedelta
from io import BytesIO
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from apps.accounts.decorators import admin_required, superadmin_required

from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import dateformat, timezone
from django.utils.dateparse import parse_date
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from apps.accounts.decorators import admin_required
from apps.accounts.models import Usuario
from apps.tickets.models import Ticket

DURACION_RESOLUCION = ExpressionWrapper(
    F("resuelto_en") - F("creado_en"), output_field=DurationField()
)
DURACION_PRIMERA_RESPUESTA = ExpressionWrapper(
    F("primera_respuesta_en") - F("creado_en"), output_field=DurationField()
)
FILTRO_CON_RESOLUCION = Q(resuelto_en__isnull=False)
FILTRO_CON_PRIMERA_RESPUESTA = Q(primera_respuesta_en__isnull=False)
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _horas(duracion):
    return round(duracion.total_seconds() / 3600, 1) if duracion else None


def _fecha_get(request, nombre):
    """Lee una fecha YYYY-MM-DD de la URL; si viene mal escrita, la ignora."""
    try:
        return parse_date(request.GET.get(nombre, "").strip())
    except ValueError:
        return None

def _tickets_alcance(request):
    tickets = Ticket.objects.all()
    if request.user.es_superadmin:
        return tickets
    return tickets.filter(sucursal_id=request.user.sucursal_id)

def _resumen_por(tickets, campo, sin_valor):
    """Agrupa los tickets por `campo` (ej. 'area__nombre') y calcula, por grupo:
    total, pendientes, cerrados, % cerrados y tiempo promedio de cierre."""
    filas = (
        tickets.order_by()
        .values(campo)
        .annotate(
            total=Count("id"),
            cerrados=Count("id", filter=Q(estado=Ticket.Estado.CERRADO)),
            promedio=Avg(DURACION_RESOLUCION, filter=FILTRO_CON_RESOLUCION),
            promedio_respuesta=Avg(
                DURACION_PRIMERA_RESPUESTA, filter=FILTRO_CON_PRIMERA_RESPUESTA
            ),
        )
        .order_by("-total", campo)
    )
    resultado = []
    for fila in filas:
        total, cerrados = fila["total"], fila["cerrados"]
        resultado.append({
            "nombre": fila[campo] or sin_valor,
            "total": total,
            "pendientes": total - cerrados,
            "cerrados": cerrados,
            "porcentaje": round(cerrados / total * 100) if total else 0,
            "horas": _horas(fila["promedio"]),
            "horas_respuesta": _horas(fila["promedio_respuesta"]),
        })
    return resultado


def _grafica_barras(filas):
    return {
        "labels": [f["nombre"] for f in filas],
        "pendientes": [f["pendientes"] for f in filas],
        "cerrados": [f["cerrados"] for f in filas],
    }

@admin_required
def reportes(request):
    desde = _fecha_get(request, "desde")
    hasta = _fecha_get(request, "hasta")

    base = _tickets_alcance(request)
    tickets = base
    if desde:
        tickets = tickets.filter(creado_en__date__gte=desde)
    if hasta:
        tickets = tickets.filter(creado_en__date__lte=hasta)

    total = tickets.count()
    abiertos = tickets.filter(estado=Ticket.Estado.ABIERTO).count()
    en_proceso = tickets.filter(estado=Ticket.Estado.EN_PROCESO).count()
    en_espera = tickets.filter(estado=Ticket.Estado.EN_ESPERA).count()
    por_confirmar = tickets.filter(estado=Ticket.Estado.POR_CONFIRMAR).count()
    cerrados = tickets.filter(estado=Ticket.Estado.CERRADO).count()

    tiempos = tickets.aggregate(
        resolucion=Avg(DURACION_RESOLUCION, filter=FILTRO_CON_RESOLUCION),
        respuesta=Avg(
            DURACION_PRIMERA_RESPUESTA, filter=FILTRO_CON_PRIMERA_RESPUESTA
        ),
    )
    tiempo_promedio_horas = _horas(tiempos["resolucion"])
    tiempo_respuesta_horas = _horas(tiempos["respuesta"])

    porcentaje_resueltos = round((cerrados / total) * 100) if total else 0

    hoy = timezone.localdate()
    dias = [hoy - timedelta(days=i) for i in range(6, -1, -1)]
    por_dia = dict(
        base.filter(creado_en__date__gte=dias[0])
        .annotate(dia=TruncDate("creado_en"))
        .order_by()
        .values_list("dia")
        .annotate(total=Count("id"))
    )

        
    primer_mes = hoy.replace(day=1)
    meses = []
    for _ in range(6):
        meses.append(primer_mes)
        primer_mes = (primer_mes - timedelta(days=1)).replace(day=1)
    meses.reverse()

    def _por_mes(campo):
        datos = (
            base.filter(**{f"{campo}__date__gte": meses[0]})
            .annotate(mes=TruncMonth(campo))
            .order_by()
            .values_list("mes")
            .annotate(total=Count("id"))
        )
        return {m.date() if hasattr(m, "date") else m: n for m, n in datos}

    creados_mes = _por_mes("creado_en")
    cerrados_mes = _por_mes("cerrado_en")

    por_categoria = _resumen_por(tickets, "categoria__nombre", "Sin categoría")
    por_area = _resumen_por(tickets, "area__nombre", "Sin área")
    por_sucursal = _resumen_por(tickets, "sucursal__nombre", "Sin sucursal")
    resueltos_por_persona = list(
        tickets.filter(
            resuelto_por__isnull=False,
            estado__in=[Ticket.Estado.POR_CONFIRMAR, Ticket.Estado.CERRADO],
        )
        .order_by()
        .values("resuelto_por__nombre", "resuelto_por__rol")
        .annotate(
            resueltos=Count("id"),
            cerrados=Count("id", filter=Q(estado=Ticket.Estado.CERRADO)),
        )
        .order_by("-resueltos", "resuelto_por__nombre")
    )
    for fila in resueltos_por_persona:
        fila["rol"] = Usuario.Rol(fila["resuelto_por__rol"]).label

    top_solicitantes = list(
        tickets.order_by()
        .values("creado_por__nombre", "creado_por__area__nombre")
        .annotate(total=Count("id"))
        .order_by("-total", "creado_por__nombre")[:5]
    )

    graficas = {
        "actividad": {
            "labels": [dateformat.format(d, "d-b") for d in dias],
            "data": [por_dia.get(d, 0) for d in dias],
        },
        "distribucion": {
            "labels": ["Abiertos", "En proceso", "Por confirmar", "Cerrados", "En espera"],
            "data": [abiertos, en_proceso, por_confirmar, cerrados, en_espera],
        },
        "categorias": _grafica_barras(por_categoria),
        "areas": _grafica_barras(por_area),
        "mensual": {
            "labels": [f"{MESES[m.month - 1]} {m.year}" for m in meses],
            "creados": [creados_mes.get(m, 0) for m in meses],
            "cerrados": [cerrados_mes.get(m, 0) for m in meses],
        },
    }

    return render(request, "dashboard/reportes.html", {
        "total": total,
        "abiertos": abiertos,
        "en_proceso": en_proceso,
        "en_espera": en_espera,
        "por_confirmar": por_confirmar,
        "cerrados": cerrados,
        "tiempo_promedio_horas": tiempo_promedio_horas,
        "tiempo_respuesta_horas": tiempo_respuesta_horas,
        "porcentaje_resueltos": porcentaje_resueltos,
        "graficas": graficas,
        "por_categoria": por_categoria,
        "por_area": por_area,
        "por_sucursal": por_sucursal,
        "resueltos_por_persona": resueltos_por_persona,
        "top_solicitantes": top_solicitantes,
        "desde": desde.isoformat() if desde else "",
        "hasta": hasta.isoformat() if hasta else "",
    })

def _local(fecha):
    """Excel no admite fechas con zona horaria: se pasa a hora local sin tzinfo."""
    return timezone.localtime(fecha).replace(tzinfo=None) if fecha else None


def _celda_segura(valor):
    """Quita caracteres que Excel no acepta."""
    if isinstance(valor, str):
        return ILLEGAL_CHARACTERS_RE.sub("", valor)
    return valor


def _escribir(hoja, fila, columna, valor, formato=None):
    celda = hoja.cell(row=fila, column=columna, value=_celda_segura(valor))
    if isinstance(valor, str):
        celda.data_type = "s"
        if valor[:1] in ("=", "+", "-", "@"):
            celda.quotePrefix = True
    if formato:
        celda.number_format = formato
    return celda


def _estilizar_encabezado(hoja, fila, columnas):
    relleno = PatternFill("solid", fgColor="1F4E78")
    for col in range(1, columnas + 1):
        celda = hoja.cell(row=fila, column=col)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = relleno
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

FORMATO_FECHA = "dd/mm/yyyy hh:mm"
ESTADOS_PENDIENTES = (
    Ticket.Estado.ABIERTO,
    Ticket.Estado.EN_PROCESO,
    Ticket.Estado.EN_ESPERA,
)


def _horas_entre(inicio, fin):
    if not inicio or not fin:
        return None
    return round((fin - inicio).total_seconds() / 3600, 1)


def _hoja_tabla(wb, titulo, encabezados, filas, anchos, fechas=(), envolver=()):
    hoja = wb.create_sheet(titulo)
    hoja.append(encabezados)
    _estilizar_encabezado(hoja, 1, len(encabezados))
    for numero, valores in enumerate(filas, start=2):
        for col, valor in enumerate(valores, start=1):
            celda = _escribir(
                hoja, numero, col, valor, FORMATO_FECHA if col in fechas else None
            )
            celda.alignment = Alignment(vertical="top", wrap_text=col in envolver)
    for i, ancho in enumerate(anchos, start=1):
        hoja.column_dimensions[get_column_letter(i)].width = ancho
    hoja.row_dimensions[1].height = 32
    hoja.freeze_panes = "A2"
    if hoja.max_row > 1:
        hoja.auto_filter.ref = hoja.dimensions
    return hoja


def _filas_resumen(grupos):
    return [
        [g["nombre"], g["total"], g["pendientes"], g["cerrados"],
         g["porcentaje"], g["horas"], g["horas_respuesta"]]
        for g in grupos
    ]


ENCABEZADOS_RESUMEN = [
    "Nombre", "Total", "Pendientes", "Cerrados", "% cerrados",
    "Horas promedio de resolución", "Horas promedio de primera respuesta",
]
ANCHOS_RESUMEN = [30, 10, 12, 10, 12, 20, 22]


def _agregar_hojas(wb, request, desde, hasta):
    ahora = timezone.now()
    base = _tickets_alcance(request)
    if desde:
        base = base.filter(creado_en__date__gte=desde)
    if hasta:
        base = base.filter(creado_en__date__lte=hasta)
    detalle = base.select_related(
        "area", "categoria", "sucursal", "creado_por", "asignado_a", "resuelto_por"
    )

    sin_resolver = detalle.filter(estado__in=ESTADOS_PENDIENTES).order_by(
        "sla_vence_en", "creado_en"
    )
    filas = [
        [
            t.pk, t.titulo, t.get_estado_display(),
            t.get_prioridad_display() or "Sin definir",
            t.categoria.nombre if t.categoria else "Sin categoría",
            t.area.nombre if t.area else "Sin área",
            t.sucursal.nombre if t.sucursal else "Sin sucursal",
            t.creado_por.nombre,
            t.asignado_a.nombre if t.asignado_a else "Sin asignar",
            _local(t.creado_en),
            round((ahora - t.creado_en).total_seconds() / 86400, 1),
            _local(t.sla_vence_en), t.estado_sla,
            "Sí" if t.escalado_en else "No",
        ]
        for t in sin_resolver
    ]
    _hoja_tabla(
        wb, "Sin resolver",
        ["ID", "Título", "Estado", "Prioridad", "Categoría", "Área", "Sucursal",
         "Solicitante", "Asignado a", "Fecha de creación", "Días abierto",
         "SLA vence", "Estado del SLA", "Escalado"],
        filas, [8, 34, 20, 12, 18, 20, 18, 24, 24, 18, 12, 18, 14, 10],
        fechas=(10, 12), envolver=(2,),
    )

    por_confirmar = detalle.filter(estado=Ticket.Estado.POR_CONFIRMAR).order_by(
        "resuelto_en"
    )
    filas = [
        [
            t.pk, t.titulo, t.creado_por.nombre, t.creado_por.correo,
            t.resuelto_por.nombre if t.resuelto_por else "",
            _local(t.resuelto_en),
            round((ahora - t.resuelto_en).total_seconds() / 86400, 1)
            if t.resuelto_en else None,
            "Sí" if t.recordatorio_cierre_en else "No",
            t.nota_resolucion,
        ]
        for t in por_confirmar
    ]
    _hoja_tabla(
        wb, "Por confirmar",
        ["ID", "Título", "Solicitante", "Correo del solicitante", "Resuelto por",
         "Fecha de resolución", "Días esperando confirmación",
         "Recordatorio enviado", "Nota de resolución"],
        filas, [8, 34, 24, 28, 22, 18, 16, 14, 50],
        fechas=(6,), envolver=(2, 9),
    )

    con_sla = list(detalle.filter(sla_vence_en__isnull=False).order_by("sla_vence_en"))
    filas = []
    for t in con_sla:
        fin = t.resuelto_en or ahora
        retraso = _horas_entre(t.sla_vence_en, fin)
        filas.append([
            t.pk, t.titulo, t.get_prioridad_display(), t.get_estado_display(),
            t.asignado_a.nombre if t.asignado_a else "Sin asignar",
            _local(t.prioridad_en), _local(t.sla_vence_en), _local(t.resuelto_en),
            t.estado_sla, max(retraso, 0) if retraso is not None else 0,
        ])
    _hoja_tabla(
        wb, "SLA",
        ["ID", "Título", "Prioridad", "Estado", "Asignado a",
         "Prioridad definida el", "SLA vence", "Fecha de resolución",
         "Estado del SLA", "Horas de retraso"],
        filas, [8, 34, 12, 20, 24, 18, 18, 18, 14, 14],
        fechas=(6, 7, 8), envolver=(2,),
    )

    _hoja_tabla(
        wb, "Por categoría", ENCABEZADOS_RESUMEN,
        _filas_resumen(_resumen_por(base, "categoria__nombre", "Sin categoría")),
        ANCHOS_RESUMEN,
    )
    _hoja_tabla(
        wb, "Por área", ENCABEZADOS_RESUMEN,
        _filas_resumen(_resumen_por(base, "area__nombre", "Sin área")),
        ANCHOS_RESUMEN,
    )
    if request.user.es_superadmin:
        _hoja_tabla(
            wb, "Por sucursal", ENCABEZADOS_RESUMEN,
            _filas_resumen(_resumen_por(base, "sucursal__nombre", "Sin sucursal")),
            ANCHOS_RESUMEN,
        )

    personas = {}
    resueltos = (
        base.filter(
            resuelto_por__isnull=False,
            estado__in=[Ticket.Estado.POR_CONFIRMAR, Ticket.Estado.CERRADO],
        )
        .order_by()
        .values("resuelto_por", "resuelto_por__nombre")
        .annotate(
            resueltos=Count("id"),
            cerrados=Count("id", filter=Q(estado=Ticket.Estado.CERRADO)),
            promedio=Avg(DURACION_RESOLUCION, filter=FILTRO_CON_RESOLUCION),
        )
    )
    for fila in resueltos:
        personas[fila["resuelto_por"]] = {
            "nombre": fila["resuelto_por__nombre"],
            "resueltos": fila["resueltos"],
            "cerrados": fila["cerrados"],
            "horas": _horas(fila["promedio"]),
            "pendientes": 0,
        }
    pendientes = (
        base.filter(estado__in=ESTADOS_PENDIENTES, asignado_a__isnull=False)
        .order_by()
        .values("asignado_a", "asignado_a__nombre")
        .annotate(total=Count("id"))
    )
    for fila in pendientes:
        dato = personas.setdefault(
            fila["asignado_a"],
            {"nombre": fila["asignado_a__nombre"], "resueltos": 0,
             "cerrados": 0, "horas": None, "pendientes": 0},
        )
        dato["pendientes"] = fila["total"]
    ordenadas = sorted(
        personas.values(),
        key=lambda d: (-d["resueltos"], -d["pendientes"], d["nombre"]),
    )
    _hoja_tabla(
        wb, "Por persona",
        ["Persona", "Tickets resueltos", "De ellos, cerrados",
         "Pendientes asignados", "Horas promedio de resolución"],
        [[d["nombre"], d["resueltos"], d["cerrados"], d["pendientes"], d["horas"]]
         for d in ordenadas],
        [30, 16, 18, 20, 22],
    )

    por_estado = dict(
        base.order_by().values_list("estado").annotate(total=Count("id"))
    )
    tiempos = base.aggregate(
        resolucion=Avg(DURACION_RESOLUCION, filter=FILTRO_CON_RESOLUCION),
        respuesta=Avg(
            DURACION_PRIMERA_RESPUESTA, filter=FILTRO_CON_PRIMERA_RESPUESTA
        ),
    )
    estados_sla = [t.estado_sla for t in con_sla]
    cumplidos = estados_sla.count("Cumplido")
    incumplidos = estados_sla.count("Incumplido")
    resumen = wb.create_sheet("Resumen general")
    resumen.append(["Resumen general de tickets"])
    resumen["A1"].font = Font(bold=True, size=14)
    resumen.append(["Generado", _local(ahora)])
    resumen.cell(row=2, column=2).number_format = FORMATO_FECHA
    resumen.append(["Creados desde", desde.isoformat() if desde else "Sin límite"])
    resumen.append(["Creados hasta", hasta.isoformat() if hasta else "Sin límite"])
    resumen.append(["Total de tickets", sum(por_estado.values())])
    resumen.append([])
    resumen.append(["Por estado", "Tickets"])
    _estilizar_encabezado(resumen, resumen.max_row, 2)
    for valor, etiqueta in Ticket.Estado.choices:
        resumen.append([etiqueta, por_estado.get(valor, 0)])
    resumen.append([])
    resumen.append(["Tiempos", "Horas"])
    _estilizar_encabezado(resumen, resumen.max_row, 2)
    resumen.append(["Promedio de primera respuesta", _horas(tiempos["respuesta"]) or "—"])
    resumen.append(["Promedio de resolución", _horas(tiempos["resolucion"]) or "—"])
    resumen.append([])
    resumen.append(["SLA", "Tickets"])
    _estilizar_encabezado(resumen, resumen.max_row, 2)
    for etiqueta in ("En tiempo", "Por vencer", "Vencido", "Cumplido", "Incumplido"):
        resumen.append([etiqueta, estados_sla.count(etiqueta)])
    resumen.append([
        "Cumplimiento (resueltos a tiempo)",
        f"{round(cumplidos / (cumplidos + incumplidos) * 100)} %"
        if (cumplidos + incumplidos) else "—",
    ])
    resumen.column_dimensions["A"].width = 38
    resumen.column_dimensions["B"].width = 22
    wb.move_sheet(resumen, offset=-(len(wb.sheetnames) - 1))

@admin_required
def exportar_resueltos(request):
    """Descarga en Excel los tickets resueltos (cerrados) con todos sus datos.
    Se puede acotar por fecha de cierre con ?desde=AAAA-MM-DD&hasta=AAAA-MM-DD."""
    desde = _fecha_get(request, "desde")
    hasta = _fecha_get(request, "hasta")

    tickets = (
        _tickets_alcance(request).filter(estado=Ticket.Estado.CERRADO)
        .select_related(
            "area", "categoria", "creado_por", "creado_por__area",
            "creado_por__puesto", "resuelto_por",
        )
        .annotate(num_adjuntos=Count("adjuntos"))
        .order_by("-cerrado_en", "-id")
    )
    if desde:
        tickets = tickets.filter(cerrado_en__date__gte=desde)
    if hasta:
        tickets = tickets.filter(cerrado_en__date__lte=hasta)

    wb = Workbook()
    hoja = wb.active
    hoja.title = "Tickets resueltos"

    encabezados = [
        "ID", "Título", "Descripción", "Nº de serie / Service Tag",
        "Área (departamento)", "Categoría", "Estado",
        "Solicitante", "Correo del solicitante", "Área del solicitante", "Puesto del solicitante",
        "Fecha de creación", "Fecha de resolución", "Fecha de cierre",
        "Horas hasta resolver", "Horas hasta el cierre",
        "Resuelto por", "Forma de cierre", "Nota de resolución", "Adjuntos",
    ]
    hoja.append(encabezados)
    _estilizar_encabezado(hoja, 1, len(encabezados))

    formato_fecha = "dd/mm/yyyy hh:mm"
    resumen_area, resumen_categoria = {}, {}
    suma_horas, con_horas = 0.0, 0

    for fila, t in enumerate(tickets, start=2):
        horas_resolver = (
            round((t.resuelto_en - t.creado_en).total_seconds() / 3600, 1)
            if t.resuelto_en else None
        )
        horas_cierre = (
            round((t.cerrado_en - t.creado_en).total_seconds() / 3600, 1)
            if t.cerrado_en else None
        )
        if horas_resolver is not None:
            suma_horas += horas_resolver
            con_horas += 1

        if t.justificacion_cierre:
            forma_cierre = "Cerrado por el administrador"
        else:
            forma_cierre = "Confirmado por el usuario"

        solicitante = t.creado_por
        valores = [
            t.pk, t.titulo, t.descripcion, t.numero_serie,
            t.area.nombre if t.area else "Sin área",
            t.categoria.nombre if t.categoria else "Sin categoría",
            t.get_estado_display(),
            solicitante.nombre, solicitante.correo,
            solicitante.area.nombre if solicitante.area else "",
            solicitante.puesto.nombre if solicitante.puesto else "",
            _local(t.creado_en), _local(t.resuelto_en), _local(t.cerrado_en),
            horas_resolver, horas_cierre,
            t.resuelto_por.nombre if t.resuelto_por else "", forma_cierre,
            t.nota_resolucion, t.num_adjuntos,
        ]

        for col, valor in enumerate(valores, start=1):
            formato = formato_fecha if col in (12, 13, 14) else None
            celda = _escribir(hoja, fila, col, valor, formato)
            if col in (2, 3, 19):
                celda.alignment = Alignment(wrap_text=True, vertical="top")
            else:
                celda.alignment = Alignment(vertical="top")

        resumen_area[valores[4]] = resumen_area.get(valores[4], 0) + 1
        resumen_categoria[valores[5]] = resumen_categoria.get(valores[5], 0) + 1

    anchos = [8, 32, 50, 22, 20, 18, 12, 24, 28, 20, 20, 18, 18, 18, 12, 12, 22, 28, 50, 10]
    for i, ancho in enumerate(anchos, start=1):
        hoja.column_dimensions[get_column_letter(i)].width = ancho
    hoja.row_dimensions[1].height = 32
    hoja.freeze_panes = "C2"
    hoja.auto_filter.ref = hoja.dimensions

    _agregar_hojas(wb, request, desde, hasta)

    resumen = wb.create_sheet("Resumen resueltos")
    total = sum(resumen_area.values())
    resumen.append(["Resumen de tickets resueltos"])
    resumen["A1"].font = Font(bold=True, size=14)
    resumen.append(["Generado", _local(timezone.now())])
    resumen.cell(row=2, column=2).number_format = formato_fecha
    resumen.append(["Cierre desde", desde.isoformat() if desde else "Sin límite"])
    resumen.append(["Cierre hasta", hasta.isoformat() if hasta else "Sin límite"])
    resumen.append(["Total de tickets", total])
    resumen.append([
        "Horas promedio hasta resolver",
        round(suma_horas / con_horas, 1) if con_horas else "—",
    ])
    for titulo, datos in (
        ("Por área (departamento)", resumen_area),
        ("Por categoría", resumen_categoria),
    ):
        resumen.append([])
        resumen.append([titulo, "Tickets"])
        _estilizar_encabezado(resumen, resumen.max_row, 2)
        for nombre, cantidad in sorted(datos.items(), key=lambda x: (-x[1], x[0])):
            resumen.append([_celda_segura(nombre), cantidad])
    resumen.column_dimensions["A"].width = 34
    resumen.column_dimensions["B"].width = 22

    salida = BytesIO()
    wb.save(salida)

    nombre = f"reporte_tickets_{timezone.localdate().isoformat()}.xlsx"
    respuesta = HttpResponse(
        salida.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return respuesta