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
  late Future<List<Ticket>> _futuro;

  @override
  void initState() {
    super.initState();
    _futuro = ApiService.tickets();
  }

  Future<void> _recargar() async {
    final f = ApiService.tickets();
    setState(() { _futuro = f; });
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
      body: FutureBuilder<List<Ticket>>(
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
                children: const [
                  SizedBox(height: 160),
                  Center(child: Text('No hay tickets.')),
                ],
              ),
            );
          }
          return RefreshIndicator(
            onRefresh: _recargar,
            child: ListView.separated(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(12, 12, 12, 88),
              itemCount: tickets.length,
              separatorBuilder: (context, index) => const SizedBox(height: 8),
              itemBuilder: (context, i) {
                final t = tickets[i];
                final color = colorEstado(t.estado);
                final linea1 = [
                  t.creadoPor,
                  if (t.sucursal != null) t.sucursal!,
                  fecha(t.creadoEn),
                ].join(' · ');
                final linea2 =
                    t.asignadoA != null ? 'Asignado a ${t.asignadoA}' : 'Sin asignar';
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
                          style: TextStyle(
                              color: color, fontSize: 12, fontWeight: FontWeight.w600)),
                    ),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}