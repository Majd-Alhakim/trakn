// =============================================================================
// TRAKN Parent App — lib/main.dart
// App entry point. Handles auth state and route navigation.
// =============================================================================

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'services/auth_service.dart';
import 'screens/home_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const TraknApp());
}

class TraknApp extends StatelessWidget {
  const TraknApp({super.key});

  @override
  Widget build(BuildContext context) {
    final authService = AuthService();

    return Provider<AuthService>.value(
      value: authService,
      child: MaterialApp(
        title: 'TRAKN',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          brightness: Brightness.dark,
          colorScheme: const ColorScheme.dark(
            primary: Color(0xFF7C9CFF),
            surface: Color(0xFF1A1D27),
          ),
          scaffoldBackgroundColor: const Color(0xFF0F1117),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF1A1D27),
            elevation: 0,
          ),
        ),
        home: _AuthGate(authService: authService),
        routes: {
          '/login': (_) => _LoginPage(authService: authService),
          '/home': (_) => HomeScreen(authService: authService),
        },
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Auth Gate: checks stored token and routes accordingly.
// ---------------------------------------------------------------------------
class _AuthGate extends StatefulWidget {
  final AuthService authService;
  const _AuthGate({required this.authService});

  @override
  State<_AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<_AuthGate> {
  @override
  void initState() {
    super.initState();
    _checkAuth();
  }

  Future<void> _checkAuth() async {
    final loggedIn = await widget.authService.isLoggedIn();
    if (!mounted) return;
    if (loggedIn) {
      Navigator.of(context).pushReplacementNamed('/home');
    } else {
      Navigator.of(context).pushReplacementNamed('/login');
    }
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: Color(0xFF0F1117),
      body: Center(
        child: CircularProgressIndicator(color: Color(0xFF7C9CFF)),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Login Page
// ---------------------------------------------------------------------------
class _LoginPage extends StatefulWidget {
  final AuthService authService;
  const _LoginPage({required this.authService});

  @override
  State<_LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<_LoginPage> {
  final _emailCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  bool _loading = false;
  String _error = '';
  bool _register = false;

  Future<void> _submit() async {
    final email = _emailCtrl.text.trim();
    final password = _passwordCtrl.text;

    if (email.isEmpty || password.isEmpty) {
      setState(() => _error = 'Enter email and password.');
      return;
    }

    setState(() {
      _loading = true;
      _error = '';
    });

    String? err;
    if (_register) {
      err = await widget.authService.register(email, password);
      if (err == null) {
        err = await widget.authService.login(email, password);
      }
    } else {
      err = await widget.authService.login(email, password);
    }

    if (!mounted) return;
    setState(() => _loading = false);

    if (err != null) {
      setState(() => _error = err!);
    } else {
      Navigator.of(context).pushReplacementNamed('/home');
    }
  }

  @override
  void dispose() {
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F1117),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(32),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 380),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.location_on,
                    color: Color(0xFF7C9CFF), size: 64),
                const SizedBox(height: 8),
                const Text(
                  'TRAKN',
                  style: TextStyle(
                    color: Color(0xFF7C9CFF),
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                const Text(
                  'Indoor Child Localization',
                  style: TextStyle(color: Color(0xFF6677AA), fontSize: 13),
                ),
                const SizedBox(height: 40),
                _field(_emailCtrl, 'Email', false),
                const SizedBox(height: 12),
                _field(_passwordCtrl, 'Password', true),
                const SizedBox(height: 20),
                if (_error.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(_error,
                        style: const TextStyle(
                            color: Colors.redAccent, fontSize: 13)),
                  ),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF3A4AAA),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                    onPressed: _loading ? null : _submit,
                    child: _loading
                        ? const SizedBox(
                            height: 18,
                            width: 18,
                            child: CircularProgressIndicator(
                                color: Colors.white, strokeWidth: 2),
                          )
                        : Text(_register ? 'Register' : 'Login',
                            style: const TextStyle(color: Colors.white)),
                  ),
                ),
                const SizedBox(height: 12),
                TextButton(
                  onPressed: () => setState(() {
                    _register = !_register;
                    _error = '';
                  }),
                  child: Text(
                    _register
                        ? 'Already have an account? Login'
                        : 'No account? Register',
                    style:
                        const TextStyle(color: Color(0xFF7C9CFF), fontSize: 13),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _field(TextEditingController ctrl, String label, bool obscure) {
    return TextField(
      controller: ctrl,
      obscureText: obscure,
      style: const TextStyle(color: Color(0xFFE0E0E0)),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: Color(0xFF8898AA)),
        filled: true,
        fillColor: const Color(0xFF1A1D27),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: Color(0xFF2D3148)),
        ),
      ),
    );
  }
}
