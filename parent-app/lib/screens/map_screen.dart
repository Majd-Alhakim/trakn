// =============================================================================
// TRAKN Parent App — lib/screens/map_screen.dart
// Floor plan + animated pulse marker.
// WebSocket-driven real-time child position. No technical overlay.
// =============================================================================

import 'dart:async';
import 'package:flutter/material.dart';

import '../models/position.dart';
import '../services/websocket_service.dart';
import '../services/auth_service.dart';

class MapScreen extends StatefulWidget {
  final String deviceMac;
  final String childName;
  final AuthService authService;

  const MapScreen({
    super.key,
    required this.deviceMac,
    required this.childName,
    required this.authService,
  });

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen>
    with TickerProviderStateMixin {

  late WebSocketService _ws;
  Position? _lastPosition;
  bool _connected = false;

  // Pulse animation
  late AnimationController _pulseCtrl;
  late Animation<double>   _pulseAnim;

  // Floor plan display bounds (in metres)
  double _mapWidthM  = 50.0;
  double _mapHeightM = 40.0;

  // Ping timer
  Timer? _pingTimer;

  @override
  void initState() {
    super.initState();

    _pulseCtrl = AnimationController(
      vsync:    this,
      duration: const Duration(seconds: 1),
    )..repeat(reverse: true);
    _pulseAnim = Tween<double>(begin: 10.0, end: 22.0).animate(
      CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut),
    );

    _ws = WebSocketService(
      authService:        widget.authService,
      onPosition:         _handlePosition,
      onError:            _handleError,
      onConnectionChange: _handleConnectionChange,
    );
    _ws.connect(widget.deviceMac);

    _pingTimer = Timer.periodic(const Duration(seconds: 20), (_) => _ws.ping());
  }

  void _handlePosition(Position pos) {
    if (mounted) setState(() => _lastPosition = pos);
  }

  void _handleError(String err) {
    // Silently log — no technical overlay shown to parent
    debugPrint('[WS] Error: $err');
  }

  void _handleConnectionChange(bool connected) {
    if (mounted) setState(() => _connected = connected);
  }

  @override
  void dispose() {
    _pingTimer?.cancel();
    _ws.disconnect();
    _pulseCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1A1D27),
        title: Row(
          children: [
            const Icon(Icons.child_care, color: Color(0xFF7C9CFF), size: 20),
            const SizedBox(width: 8),
            Text(
              widget.childName,
              style: const TextStyle(color: Color(0xFF7C9CFF), fontSize: 16),
            ),
          ],
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Center(
              child: Container(
                width: 10, height: 10,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: _connected ? const Color(0xFF3AFF88) : const Color(0xFFFF4444),
                ),
              ),
            ),
          ),
        ],
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final cw = constraints.maxWidth;
          final ch = constraints.maxHeight;

          // Map position → canvas coordinates
          double? markerX, markerY;
          if (_lastPosition != null) {
            markerX = (_lastPosition!.x / _mapWidthM)  * cw;
            markerY = (_lastPosition!.y / _mapHeightM) * ch;
          }

          return Stack(
            children: [
              // Floor plan placeholder (grey grid)
              _buildFloorPlanPlaceholder(cw, ch),

              // Pulse marker
              if (markerX != null && markerY != null)
                _buildPulseMarker(markerX, markerY),

              // Bottom status bar — parent-friendly only
              Positioned(
                left: 0, right: 0, bottom: 0,
                child: _buildStatusBar(),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildFloorPlanPlaceholder(double w, double h) {
    return CustomPaint(
      size: Size(w, h),
      painter: _GridPainter(),
    );
  }

  Widget _buildPulseMarker(double x, double y) {
    return Positioned(
      left: x - 22,
      top:  y - 22,
      child: AnimatedBuilder(
        animation: _pulseAnim,
        builder: (_, __) => SizedBox(
          width: 44, height: 44,
          child: Stack(
            alignment: Alignment.center,
            children: [
              // Outer pulse ring
              Container(
                width:  _pulseAnim.value * 2,
                height: _pulseAnim.value * 2,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: const Color(0xFF7C9CFF).withOpacity(0.25),
                ),
              ),
              // Inner dot
              Container(
                width: 16, height: 16,
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  color: Color(0xFF7C9CFF),
                ),
              ),
              // Child icon
              const Icon(Icons.child_care, color: Colors.white, size: 10),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatusBar() {
    String msg;
    if (!_connected) {
      msg = 'Connecting…';
    } else if (_lastPosition == null) {
      msg = 'Waiting for location…';
    } else {
      msg = 'Location updated';
    }

    return Container(
      color:   const Color(0xCC1A1D27),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Text(
        msg,
        style: const TextStyle(color: Color(0xFF8898AA), fontSize: 13),
        textAlign: TextAlign.center,
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Grid painter — draws a light grid as floor plan placeholder.
// ---------------------------------------------------------------------------
class _GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0xFF1E2035)
      ..strokeWidth = 0.8;

    const step = 40.0;
    for (double x = 0; x < size.width; x += step) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y < size.height; y += step) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(_GridPainter old) => false;
}
