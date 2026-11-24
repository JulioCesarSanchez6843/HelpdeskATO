import 'dart:async';

import 'package:flutter/material.dart';

import '../api_service.dart';
import '../config.dart';
import '../models/ticket.dart';
import '../util.dart';
import 'detalle_screen.dart';
import 'login_screen.dart';
import 'nuevo_ticket_screen.dart';

class TicketsScreen extends StatefulWidget {
  const TicketsScreen({super.key});

  @override
  State<TicketsScreen> createState() => _TicketsScreenState();
}

class _TicketsScreenState extends State<TicketsScreen> {
  static const _estados = <String, String>{
    'ABIERTO': 'Abierto',
    'EN_PROCESO': 'En proceso',
    'EN_ESPERA': 'En espera',
    'POR_CONFIRMAR': 'Por confirmar',
    'CERRADO': 'Cerrado',
  };

  final _busqueda = TextEditingController();
  Timer? _espera;
  String? _estado;
  bool _soloMios = false;
  bool _esPersonal = false;
  late Future<List<Ticket>> _futuro;

  @override
  void initState() {
    super.initState();
    _futuro = _consultar();
    ApiService.rol().then((rol) {
      if (!mounted) return;
      setState(() {
        _esPersonal = const ['SUPERADMIN', 'ENCARGADO', 'BECARIO'].contains(rol);
      });
    });
  }

  @override
  void dispose() {
    _espera?.cancel();
    _busqueda.dispose();
    super.dispose();
  }

  Future<List<Ticket>> _consultar() => ApiService.tickets(
        estado: _estado,
        busqueda: _busqueda.text.trim(),
        asignadosAMi: _soloMios,
      );

  void _cambiar(void Function() cambio) {
    setState(() {
      cambio();
      _futuro = _consultar();
    });
  }

  void _alEscribir(String _) {
    _espera?.cancel();
    _espera = Timer(const Duration(milliseconds: 450), () {
      if (mounted) _cambiar(() {});
    });
  }

  Future<void> _recargar() async {
    final f = _consultar();
    setState(() {
      _futuro = f;
    });
    try {
      await f;
    } catch (_) {}
  }

  Future<void> _irALogin({bool cerrarSesion = false}) async {
    if (cerrarSesion) await ApiService.logout();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
    );
  }

  Future<void> _abrir(int id) async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => DetalleScreen(ticketId: id)),
    );
    if (mounted) _recargar();
  }

  Future<void> _nuevo() async {
    final id = await Navigator.of(context).push<int>(
      MaterialPageRoute(builder: (_) => const NuevoTicketScreen()),
    );
    if (!mounted) return;
    _recargar();
    if (id != null) {
      await Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => DetalleScreen(ticketId: id)),
      );
      if (mounted) _recargar();
    }
  }

  bool get _hayFiltros =>
      _estado != null || _soloMios || _busqueda.text.trim().isNotEmpty;

  Widget _filtros() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 4),
          child: TextField(
            controller: _busqueda,
            onChanged: _alEscribir,
            textInputAction: TextInputAction.search,
            decoration: InputDecoration(
              hintText: 'Buscar por título o descripción',
              prefixIcon: const Icon(Icons.search),
              isDense: true,
              border: const OutlineInputBorder(),
              suffixIcon: _busqueda.text.isEmpty
                  ? null
                  : IconButton(
                      icon: const Icon(Icons.clear),
                      onPressed: () {
                        _busqueda.clear();
                        _cambiar(() {});
                      },
                    ),
            ),
          ),
        ),
        SizedBox(
          height: 46,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            children: [
              if (_esPersonal)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: const Text('Mis asignados'),
                    selected: _soloMios,
                    onSelected: (v) => _cambiar(() {
                      _soloMios = v;
                    }),
                  ),
                ),
              Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  label: const Text('Todos'),
                  selected: _estado == null,
                  onSelected: (_) => _cambiar(() {
                    _estado = null;
                  }),
                ),
              ),
              for (final e in _estados.entries)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(e.value),
                    selected: _estado == e.key,
                    onSelected: (_) => _cambiar(() {
                      _estado = e.key;
                    }),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _tarjeta(Ticket t) {
    final color = colorEstado(t.estado);
    final linea1 = [
      t.creadoPor,
      if (t.sucursal != null) t.sucursal!,
      fecha(t.creadoEn),
    ].join(' · ');
    final linea2 = t.asignadoA != null ? 'Asignado a ${t.asignadoA}' : 'Sin asignar';
    return Card(
      margin: EdgeInsets.zero,
      child: ListTile(
        onTap: () => _abrir(t.id),
        isThreeLine: true,
        title: Text('#${t.id}  ${t.titulo}',
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text('$linea1\n$linea2'),
        trailing: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(t.estadoDisplay,
              style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
        ),
      ),
    );
  }

  Widget _resultados() {
    return FutureBuilder<List<Ticket>>(
      future: _futuro,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          final e = snap.error;
          final sesion = e is ApiException && e.codigo == 401;
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(e is ApiException ? e.mensaje : 'Ocurrió un error.',
                      textAlign: TextAlign.center),
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: sesion ? _irALogin : _recargar,
                    child: Text(sesion ? 'Ir al inicio de sesión' : 'Reintentar'),
                  ),
                ],
              ),
            ),
          );
        }
        final tickets = snap.data!;
        if (tickets.isEmpty) {
          return RefreshIndicator(
            onRefresh: _recargar,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                const SizedBox(height: 120),
                Center(
                  child: Text(_hayFiltros
                      ? 'No hay tickets con esos filtros.'
                      : 'No hay tickets.'),
                ),
              ],
            ),
          );
        }
        return RefreshIndicator(
          onRefresh: _recargar,
          child: ListView.separated(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 88),
            itemCount: tickets.length,
            separatorBuilder: (context, index) => const SizedBox(height: 8),
            itemBuilder: (context, i) => _tarjeta(tickets[i]),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Config.oscuro,
        foregroundColor: Colors.white,
        title: const Text('Tickets'),
        actions: [
          IconButton(
            tooltip: 'Cerrar sesión',
            icon: const Icon(Icons.logout),
            onPressed: () => _irALogin(cerrarSesion: true),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: Config.rojo,
        foregroundColor: Colors.white,
        onPressed: _nuevo,
        icon: const Icon(Icons.add),
        label: const Text('Nuevo ticket'),
      ),
      body: Column(
        children: [
          _filtros(),
          Expanded(child: _resultados()),
        ],
      ),
    );
  }
}