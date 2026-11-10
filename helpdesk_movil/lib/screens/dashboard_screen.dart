import 'package:flutter/material.dart';
import '../models/ticket_model.dart';
import '../services/api_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final ApiService _apiService = ApiService();
  late Future<List<Ticket>> _futureTickets;

  @override
  void initState() {
    super.initState();
    // Disparamos la petición a la API de Django al cargar la pantalla
    _futureTickets = _apiService.getTickets();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Helpdesk - Tickets Móvil'),
        backgroundColor: Colors.blueAccent,
        foregroundColor: Colors.white,
      ),
      body: FutureBuilder<List<Ticket>>(
        future: _futureTickets,
        builder: (context, snapshot) {
          // Mientras carga la información de la web
          if (snapshot.connectionState == ConnectionState.waiting) {
            const Center(child: CircularProgressIndicator());
          }
          
          // Si hubo un error de conexión con Django
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Text(
                  'Error al conectar con el servidor:\n${snapshot.error}',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.red),
                ),
              ),
            );
          }

          // Si la petición fue exitosa pero no hay tickets registrados
          if (!snapshot.hasData || snapshot.data!.isEmpty) {
            return const Center(
              child: Text('No hay tickets registrados en el sistema.'),
            );
          }

          // Si tenemos datos, los listamos en tarjetas modernas
          final tickets = snapshot.data!;
          return ListView.builder(
            itemCount: tickets.length,
            itemBuilder: (context, index) {
              final ticket = tickets[index];
              return Card(
                margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                elevation: 3,
                child: ListTile(
                  leading: CircleAvatar(
                    backgroundColor: _getColorByPrioridad(ticket.prioridad),
                    child: Text(
                      '#${ticket.id}',
                      style: const TextStyle(color: Colors.white, fontSize: 12),
                    ),
                  ),
                  title: Text(
                    ticket.titulo,
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  subtitle: Text(
                    ticket.descripcion,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  trailing: Chip(
                    label: Text(
                      ticket.estado,
                      style: const TextStyle(fontSize: 10, color: Colors.white),
                    ),
                    backgroundColor: _getColorByEstado(ticket.estado),
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }

  // Colores dinámicos basados en la prioridad del modelo de tu compañero
  Color _getColorByPrioridad(String prioridad) {
    switch (prioridad) {
      case 'CRITICA':
        return Colors.red;
      case 'ALTA':
        return Colors.orange;
      case 'MEDIA':
        return Colors.amber.shade700;
      case 'BAJA':
        return Colors.green;
      default:
        return Colors.blue;
    }
  }

  // Colores dinámicos basados en el estado del ticket en Django
  Color _getColorByEstado(String estado) {
    switch (estado) {
      case 'ABIERTO':
        return Colors.blue;
      case 'EN_PROCESO':
        return Colors.purple;
      case 'EN_ESPERA':
        return Colors.orange;
      case 'CERRADO':
        return Colors.grey;
      default:
        return Colors.blueGrey;
    }
  }
}
