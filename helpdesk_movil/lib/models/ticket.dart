String? _opc(dynamic v) {
  final s = v as String?;
  return (s == null || s.isEmpty) ? null : s;
}

class Ticket {
  final int id;
  final String titulo;
  final String estado;
  final String estadoDisplay;
  final String? prioridadValor;
  final String? prioridad;
  final String? sucursal;
  final String creadoPor;
  final String? asignadoA;
  final int? asignadoAId;
  final DateTime creadoEn;

  Ticket.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        titulo = j['titulo'] as String,
        estado = j['estado'] as String,
        estadoDisplay = j['estado_display'] as String,
        prioridadValor = _opc(j['prioridad']),
        prioridad = _opc(j['prioridad_display']),
        sucursal = _opc(j['sucursal']),
        creadoPor = j['creado_por'] as String,
        asignadoA = _opc(j['asignado_a']),
        asignadoAId = j['asignado_a_id'] as int?,
        creadoEn = DateTime.parse(j['creado_en'] as String).toLocal();
}

class Comentario {
  final int id;
  final String autor;
  final String contenido;
  final bool interno;
  final DateTime creadoEn;

  Comentario.fromJson(Map<String, dynamic> j)
      : id = j['id'] as int,
        autor = j['autor'] as String,
        contenido = j['contenido'] as String,
        interno = j['interno'] as bool? ?? false,
        creadoEn = DateTime.parse(j['creado_en'] as String).toLocal();
}

class EventoHistorial {
  final String tipoDisplay;
  final String usuario;
  final String contenido;
  final DateTime fecha;

  EventoHistorial.fromJson(Map<String, dynamic> j)
      : tipoDisplay = j['tipo_display'] as String? ?? '',
        usuario = j['usuario'] as String? ?? '',
        contenido = j['contenido'] as String? ?? '',
        fecha = DateTime.parse(j['fecha'] as String).toLocal();
}

class Permisos {
  final bool puedeComentar;
  final bool puedeTomar;
  final bool puedeAsignar;
  final bool puedeReabrir;
  final bool puedeResponderCierre;

  Permisos.fromJson(Map<String, dynamic> j)
      : puedeComentar = j['puede_comentar'] as bool? ?? false,
        puedeTomar = j['puede_tomar'] as bool? ?? false,
        puedeAsignar = j['puede_asignar'] as bool? ?? false,
        puedeReabrir = j['puede_reabrir'] as bool? ?? false,
        puedeResponderCierre = j['puede_responder_cierre'] as bool? ?? false;
}

class TicketDetalle {
  final Ticket ticket;
  final String descripcion;
  final String? area;
  final String? numeroSerie;
  final String? notaResolucion;
  final DateTime? slaVenceEn;
  final bool slaVencido;
  final int adjuntos;
  final List<int> adjuntosIds;
  final List<Comentario> comentarios;
  final List<EventoHistorial> historial;
  final Permisos permisos;

  TicketDetalle.fromJson(Map<String, dynamic> j)
      : ticket = Ticket.fromJson(j),
        descripcion = j['descripcion'] as String? ?? '',
        area = _opc(j['area']),
        numeroSerie = _opc(j['numero_serie']),
        notaResolucion = _opc(j['nota_resolucion']),
        slaVenceEn = j['sla_vence_en'] == null
            ? null
            : DateTime.parse(j['sla_vence_en'] as String).toLocal(),
        slaVencido = j['sla_vencido'] as bool? ?? false,
        adjuntos = (j['adjuntos'] as List? ?? const []).length,
        adjuntosIds = (j['adjuntos'] as List? ?? const [])
            .map((e) => (e as Map<String, dynamic>)['id'] as int)
            .toList(),
        comentarios = (j['comentarios'] as List? ?? const [])
            .map((e) => Comentario.fromJson(e as Map<String, dynamic>))
            .toList(),
        historial = (j['historial'] as List? ?? const [])
            .map((e) => EventoHistorial.fromJson(e as Map<String, dynamic>))
            .toList(),
        permisos = Permisos.fromJson(
            (j['permisos'] as Map<String, dynamic>?) ?? <String, dynamic>{});
}

class Asignable {
  final int id;
  final String etiqueta;
  Asignable(this.id, this.etiqueta);
}

class Prioridad {
  final String valor;
  final String etiqueta;
  Prioridad(this.valor, this.etiqueta);
}

class Opciones {
  final List<Asignable> asignables;
  final List<Prioridad> prioridades;

  Opciones.fromJson(Map<String, dynamic> j)
      : asignables = (j['asignables'] as List).map((e) {
          final m = e as Map<String, dynamic>;
          return Asignable(m['id'] as int, '${m['nombre']} (${m['rol']})');
        }).toList(),
        prioridades = (j['prioridades'] as List).map((e) {
          final m = e as Map<String, dynamic>;
          return Prioridad(m['valor'] as String, m['etiqueta'] as String);
        }).toList();
}