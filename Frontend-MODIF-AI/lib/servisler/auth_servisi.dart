import 'package:shared_preferences/shared_preferences.dart';

/// Kullanıcı oturum (token) yönetimi.
/// Token SharedPreferences'da saklanır; uygulama kapansa bile oturum korunur.
class AuthServisi {
  static const String _tokenKey = 'access_token';
  static const String _userIdKey = 'user_id';
  static const String _userNameKey = 'user_name';

  // ── Singleton ──────────────────────────────────────
  static final AuthServisi _instance = AuthServisi._internal();
  factory AuthServisi() => _instance;
  AuthServisi._internal();

  String? _cachedToken;

  // ── Token İşlemleri ────────────────────────────────

  Future<void> saveToken(String token) async {
    _cachedToken = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
  }

  Future<String?> getToken() async {
    if (_cachedToken != null) return _cachedToken;
    final prefs = await SharedPreferences.getInstance();
    _cachedToken = prefs.getString(_tokenKey);
    return _cachedToken;
  }

  Future<bool> isLoggedIn() async {
    final token = await getToken();
    return token != null && token.isNotEmpty;
  }

  Future<void> logout() async {
    _cachedToken = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    await prefs.remove(_userIdKey);
    await prefs.remove(_userNameKey);
  }

  // ── Yardımcı Kullanıcı Bilgisi ────────────────────

  Future<void> saveUserName(String name) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_userNameKey, name);
  }

  Future<String> getUserName() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_userNameKey) ?? '';
  }

  /// Authorization header'ı döner. Token yoksa boş map döner.
  Future<Map<String, String>> getAuthHeaders() async {
    final token = await getToken();
    if (token == null || token.isEmpty) return {};
    return {
      'Authorization': 'Bearer $token',
    };
  }
}
