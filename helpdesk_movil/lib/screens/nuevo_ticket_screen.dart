import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../api_service.dart';
import '../config.dart';

class NuevoTicketScreen extends StatefulWidget {
  const NuevoTicketScreen({super.key});

  @override
  State<NuevoTicketScreen> createState() => _NuevoTicketScreenState();
}

class _NuevoTicketScreenState extends State<NuevoTicketScreen> {
  static const _maxFotos = 5;

  final _titulo = TextEditingController();
  final _descripcion = TextEditingController();
  final _picker = ImagePicker();
  final List<XFile> _fotos = [];
  bool _enviando = false;
  String? _error;

  @override
  void dispose() {
    _titulo.dispose();
    _descripcion.dispose();
    super.dispose();
  }

  Future<void> _tomarFoto() async {
    if (_fotos.length >= _maxFotos) return;
    try {
      final f = await _picker.pickImage(
        source: ImageSource.camera,
        imageQuality: 85,
        maxWidth: 2000,
      );
      if (f != null && mounted) {
        setState(() {
          _fotos.add(f);
        });
      }
    } catch (_) {
      if (mounted) setState(() => _error = 'No se pudo abrir la cámara.');
    }
  }

  Future<void> _elegirGaleria() async {
    final restantes = _maxFotos - _fotos.length;
    if (restantes <= 0) return;
    try {
      final fs = await _picker.pickMultiImage(imageQuality: 85, maxWidth: 2000);
      if (fs.isNotEmpty && mounted) {
        setState(() {
          _fotos.addAll(fs.take(restantes));
        });
      }
    } catch (_) {
      if (mounted) setState(() => _error = 'No se pudo abrir la galería.');
    }
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
      final d = await ApiService.crearConFotos(
        titulo,
        descripcion,
        _fotos.map((f) => f.path).toList(),
      );
      if (!mounted) return;
      Navigator.of(context).pop(d.ticket.id);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.mensaje);
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  Widget _miniatura(int i) {
    final f = _fotos[i];
    return Stack(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: Image.file(
            File(f.path),
            width: 84,
            height: 84,
            fit: BoxFit.cover,
            cacheWidth: 252,
          ),
        ),
        Positioned(
          top: 2,
          right: 2,
          child: InkWell(
            onTap: _enviando
                ? null
                : () {
                    setState(() {
                      _fotos.removeAt(i);
                    });
                  },
            child: Container(
              decoration: const BoxDecoration(
                color: Colors.black54,
                shape: BoxShape.circle,
              ),
              padding: const EdgeInsets.all(3),
              child: const Icon(Icons.close, size: 14, color: Colors.white),
            ),
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final lleno = _fotos.length >= _maxFotos;
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
            const SizedBox(height: 12),
            Text('Fotos (${_fotos.length}/$_maxFotos)',
                style: const TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                OutlinedButton.icon(
                  onPressed: (_enviando || lleno) ? null : _tomarFoto,
                  icon: const Icon(Icons.photo_camera_outlined),
                  label: const Text('Tomar foto'),
                ),
                OutlinedButton.icon(
                  onPressed: (_enviando || lleno) ? null : _elegirGaleria,
                  icon: const Icon(Icons.photo_library_outlined),
                  label: const Text('Galería'),
                ),
              ],
            ),
            if (_fotos.isNotEmpty) ...[
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [for (var i = 0; i < _fotos.length; i++) _miniatura(i)],
              ),
            ],
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