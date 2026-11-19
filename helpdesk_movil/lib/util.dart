import 'package:flutter/material.dart';

String _dos(int n) => n.toString().padLeft(2, '0');

String fecha(DateTime d) => '${_dos(d.day)}/${_dos(d.month)}/${d.year}';

String fechaHora(DateTime d) => '${fecha(d)} ${_dos(d.hour)}:${_dos(d.minute)}';

Color colorEstado(String estado) {
  switch (estado) {
    case 'ABIERTO':
      return Colors.blue;
    case 'EN_PROCESO':
      return Colors.orange;
    case 'EN_ESPERA':
      return Colors.purple;
    case 'POR_CONFIRMAR':
      return Colors.teal;
    default:
      return Colors.green;
  }
}