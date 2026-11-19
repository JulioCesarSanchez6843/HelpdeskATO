import 'package:flutter/material.dart';

import '../api_service.dart';
import '../config.dart';

class NuevoTicketScreen extends StatefulWidget {
  const NuevoTicketScreen({super.key});

  @override
  State<NuevoTicketScreen> createState() => _NuevoTicketScreenState();
}

class _NuevoTicketScreenState extends State<NuevoTicketScreen> {
  final _titulo = TextEditingController();
  final _descripcion = TextEditingController();
  bool _enviando = false;
  String? _error;

  @override
  void dispose() {
    _titulo.dispose();
    _descripcion.dispose();
    super.dispose();
  }

  Future<void> _crear() async {
    final titulo = _titulo.text.trim();
    final descripcion = _descripcion.text.trim();
    if (titulo.isEmpty || descripcion.isEmpty) {
      setState(() => _error = 'Escribe un título y una descripción.');
      return;
    }
    setState(() {
      _enviando = true;
      _error = null;
    });
    try {
      final d = await ApiService.crear(titulo, descripcion);
      if (!mounted) return;
      Navigator.of(context).pop(d.ticket.id);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.mensaje);
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Config.oscuro,
        foregroundColor: Colors.white,
        title: const Text('Nuevo ticket'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: _titulo,
              maxLength: 150,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(
                labelText: 'Título',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _descripcion,
              minLines: 5,
              maxLines: 8,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(
                labelText: 'Descripción',
                alignLabelWithHint: true,
                border: OutlineInputBorder(),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.red)),
            ],
            const SizedBox(height: 20),
            FilledButton(
              onPressed: _enviando ? null : _crear,
              style: FilledButton.styleFrom(
                backgroundColor: Config.rojo,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              child: _enviando
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white))
                  : const Text('Crear ticket'),
            ),
          ],
        ),
      ),
    );
  }
}