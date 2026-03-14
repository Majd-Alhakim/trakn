// =============================================================================
// TRAKN Parent App — lib/services/websocket_service.dart
// WebSocket connection to wss://trakn.duckdns.org/ws/position/{mac}?token=JWT
// Auto-reconnect with exponential backoff (1s → 2s → 4s → 8s → 16s → 30s cap).
// =============================================================================

import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as ws_status;

import '../models/position.dart';
import 'auth_service.dart';

class WebSocketService {
  static const _wsBase = 'wss://trakn.duckdns.org/ws/position';

  final AuthService _authService;
  final void Function(Position)   onPosition;
  final void Function(String)?    onError;
  final void Function(bool)?      onConnectionChange;

  WebSocketChannel?  _channel;
  StreamSubscription? _subscription;

  bool   _shouldConnect = false;
  bool   _isConnected   = false;
  String _currentMac    = '';
  int    _retryDelay    = 1;        // seconds
  Timer? _reconnectTimer;

  WebSocketService({
    required AuthService authService,
    required this.onPosition,
    this.onError,
    this.onConnectionChange,
  }) : _authService = authService;

  // ---------------------------------------------------------------------------
  // connect / disconnect
  // ---------------------------------------------------------------------------

  Future<void> connect(String mac) async {
    _shouldConnect = true;
    _currentMac    = mac.toUpperCase();
    _retryDelay    = 1;
    await _doConnect();
  }

  void disconnect() {
    _shouldConnect = false;
    _reconnectTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close(ws_status.goingAway);
    _isConnected = false;
    onConnectionChange?.call(false);
  }

  // ---------------------------------------------------------------------------
  // Internal connection logic
  // ---------------------------------------------------------------------------

  Future<void> _doConnect() async {
    if (!_shouldConnect || _currentMac.isEmpty) return;

    final token = await _authService.getToken();
    if (token == null || token.isEmpty) {
      _scheduleReconnect();
      return;
    }

    final uri = Uri.parse('$_wsBase/$_currentMac?token=$token');

    try {
      _channel = WebSocketChannel.connect(uri);
      _subscription = _channel!.stream.listen(
        _onMessage,
        onError: _onStreamError,
        onDone:  _onStreamDone,
        cancelOnError: false,
      );

      _isConnected = true;
      _retryDelay  = 1;
      onConnectionChange?.call(true);
    } catch (e) {
      _isConnected = false;
      onError?.call('Connection failed: $e');
      _scheduleReconnect();
    }
  }

  void _onMessage(dynamic raw) {
    try {
      final json = jsonDecode(raw as String) as Map<String, dynamic>;
      final pos  = Position.fromJson(json);
      onPosition(pos);
    } catch (e) {
      onError?.call('Parse error: $e');
    }
  }

  void _onStreamError(Object error) {
    _isConnected = false;
    onError?.call('Stream error: $error');
    onConnectionChange?.call(false);
    _scheduleReconnect();
  }

  void _onStreamDone() {
    _isConnected = false;
    onConnectionChange?.call(false);
    if (_shouldConnect) _scheduleReconnect();
  }

  // ---------------------------------------------------------------------------
  // Exponential backoff
  // ---------------------------------------------------------------------------

  void _scheduleReconnect() {
    if (!_shouldConnect) return;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(Duration(seconds: _retryDelay), () async {
      await _doConnect();
    });
    // Double delay, cap at 30 s
    _retryDelay = (_retryDelay * 2).clamp(1, 30);
  }

  // ---------------------------------------------------------------------------
  // Ping (keepalive)
  // ---------------------------------------------------------------------------
  void ping() {
    if (_isConnected) {
      try {
        _channel?.sink.add('ping');
      } catch (_) {}
    }
  }

  bool get isConnected => _isConnected;
}
