// =============================================================================
// TRAKN Parent App — lib/services/auth_service.dart
// JWT stored in flutter_secure_storage. Login / Register.
// =============================================================================

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthService {
  static const _apiBase    = 'https://trakn.duckdns.org/api/v1';
  static const _tokenKey   = 'trakn_access_token';
  static const _userIdKey  = 'trakn_user_id';

  final _storage = const FlutterSecureStorage();
  final Dio _dio;

  AuthService() : _dio = Dio(BaseOptions(baseUrl: _apiBase));

  // ---------------------------------------------------------------------------
  // Token management
  // ---------------------------------------------------------------------------

  Future<String?> getToken() => _storage.read(key: _tokenKey);

  Future<void> saveToken(String token) =>
      _storage.write(key: _tokenKey, value: token);

  Future<void> deleteToken() async {
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _userIdKey);
  }

  Future<bool> isLoggedIn() async {
    final token = await getToken();
    return token != null && token.isNotEmpty;
  }

  // ---------------------------------------------------------------------------
  // Register
  // Returns null on success, or an error message string.
  // ---------------------------------------------------------------------------
  Future<String?> register(String email, String password) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/register',
        data: {'email': email, 'password': password},
      );
      if (response.statusCode == 201) return null;
      return 'Registration failed';
    } on DioException catch (e) {
      final detail = e.response?.data['detail'];
      return detail?.toString() ?? e.message ?? 'Unknown error';
    }
  }

  // ---------------------------------------------------------------------------
  // Login
  // Returns null on success, or an error message string.
  // ---------------------------------------------------------------------------
  Future<String?> login(String email, String password) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/login',
        data: {'email': email, 'password': password},
      );
      if (response.statusCode == 200) {
        final token = response.data!['access_token'] as String;
        await saveToken(token);
        return null;
      }
      return 'Login failed';
    } on DioException catch (e) {
      final detail = e.response?.data['detail'];
      return detail?.toString() ?? e.message ?? 'Unknown error';
    }
  }

  // ---------------------------------------------------------------------------
  // Logout
  // ---------------------------------------------------------------------------
  Future<void> logout() => deleteToken();

  // ---------------------------------------------------------------------------
  // Auth header helper
  // ---------------------------------------------------------------------------
  Future<Map<String, String>> authHeaders() async {
    final token = await getToken();
    if (token == null || token.isEmpty) return {};
    return {'Authorization': 'Bearer $token'};
  }
}
