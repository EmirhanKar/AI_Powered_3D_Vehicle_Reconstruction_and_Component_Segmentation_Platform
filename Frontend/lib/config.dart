/// Uygulama genelinde kullanılan merkezi konfigürasyon.
/// Backend URL, timeout ve resim yolu gibi ayarlar burada tanımlanır.
class AppConfig {
  // ── Backend URL ──────────────────────────────────────
  // Android emülatör: http://10.0.2.2:8000
  // iOS simülatör:    http://localhost:8000
  // Fiziksel cihaz:   http://<bilgisayar-ip>:8000
  static const String baseUrl = "http://192.168.8.3:8000";

  // ── Timeout Ayarları ─────────────────────────────────
  static const Duration defaultTimeout = Duration(seconds: 30);
  static const Duration uploadTimeout = Duration(seconds: 120);

  // ── Yardımcı Metotlar ────────────────────────────────

  /// Sunucudan gelen göreceli resim yolunu tam URL'ye çevirir.
  /// Zaten http ile başlıyorsa dokunmaz.
  static String? buildImageUrl(String? path) {
    if (path == null || path.isEmpty) return null;
    if (path.startsWith('http')) return path;
    // Başındaki slash'ı temizle
    final clean = path.startsWith('/') ? path.substring(1) : path;
    return '$baseUrl/$clean';
  }
}
