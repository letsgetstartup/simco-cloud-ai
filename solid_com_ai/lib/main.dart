import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'screens/chat_screen.dart';

void main() {
  runApp(const SolidCamAIApp());
}

class SolidCamAIApp extends StatelessWidget {
  const SolidCamAIApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SolidCamAI',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0F0F0F),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF0F0F0F),
          elevation: 0,
          centerTitle: false,
        ),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFFFFD700),
          surface: Color(0xFF1E1E1E),
          onSurface: Colors.white,
        ),
        useMaterial3: true,
      ),
      home: const ChatScreen(),
    );
  }
}
