import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../api_service.dart';

class ImagenAdjunta extends StatefulWidget {
  final int id;
  final double tamano;
  const ImagenAdjunta({super.key, required this.id, this.tamano = 90});

  @override
  State<ImagenAdjunta> createState() => _ImagenAdjuntaState();
}

class _ImagenAdjuntaState extends State<ImagenAdjunta> {
  late final Future<Uint8List> _futuro;

  @override
  void initState() {
    super.initState();
    _futuro = ApiService.imagen(widget.id);
  }

  void _ampliar(Uint8List bytes) {
    showDialog<void>(
      context: context,
      builder: (ctx) => Dialog.fullscreen(
        backgroundColor: Colors.black,
        child: Stack(
          children: [
            Positioned.fill(
              child: InteractiveViewer(
                child: Center(child: Image.memory(bytes)),
              ),
            ),
            Positioned(
              top: 8,
              right: 8,
              child: SafeArea(
                child: IconButton(
                  icon: const Icon(Icons.close, color: Colors.white),
                  onPressed: () => Navigator.pop(ctx),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final t = widget.tamano;
    return FutureBuilder<Uint8List>(
      future: _futuro,
      builder: (context, snap) {
        Widget hijo;
        if (snap.connectionState != ConnectionState.done) {
          hijo = const Center(
            child: SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
          );
        } else if (snap.hasError || snap.data == null) {
          hijo = const Center(
            child: Icon(Icons.broken_image_outlined, color: Colors.black38),
          );
        } else {
          final bytes = snap.data!;
          hijo = GestureDetector(
            onTap: () => _ampliar(bytes),
            child: Image.memory(bytes, fit: BoxFit.cover, cacheWidth: (t * 3).round()),
          );
        }
        return ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: Container(width: t, height: t, color: Colors.black12, child: hijo),
        );
      },
    );
  }
}