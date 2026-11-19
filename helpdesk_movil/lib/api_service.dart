import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import 'config.dart';
import 'models/ticket.dart';

class ApiException implements Exception {
  final String mensaje;
  final int? codigo;
  ApiException(this.mensaje, {this.codigo});
  @override
  String toString() => mensaje;
}

class ApiService {
  static const _storage = FlutterSecureStorage();
  static const _kToken = 'token';
  static const _kRol = 'rol';

  static Future<String?> token() => _storage.read(key: _kToken);

  static Future<Map<String, String>> _headers() async {
    final t = await token();
    return {
      'Content-Type': 'application/json',
      if (t != null) 'Authorization': 'Token $t',
    };
  }

  static dynamic _decode(http.Response r) =>
      r.body.isEmpty ? null : jsonDecode(utf8.decode(r.bodyBytes));

  static ApiException _error(http.Response r) {
    var msg = 'Error ${r.statusCode}';
    try {
      final d = _decode(r);
      if (d is Map) {
        if (d['errores'] is Map) {
          final partes = (d['errores'] as Map)
              .values
              .expand((v) => v is List ? v : [v])
              .map((e) => e.toString())
              .toList();
          if (partes.isNotEmpty) msg = partes.join('\n');
        } else if (d['detail'] != null) {
          msg = d['detail'].toString();
        }
      }
    } catch (_) {}
    return ApiException(msg, codigo: r.statusCode);
  }

  static Future<http.Response> _send(Future<http.Response> Function() f) async {
    try {
      return await f().timeout(const Duration(seconds: 15));
    } catch (_) {
      throw ApiException('No se pudo conectar con el servidor.');
    }
  }

  static Future<http.Response> _validar(http.Response r) async {
    if (r.statusCode == 401) {
      await _storage.deleteAll();
      throw ApiException('Tu sesión expiró. Inicia sesión de nuevo.', codigo: 401);
    }
    if (r.statusCode >= 400) throw _error(r);
    return r;
  }

  static Future<http.Response> _get(String path) async {
    final h = await _headers();
    final r = await _send(() => http.get(Uri.parse('${Config.baseUrl}$path'), headers: h));
    return _validar(r);
  }

  static Future<http.Response> _post(String path, [Map<String, dynamic>? body]) async {
    final h = await _headers();
    final r = await _send(() => http.post(
          Uri.parse('${Config.baseUrl}$path'),
          headers: h,
          body: jsonEncode(body ?? <String, dynamic>{}),
        ));
    return _validar(r);
  }

  static TicketDetalle _det(http.Response r) =>
      TicketDetalle.fromJson(_decode(r) as Map<String, dynamic>);

  static Future<void> login(String correo, String password) async {
    final r = await _send(() => http.post(
          Uri.parse('${Config.baseUrl}/login/'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'correo': correo, 'password': password}),
        ));
    if (r.statusCode != 200) throw _error(r);
    final d = _decode(r) as Map<String, dynamic>;
    await _storage.write(key: _kToken, value: d['token'] as String);
    final u = d['usuario'] as Map<String, dynamic>?;
    if (u != null && u['rol'] != null) {
      await _storage.write(key: _kRol, value: u['rol'] as String);
    }
  }

  static Future<void> logout() async {
    try {
      await http
          .post(Uri.parse('${Config.baseUrl}/logout/'), headers: await _headers())
          .timeout(const Duration(seconds: 5));
    } catch (_) {}
    await _storage.deleteAll();
  }

  static Future<String?> rol() async {
    var r = await _storage.read(key: _kRol);
    if (r != null) return r;
    try {
      final resp = await _get('/me/');
      r = (_decode(resp) as Map<String, dynamic>)['rol'] as String?;
      if (r != null) await _storage.write(key: _kRol, value: r);
    } catch (_) {}
    return r;
  }

  static Future<List<Ticket>> tickets() async {
    final r = await _get('/tickets/?page_size=50');
    final d = _decode(r) as Map<String, dynamic>;
    return (d['results'] as List)
        .map((e) => Ticket.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  static Future<TicketDetalle> detalle(int id) async =>
      _det(await _get('/tickets/$id/'));

  static Future<TicketDetalle> comentar(int id, String contenido,
          {bool interno = false}) async =>
      _det(await _post('/tickets/$id/comentarios/',
          {'contenido': contenido, 'interno': interno}));

  static Future<TicketDetalle> tomar(int id) async =>
      _det(await _post('/tickets/$id/tomar/'));

  static Future<Opciones> opciones(int id) async => Opciones.fromJson(
      _decode(await _get('/tickets/$id/opciones/')) as Map<String, dynamic>);

  static Future<TicketDetalle> asignar(int id,
          {int? asignadoA, required String prioridad}) async =>
      _det(await _post('/tickets/$id/asignar/',
          {'asignado_a': asignadoA, 'prioridad': prioridad}));

  static Future<TicketDetalle> crear(String titulo, String descripcion) async =>
      _det(await _post('/tickets/nuevo/',
          {'titulo': titulo, 'descripcion': descripcion}));
}