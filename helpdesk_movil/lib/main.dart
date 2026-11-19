import 'package:flutter/material.dart';

import 'api_service.dart';
import 'config.dart';
import 'screens/login_screen.dart';
import 'screens/tickets_screen.dart';

void main() => runApp(const HelpdeskApp());

class HelpdeskApp extends StatelessWidget {
  const HelpdeskApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Helpdesk Tollocan',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Config.rojo, primary: Config.rojo),
        useMaterial3: true,
      ),
      home: const _Arranque(),
    );
  }
}

class _Arranque extends StatelessWidget {
  const _Arranque();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<String?>(
      future: ApiService.token(),
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        return snap.data == null ? const LoginScreen() : const TicketsScreen();
      },
    );
  }
}