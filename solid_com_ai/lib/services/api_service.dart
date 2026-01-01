import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/message.dart';

class ApiService {
  // Using the Hosting URL which rewrites to Cloud Functions
  static const String _baseUrl = 'https://solidcam-f58bc.web.app/ask';

  Future<String> sendMessage(String question) async {
    try {
      final response = await http.post(
        Uri.parse(_baseUrl),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'question': question,
          // 'collection' is removed for Unified Data View
          // No API Key needed - handled by server-side secrets
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        // The backend now returns { "answer": "...", "follow_up": [...] }
        // For now, we return the answer. The Flutter UI can be updated to support chips later.
        return data['answer'] ?? 'No answer provided.';
      } else {
        final errorData = jsonDecode(response.body);
        return "Error: ${errorData['error'] ?? 'Unknown error occurred'}";
      }
    } catch (e) {
      return "Failed to connect to Simco AI: $e";
    }
  }
}
