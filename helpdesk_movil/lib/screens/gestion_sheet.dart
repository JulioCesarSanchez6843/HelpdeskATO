import 'package:flutter/material.dart';

import '../api_service.dart';
import '../config.dart';

class GestionSheet extends StatefulWidget {
  final int ticketId;
  const GestionSheet({super.key, required this.ticketId});

  @override
  State<GestionSheet> createState() => _GestionSheetState();
}

class _GestionSheetState extends State<GestionSheet> {
  Map<String, dynamic>? _op;
  String? _errorCarga;
  String? _error;
  bool _guardando = false;

  String? _estado;
  String _estadoOriginal = '';
  String? _prioridad;
  int? _categoria;
  final _serie = TextEditingController();
  final _nota = TextEditingController();
  final _motivo = TextEditingController();

  @override
  void initState() {
    super.initState();
    _cargar();
  }

  @override
  void dispose() {
    _serie.dispose();
    _nota.dispose();
    _motivo.dispose();
    super.dispose();
  }

  Future<void> _cargar() async {
    try {
      final op = await ApiService.gestionOpciones(widget.ticketId);
      final v = op['valores'] as Map<String, dynamic>;
      if (!mounted) return;
      setState(() {
        _op = op;
        _estado = v['estado'] as String?;
        _estadoOriginal = _estado ?? '';
        final p = v['prioridad'] as String?;
        _prioridad = (p == null || p.isEmpty) ? null : p;
        _categoria = v['categoria'] as int?;
        _serie.text = (v['numero_serie'] as String?) ?? '';
        _nota.text = (v['nota_resolucion'] as String?) ?? '';
      });
    } on ApiException catch (e) {
      if (mounted) setState(() => _errorCarga = e.mensaje);
    }
  }

  Future<void> _guardar() async {
    final op = _op;
    if (op == null || _estado == null) return;
    setState(() {
      _guardando = true;
      _error = null;
    });
    final datos = <String, dynamic>{
      'estado': _estado,
      'categoria': _categoria,
      'numero_serie': _serie.text.trim(),
      'nota_resolucion': _nota.text.trim(),
      'motivo_espera': _motivo.text.trim(),
      if (op['puede_priorizar'] == true) 'prioridad': _prioridad ?? '',
    };
    try {
      final d = await ApiService.gestion(widget.ticketId, datos);
      if (!mounted) return;
      Navigator.of(context).pop(d);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.mensaje);
    } finally {
      if (mounted) setState(() => _guardando = false);
    }
  }

  Widget _titulo(String t) => Padding(
        padding: const EdgeInsets.only(top: 14, bottom: 4),
        child: Text(t, style: const TextStyle(fontWeight: FontWeight.w600)),
      );

  Widget _formulario(Map<String, dynamic> op) {
    final estados = (op['estados'] as List).cast<Map<String, dynamic>>();
    final prioridades = (op['prioridades'] as List).cast<Map<String, dynamic>>();
    final categorias = (op['categorias'] as List).cast<Map<String, dynamic>>();
    final puedePriorizar = op['puede_priorizar'] == true;
    final pideMotivo = _estado == 'EN_ESPERA' && _estadoOriginal != 'EN_ESPERA';
    final pideNota = _estado == 'POR_CONFIRMAR';

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Actualizar ticket',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
        _titulo('Estado'),
        Wrap(
          spacing: 8,
          runSpacing: 4,
          children: [
            for (final e in estados)
              ChoiceChip(
                label: Text(e['etiqueta'] as String),
                selected: _estado == e['valor'],
                onSelected: (_) => setState(() => _estado = e['valor'] as String),
              ),
          ],
        ),
        if (pideMotivo) ...[
          _titulo('Motivo de la espera'),
          TextField(
            controller: _motivo,
            minLines: 2,
            maxLines: 4,
            maxLength: 1000,
            decoration: const InputDecoration(
              hintText: 'Explica qué materiales faltan',
              border: OutlineInputBorder(),
            ),
          ),
        ],
        if (pideNota) ...[
          _titulo('Nota de resolución'),
          TextField(
            controller: _nota,
            minLines: 3,
            maxLines: 6,
            decoration: const InputDecoration(
              hintText: 'Qué se hizo para resolverlo',
              border: OutlineInputBorder(),
            ),
          ),
        ],
        if (puedePriorizar) ...[
          _titulo('Prioridad (SLA)'),
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: [
              for (final p in prioridades)
                ChoiceChip(
                  label: Text(p['etiqueta'] as String),
                  selected: _prioridad == p['valor'],
                  onSelected: (_) => setState(() => _prioridad = p['valor'] as String),
                ),
            ],
          ),
        ],
        _titulo('Categoría'),
        Wrap(
          spacing: 8,
          runSpacing: 4,
          children: [
            ChoiceChip(
              label: const Text('Sin categoría'),
              selected: _categoria == null,
              onSelected: (_) => setState(() => _categoria = null),
            ),
            for (final c in categorias)
              ChoiceChip(
                label: Text(c['nombre'] as String),
                selected: _categoria == c['id'],
                onSelected: (_) => setState(() => _categoria = c['id'] as int),
              ),
          ],
        ),
        _titulo('Número de serie / Service Tag'),
        TextField(
          controller: _serie,
          maxLength: 50,
          decoration: const InputDecoration(border: OutlineInputBorder()),
        ),
        if (_error != null) ...[
          const SizedBox(height: 8),
          Text(_error!, style: const TextStyle(color: Colors.red)),
        ],
        const SizedBox(height: 12),
        SizedBox(
          width: double.infinity,
          child: FilledButton(
            onPressed: _guardando ? null : _guardar,
            style: FilledButton.styleFrom(
              backgroundColor: Config.rojo,
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
            child: _guardando
                ? const SizedBox(
                    height: 20,
                    width: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Text('Guardar cambios'),
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final op = _op;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(
            16, 16, 16, 16 + MediaQuery.of(context).viewInsets.bottom),
        child: _errorCarga != null
            ? Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(_errorCarga!, textAlign: TextAlign.center),
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
                : SingleChildScrollView(child: _formulario(op)),
      ),
    );
  }
}