// =============================================================================
// TRAKN Parent App — lib/screens/link_tag_screen.dart
// Enter tag MAC → POST /api/v1/devices/link
// =============================================================================

import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import '../services/auth_service.dart';

class LinkTagScreen extends StatefulWidget {
  final AuthService authService;
  const LinkTagScreen({super.key, required this.authService});

  @override
  State<LinkTagScreen> createState() => _LinkTagScreenState();
}

class _LinkTagScreenState extends State<LinkTagScreen> {
  final _macController       = TextEditingController();
  final _childNameController = TextEditingController();
  bool   _loading = false;
  String _error   = '';

  static const _apiBase = 'https://trakn.duckdns.org/api/v1';

  Future<void> _linkDevice() async {
    final mac   = _macController.text.trim().toUpperCase();
    final name  = _childNameController.text.trim();

    // Basic MAC format validation
    final macRegex = RegExp(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$');
    if (!macRegex.hasMatch(mac)) {
      setState(() => _error = 'Invalid MAC address format (e.g. 24:42:E3:15:E5:72)');
      return;
    }
    if (name.isEmpty) {
      setState(() => _error = 'Enter child name.');
      return;
    }

    setState(() { _loading = true; _error = ''; });

    try {
      final headers = await widget.authService.authHeaders();
      final dio     = Dio(BaseOptions(baseUrl: _apiBase));
      final resp    = await dio.post<Map<String, dynamic>>(
        '/devices/link',
        data: {'mac': mac, 'child_name': name},
        options: Options(headers: headers),
      );

      if (resp.statusCode == 200 || resp.statusCode == 201) {
        if (mounted) {
          Navigator.of(context).pop({'mac': mac, 'child_name': name});
        }
      }
    } on DioException catch (e) {
      final detail = e.response?.data['detail'];
      setState(() => _error = detail?.toString() ?? e.message ?? 'Unknown error');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _macController.dispose();
    _childNameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1A1D27),
        title: const Text('Link Tag', style: TextStyle(color: Color(0xFF7C9CFF))),
        iconTheme: const IconThemeData(color: Color(0xFF7C9CFF)),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Enter the tag MAC address printed on the device.',
              style: TextStyle(color: Color(0xFF8898AA), fontSize: 14),
            ),
            const SizedBox(height: 24),
            _buildField(_macController, 'MAC Address', '24:42:E3:15:E5:72'),
            const SizedBox(height: 12),
            _buildField(_childNameController, "Child's Name", 'e.g. Layla'),
            const SizedBox(height: 24),
            if (_error.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(_error, style: const TextStyle(color: Colors.redAccent, fontSize: 13)),
              ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF3A4AAA),
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              onPressed: _loading ? null : _linkDevice,
              child: _loading
                  ? const SizedBox(
                      height: 18, width: 18,
                      child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                    )
                  : const Text('Link Device', style: TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildField(TextEditingController ctrl, String label, String hint) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: Color(0xFF8898AA), fontSize: 12)),
        const SizedBox(height: 4),
        TextField(
          controller:  ctrl,
          style:       const TextStyle(color: Color(0xFFE0E0E0)),
          decoration:  InputDecoration(
            hintText:        hint,
            hintStyle:       const TextStyle(color: Color(0xFF444466)),
            filled:          true,
            fillColor:       const Color(0xFF1A1D27),
            border:          OutlineInputBorder(borderRadius: BorderRadius.circular(6)),
            enabledBorder:   OutlineInputBorder(
              borderRadius: BorderRadius.circular(6),
              borderSide: const BorderSide(color: Color(0xFF2D3148)),
            ),
          ),
        ),
      ],
    );
  }
}
