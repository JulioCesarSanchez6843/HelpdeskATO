import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/ticket_model.dart';

class ApiService {
  // Nota: Si estás probando en un emulador Android, '10.0.2.2' apunta a tu localhost de la PC.
  // Si usas un dispositivo físico, debes poner la IP local de tu computadora (ej. 192.168.1.50).
  final String baseUrl = 'http://10.0.2.2:8000/api'; 

  // Método para obtener la lista de tickets desde la web de Django
  Future<List<Ticket>> getTickets() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/tickets/'));

      if (response.statusCode == 200) {
        // Decodificamos la respuesta JSON que nos manda Django
        List<dynamic> body = jsonDecode(utf8.decode(response.bodyBytes));
        
        // Convertimos cada elemento del JSON en una instancia de nuestro modelo Ticket
        List<Ticket> tickets = body.map((item) => Ticket.fromJson(item)).toList();
        
        return tickets;
      } else {
        throw Exception('Error al cargar los tickets: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Error de conexión: $e');
    }
  }
}
