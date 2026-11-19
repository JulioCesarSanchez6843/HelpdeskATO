import 'package:flutter/material.dart';

class Config {
  // Con "adb reverse tcp:8000 tcp:8000" el celular llega a Django en localhost.
  static const String baseUrl = 'http://localhost:8000/api';
  static const Color rojo = Color(0xFFC8102E);
  static const Color oscuro = Color(0xFF2F2F2F);
}