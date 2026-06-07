class AppConfig {
  // ── API Base URL ─────────────────────────────────
  // Geliştirme ortamı için local IP.
  // Deploy'da bunu sunucu adresinle değiştir:
  // Örn: "https://api.modifai.com" veya "http://123.456.789.0:8000"
  //
  // BUG-19 FIX: Ortam yapılandırması eklendi.
  // Release build'de _productionUrl, debug'da _devUrl kullanılır.
  static const String _devUrl = "http://10.204.181.194:8000" ;
  static const String _productionUrl = "https://api.modifai.com";

  /// Aktif base URL — ortama göre seçilir.
  /// Release build için _productionUrl'yi kullanmak istersen:
  ///   bool.fromEnvironment('dart.vm.product') → true ise release
  static const bool _useProduction = bool.fromEnvironment('dart.vm.product');
  static String get baseUrl => _useProduction ? _productionUrl : _devUrl;

  // ── Timeout Süreleri ─────────────────────────────
  static const Duration defaultTimeout = Duration(seconds: 15);
  static const Duration uploadTimeout = Duration(
    seconds: 60,
  ); // Fotoğraf yükleme

  // ── Görsel URL Oluşturucu ────────────────────────
  /// Backend'den dönen dosya yolunu tam URL'ye çevirir.
  /// Örn: "uploads/thumbnails/1/thumb_5.jpg" → "http://…/uploads/…"
  static String? buildImageUrl(String? path) {
    if (path == null || path.isEmpty) return null;
    if (path.startsWith('http')) return path;
    final cleanPath = path.startsWith('/') ? path.substring(1) : path;
    return '$baseUrl/$cleanPath';
  }
}
