// =============================================================================
// TRAKN Parent App — lib/screens/home_screen.dart
// List of linked children + "Add Child" button.
// =============================================================================

import 'package:flutter/material.dart';

import '../services/auth_service.dart';
import '../screens/link_tag_screen.dart';
import '../screens/map_screen.dart';

class LinkedChild {
  final String mac;
  final String childName;
  const LinkedChild({required this.mac, required this.childName});
}

class HomeScreen extends StatefulWidget {
  final AuthService authService;
  const HomeScreen({super.key, required this.authService});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final List<LinkedChild> _children = [];
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    // In a production app, fetch linked devices from backend here.
  }

  Future<void> _addChild() async {
    final result = await Navigator.of(context).push<Map<String, dynamic>>(
      MaterialPageRoute(
        builder: (_) => LinkTagScreen(authService: widget.authService),
      ),
    );
    if (result != null) {
      setState(() {
        _children.add(LinkedChild(
          mac: result['mac'] as String,
          childName: result['child_name'] as String,
        ));
      });
    }
  }

  void _openMap(LinkedChild child) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => MapScreen(
          deviceMac: child.mac,
          childName: child.childName,
          authService: widget.authService,
        ),
      ),
    );
  }

  Future<void> _logout() async {
    await widget.authService.logout();
    if (mounted) {
      Navigator.of(context).pushReplacementNamed('/login');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F1117),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1A1D27),
        title: const Text('TRAKN',
            style: TextStyle(color: Color(0xFF7C9CFF), fontSize: 18)),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout, color: Color(0xFF7C9CFF)),
            onPressed: _logout,
            tooltip: 'Logout',
          ),
        ],
      ),
      body: _children.isEmpty
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.child_care,
                      color: Color(0xFF3A4060), size: 80),
                  const SizedBox(height: 16),
                  const Text(
                    'No children linked yet.',
                    style: TextStyle(color: Color(0xFF6677AA), fontSize: 16),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Tap + to link a TRAKN tag.',
                    style: TextStyle(color: Color(0xFF4455AA), fontSize: 13),
                  ),
                ],
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _children.length,
              itemBuilder: (context, index) {
                final child = _children[index];
                return Card(
                  color: const Color(0xFF1A1D27),
                  margin: const EdgeInsets.only(bottom: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                    side: const BorderSide(color: Color(0xFF2D3148)),
                  ),
                  child: ListTile(
                    leading: const CircleAvatar(
                      backgroundColor: Color(0xFF2A3060),
                      child: Icon(Icons.child_care, color: Color(0xFF7C9CFF)),
                    ),
                    title: Text(
                      child.childName,
                      style: const TextStyle(
                          color: Color(0xFFE0E0E0),
                          fontWeight: FontWeight.w600),
                    ),
                    subtitle: Text(
                      child.mac,
                      style: const TextStyle(
                          color: Color(0xFF6677AA), fontSize: 11),
                    ),
                    trailing: const Icon(Icons.chevron_right,
                        color: Color(0xFF4455AA)),
                    onTap: () => _openMap(child),
                  ),
                );
              },
            ),
      floatingActionButton: FloatingActionButton(
        backgroundColor: const Color(0xFF3A4AAA),
        onPressed: _addChild,
        tooltip: 'Add Child',
        child: const Icon(Icons.add, color: Colors.white),
      ),
    );
  }
}
