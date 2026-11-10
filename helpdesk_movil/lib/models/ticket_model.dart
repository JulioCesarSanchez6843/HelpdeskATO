class Ticket {
  final int id;
  final String titulo;
  final String descripcion;
  final String numeroSerie;
  final String estado;
  final String prioridad;
  final String? creadoEn;
  final String? slaVenceEn;

  Ticket({
    required this.id,
    required this.titulo,
    required this.descripcion,
    required this.numeroSerie,
    required this.estado,
    required this.prioridad,
    this.creadoEn,
    this.slaVenceEn,
  });

  // Fábrica para convertir el JSON que nos mande la API de Django en un objeto Ticket
  factory Ticket.fromJson(Map<String, dynamic> json) {
    return Ticket(
      id: json['id'],
      titulo: json['titulo'] ?? '',
      descripcion: json['descripcion'] ?? '',
      numeroSerie: json['numero_serie'] ?? '',
      estado: json['estado'] ?? 'ABIERTO',
      prioridad: json['prioridad'] ?? 'MEDIA',
      creadoEn: json['creado_en'],
      slaVenceEn: json['sla_vence_en'],
    );
  }

  // Método opcional para convertirlo de regreso a JSON (por si creamos o editamos tickets desde la app)
  Map<String, dynamic> toJson() {
    return {
      'titulo': titulo,
      'descripcion': descripcion,
      'numero_serie': numeroSerie,
      'prioridad': prioridad,
    };
  }
}
