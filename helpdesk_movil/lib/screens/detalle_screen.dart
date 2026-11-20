import 'package:flutter/material.dart';

import '../api_service.dart';
import '../config.dart';
import '../models/ticket.dart';
import '../util.dart';
import 'gestion_sheet.dart';
import 'login_screen.dart';

class DetalleScreen extends StatefulWidget {
  final int ticketId;
  const DetalleScreen({super.key, required this.ticketId});

  @override
  State<DetalleScreen> createState() => _DetalleScreenState();
}

class _DetalleScreenState extends State<DetalleScreen> {
  TicketDetalle? _d;
  String? _error;
  bool _cargando = true;
  bool _enviando = false;
  bool _esPersonal = false;
  bool _interno = false;
  final _comentario = TextEditingController();

  @override
  void initState() {
    super.initState();
    _cargar();
  }

  @override
  void dispose() {
    _comentario.dispose();
    super.dispose();
  }

  void _aviso(String m, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(m), backgroundColor: error ? Colors.red.shade700 : null),
    );
  }

  void _irALogin() {
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (route) => false,
    );
  }

  Future<void> _cargar() async {
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      final rol = await ApiService.rol();
      final d = await ApiService.detalle(widget.ticketId);
      if (!mounted) return;
      setState(() {
        _d = d;
        _esPersonal = const ['SUPERADMIN', 'ENCARGADO', 'BECARIO'].contains(rol);
      });
    } on ApiException catch (e) {
      if (e.codigo == 401) {
        _irALogin();
      } else if (_d != null) {
        _aviso(e.mensaje, error: true);
      } else if (mounted) {
        setState(() => _error = e.mensaje);
      }
    } finally {
      if (mounted) setState(() => _cargando = false);
    }
  }

  Future<bool> _accion(Future<TicketDetalle> Function() f, {String? ok}) async {
    setState(() => _enviando = true);
    try {
      final d = await f();
      if (!mounted) return true;
      setState(() => _d = d);
      if (ok != null) _aviso(ok);
      return true;
    } on ApiException catch (e) {
      if (e.codigo == 401) {
        _irALogin();
      } else {
        _aviso(e.mensaje, error: true);
      }
      return false;
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  Future<void> _comentar() async {
    final texto = _comentario.text.trim();
    if (texto.length < 2) {
      _aviso('Escribe un mensaje.', error: true);
      return;
    }
    final exito = await _accion(
      () => ApiService.comentar(widget.ticketId, texto,
          interno: _esPersonal && _interno),
      ok: 'Mensaje enviado.',
    );
    if (exito && mounted) {
      _comentario.clear();
      FocusScope.of(context).unfocus();
    }
  }

  Future<void> _tomar() async {
    await _accion(() => ApiService.tomar(widget.ticketId), ok: 'Tomaste el ticket.');
  }

  Future<void> _asignar() async {
    final d = _d;
    if (d == null) return;
    final r = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _AsignarSheet(
        ticketId: widget.ticketId,
        asignadoActual: d.ticket.asignadoAId,
        prioridadActual: d.ticket.prioridadValor,
      ),
    );
    if (r == null) return;
    await _accion(
      () => ApiService.asignar(widget.ticketId,
          asignadoA: r['asignado_a'] as int?, prioridad: r['prioridad'] as String),
      ok: 'Ticket actualizado.',
    );
  }

  Future<String?> _pedirTexto({
    required String titulo,
    required String etiqueta,
    required String boton,
    int minimo = 0,
  }) async {
    final ctrl = TextEditingController();
    String? error;
    final r = await showDialog<String>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setD) => AlertDialog(
          title: Text(titulo),
          content: TextField(
            controller: ctrl,
            autofocus: true,
            minLines: 2,
            maxLines: 5,
            maxLength: 1000,
            textCapitalization: TextCapitalization.sentences,
            decoration: InputDecoration(
              labelText: etiqueta,
              errorText: error,
              border: const OutlineInputBorder(),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancelar'),
            ),
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: Config.rojo),
              onPressed: () {
                final v = ctrl.text.trim();
                if (v.length < minimo) {
                  setD(() => error = 'Escribe al menos $minimo caracteres.');
                  return;
                }
                Navigator.pop(ctx, v);
              },
              child: Text(boton),
            ),
          ],
        ),
      ),
    );
    ctrl.dispose();
    return r;
  }

  Future<void> _confirmarCierre() async {
    await _accion(
      () => ApiService.responderCierre(widget.ticketId, 'confirmar'),
      ok: 'Gracias, el ticket quedó cerrado.',
    );
  }

  Future<void> _rechazarCierre() async {
    final motivo = await _pedirTexto(
      titulo: 'El problema no se resolvió',
      etiqueta: 'Cuéntanos qué sigue fallando (opcional)',
      boton: 'Enviar',
    );
    if (motivo == null) return;
    await _accion(
      () => ApiService.responderCierre(widget.ticketId, 'rechazar', motivo: motivo),
      ok: 'Listo, el ticket volvió a «En proceso».',
    );
  }

  Future<void> _reabrir() async {
    final motivo = await _pedirTexto(
      titulo: 'Reabrir ticket',
      etiqueta: 'Motivo de la reapertura',
      boton: 'Reabrir',
      minimo: 5,
    );
    if (motivo == null) return;
    await _accion(
      () => ApiService.reabrir(widget.ticketId, motivo),
      ok: 'Ticket reabierto.',
    );
  }

  Widget _bannerCierre() => Card(
        margin: const EdgeInsets.only(top: 10),
        color: Colors.teal.withValues(alpha: 0.12),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('¿Se resolvió tu problema?',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              const Text(
                  'El equipo de soporte marcó este ticket como resuelto. '
                  'Confírmalo para cerrarlo o avísanos si sigue fallando.'),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  FilledButton.icon(
                    onPressed: _enviando ? null : _confirmarCierre,
                    icon: const Icon(Icons.check_circle_outline),
                    label: const Text('Sí, se resolvió'),
                    style: FilledButton.styleFrom(backgroundColor: Colors.teal),
                  ),
                  OutlinedButton.icon(
                    onPressed: _enviando ? null : _rechazarCierre,
                    icon: const Icon(Icons.replay),
                    label: const Text('No se resolvió'),
                  ),
                ],
              ),
            ],
          ),
        ),
      );

  bool _puedeGestionar(TicketDetalle d) =>
      _esPersonal && d.ticket.estado != 'CERRADO';

  Future<void> _gestionar() async {
    final r = await showModalBottomSheet<TicketDetalle>(
      context: context,
      isScrollControlled: true,
      builder: (_) => GestionSheet(ticketId: widget.ticketId),
    );
    if (r == null || !mounted) return;
    setState(() => _d = r);
    _aviso(r.ticket.estado == 'POR_CONFIRMAR'
        ? 'Ticket marcado como resuelto. Se le pidió al usuario que confirme el cierre.'
        : 'Ticket actualizado.');
  }

  Widget _chip(String texto, Color color) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(texto,
            style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
      );

  Widget _fila(String k, String v, {Color? color}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
                width: 110,
                child: Text(k, style: const TextStyle(color: Colors.black54))),
            Expanded(child: Text(v, style: TextStyle(color: color))),
          ],
        ),
      );

  Widget _burbuja(Comentario c) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: c.interno ? Colors.amber.withValues(alpha: 0.18) : Colors.white,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.black12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                  child: Text(c.autor,
                      style: const TextStyle(fontWeight: FontWeight.w700))),
              if (c.interno)
                const Padding(
                  padding: EdgeInsets.only(right: 8),
                  child: Text('Nota interna',
                      style: TextStyle(
                          fontSize: 11,
                          color: Colors.orange,
                          fontWeight: FontWeight.w700)),
                ),
              Text(fechaHora(c.creadoEn),
                  style: const TextStyle(fontSize: 11, color: Colors.black54)),
            ],
          ),
          const SizedBox(height: 6),
          Text(c.contenido),
        ],
      ),
    );
  }

  Widget _barraComentario() {
    return Material(
      elevation: 8,
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 8, 8),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (_esPersonal)
                Row(
                  children: [
                    Switch(
                        value: _interno,
                        onChanged: (v) => setState(() => _interno = v)),
                    const Text('Nota interna (el usuario no la ve)',
                        style: TextStyle(fontSize: 12)),
                  ],
                ),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _comentario,
                      minLines: 1,
                      maxLines: 4,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: const InputDecoration(
                        hintText: 'Escribe un mensaje…',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                  ),
                  IconButton(
                    onPressed: _enviando ? null : _comentar,
                    icon: const Icon(Icons.send),
                    color: Config.rojo,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _contenido(TicketDetalle d) {
    final t = d.ticket;
    final p = d.permisos;
    return [
      if (_enviando) const LinearProgressIndicator(),
      Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(t.titulo,
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 4,
                children: [
                  _chip(t.estadoDisplay, colorEstado(t.estado)),
                  if (t.prioridad != null)
                    _chip('Prioridad ${t.prioridad}', Colors.blueGrey),
                  if (d.slaVencido) _chip('SLA vencido', Colors.red),
                ],
              ),
              const SizedBox(height: 10),
              _fila('Solicitante', t.creadoPor),
              if (t.sucursal != null) _fila('Sucursal', t.sucursal!),
              if (d.area != null) _fila('Área', d.area!),
              _fila('Asignado a', t.asignadoA ?? 'Sin asignar'),
              _fila('Creado', fechaHora(t.creadoEn)),
              if (d.slaVenceEn != null)
                _fila('SLA vence', fechaHora(d.slaVenceEn!),
                    color: d.slaVencido ? Colors.red : null),
              if (d.numeroSerie != null) _fila('No. de serie', d.numeroSerie!),
              const Divider(height: 24),
              Text(d.descripcion),
              if (d.adjuntos > 0) ...[
                const SizedBox(height: 10),
                Row(
                  children: [
                    const Icon(Icons.image_outlined, size: 18),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        '${d.adjuntos} imagen(es) adjunta(s) · se ven en la versión web',
                        style: const TextStyle(fontSize: 12, color: Colors.black54),
                      ),
                    ),
                  ],
                ),
              ],
              if (d.notaResolucion != null) ...[
                const Divider(height: 24),
                const Text('Nota de resolución',
                    style: TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text(d.notaResolucion!),
              ],
            ],
          ),
        ),
      ),
      if (p.puedeResponderCierre) _bannerCierre(),
      if (p.puedeTomar || p.puedeAsignar || p.puedeReabrir || _puedeGestionar(d)) ...[
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            if (p.puedeTomar)
              FilledButton.icon(
                onPressed: _enviando ? null : _tomar,
                icon: const Icon(Icons.assignment_ind),
                label: const Text('Tomar ticket'),
                style: FilledButton.styleFrom(backgroundColor: Config.rojo),
              ),
            if (p.puedeReabrir)
              OutlinedButton.icon(
                onPressed: _enviando ? null : _reabrir,
                icon: const Icon(Icons.lock_open),
                label: const Text('Reabrir ticket'),
              ),
            if (_puedeGestionar(d))
              OutlinedButton.icon(
                onPressed: _enviando ? null : _gestionar,
                icon: const Icon(Icons.edit_note),
                label: const Text('Actualizar ticket'),
              ),
            if (p.puedeAsignar)
              OutlinedButton.icon(
                onPressed: _enviando ? null : _asignar,
                icon: const Icon(Icons.person_add),
                label: const Text('Asignar / prioridad'),
              ),
          ],
        ),
      ],
      const SizedBox(height: 16),
      Text('Conversación (${d.comentarios.length})',
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
      const SizedBox(height: 8),
      if (d.comentarios.isEmpty)
        const Text('Aún no hay mensajes.', style: TextStyle(color: Colors.black54)),
      for (final c in d.comentarios) _burbuja(c),
      const SizedBox(height: 8),
      Card(
        margin: EdgeInsets.zero,
        child: ExpansionTile(
          title: Text('Historial (${d.historial.length})'),
          children: [
            for (final h in d.historial)
              ListTile(
                dense: true,
                title: Text(h.contenido),
                subtitle: Text('${h.tipoDisplay} · ${h.usuario} · ${fechaHora(h.fecha)}'),
              ),
          ],
        ),
      ),
      const SizedBox(height: 24),
    ];
  }

  Widget _vacio() {
    if (_cargando) return const Center(child: CircularProgressIndicator());
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(_error ?? 'No se pudo cargar el ticket.', textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton(onPressed: _cargar, child: const Text('Reintentar')),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Config.oscuro,
        foregroundColor: Colors.white,
        title: Text('Ticket #${widget.ticketId}'),
        actions: [
          IconButton(
            tooltip: 'Actualizar',
            icon: const Icon(Icons.refresh),
            onPressed: _cargando ? null : _cargar,
          ),
        ],
      ),
      body: d == null
          ? _vacio()
          : Column(
              children: [
                Expanded(
                  child: RefreshIndicator(
                    onRefresh: _cargar,
                    child: ListView(
                      physics: const AlwaysScrollableScrollPhysics(),
                      padding: const EdgeInsets.all(12),
                      children: _contenido(d),
                    ),
                  ),
                ),
                if (d.permisos.puedeComentar) _barraComentario(),
              ],
            ),
    );
  }
}

class _AsignarSheet extends StatefulWidget {
  final int ticketId;
  final int? asignadoActual;
  final String? prioridadActual;
  const _AsignarSheet({
    required this.ticketId,
    this.asignadoActual,
    this.prioridadActual,
  });

  @override
  State<_AsignarSheet> createState() => _AsignarSheetState();
}

class _AsignarSheetState extends State<_AsignarSheet> {
  Opciones? _op;
  String? _error;
  int? _asignado;
  String? _prioridad;

  @override
  void initState() {
    super.initState();
    _asignado = widget.asignadoActual;
    _prioridad = widget.prioridadActual;
    _cargar();
  }

  Future<void> _cargar() async {
    try {
      final op = await ApiService.opciones(widget.ticketId);
      if (mounted) setState(() => _op = op);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.mensaje);
    }
  }

  Widget _opcion(String texto, bool marcada, VoidCallback onTap) => ListTile(
        dense: true,
        contentPadding: EdgeInsets.zero,
        title: Text(texto),
        trailing: marcada ? const Icon(Icons.check, color: Config.rojo) : null,
        onTap: onTap,
      );

  @override
  Widget build(BuildContext context) {
    final op = _op;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: _error != null
            ? Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(_error!, textAlign: TextAlign.center),
                  const SizedBox(height: 12),
                  FilledButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Cerrar'),
                  ),
                ],
              )
            : op == null
                ? const SizedBox(
                    height: 120, child: Center(child: CircularProgressIndicator()))
                : SingleChildScrollView(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Asignar ticket',
                            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
                        const SizedBox(height: 12),
                        const Text('Prioridad (SLA)',
                            style: TextStyle(fontWeight: FontWeight.w600)),
                        const SizedBox(height: 4),
                        Wrap(
                          spacing: 8,
                          children: [
                            for (final p in op.prioridades)
                              ChoiceChip(
                                label: Text(p.etiqueta),
                                selected: _prioridad == p.valor,
                                onSelected: (_) => setState(() => _prioridad = p.valor),
                              ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        const Text('Asignar a',
                            style: TextStyle(fontWeight: FontWeight.w600)),
                        _opcion('Sin asignar', _asignado == null,
                            () => setState(() => _asignado = null)),
                        for (final a in op.asignables)
                          _opcion(a.etiqueta, _asignado == a.id,
                              () => setState(() => _asignado = a.id)),
                        const SizedBox(height: 12),
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton(
                            onPressed: _prioridad == null
                                ? null
                                : () => Navigator.pop(context, {
                                      'asignado_a': _asignado,
                                      'prioridad': _prioridad,
                                    }),
                            style: FilledButton.styleFrom(
                              backgroundColor: Config.rojo,
                              padding: const EdgeInsets.symmetric(vertical: 14),
                            ),
                            child: const Text('Guardar'),
                          ),
                        ),
                      ],
                    ),
                  ),
      ),
    );
  }
}
