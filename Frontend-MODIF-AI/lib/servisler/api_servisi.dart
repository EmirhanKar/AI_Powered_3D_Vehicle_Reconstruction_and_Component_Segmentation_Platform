import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'auth_servisi.dart';
import '../modeller/kullanici_model.dart';
import '../modeller/scan_model.dart';
import '../modeller/community_model.dart';
import '../modeller/plugin_model.dart';
import '../modeller/magaza_model.dart';
import '../modeller/draft_model.dart';

class ApiServisi {
  static const String baseUrl = "http://192.168.1.194:8000";
  static const Duration _timeout = Duration(seconds: 15);
  final AuthServisi _auth = AuthServisi();

  // ═══════════════════════════════════════════════════
  //  YARDIMCI METOTLAR
  // ═══════════════════════════════════════════════════

  /// Backend'den dönen dosya yollarını tam URL'ye çevirir.
  /// Örn: "uploads/thumbnails/1/thumb_5.jpg" → "http://…/uploads/thumbnails/1/thumb_5.jpg"
  static String? buildImageUrl(String? path) {
    if (path == null || path.isEmpty) return null;
    if (path.startsWith('http')) return path; // Zaten tam URL ise dokunma
    // Baştaki slash varsa kaldır
    final cleanPath = path.startsWith('/') ? path.substring(1) : path;
    return '$baseUrl/$cleanPath';
  }

  Future<Map<String, String>> _authHeaders({String? contentType}) async {
    final headers = await _auth.getAuthHeaders();
    if (contentType != null) headers['Content-Type'] = contentType;
    return headers;
  }

  // ═══════════════════════════════════════════════════
  //  KULLANICI İŞLEMLERİ (AUTH)
  // ═══════════════════════════════════════════════════

  /// Yeni kullanıcı kaydı. Başarılıysa UserResponse döner.
  Future<Kullanici> kayitOl({
    required String name,
    required String surname,
    required String email,
    required String password,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/users/register'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'name': name,
        'surname': surname,
        'email': email,
        'password': password,
      }),
    ).timeout(_timeout);

    if (response.statusCode == 201) {
      return Kullanici.fromJson(json.decode(response.body));
    } else if (response.statusCode == 400) {
      throw Exception('Bu e-posta zaten kayıtlı!');
    } else {
      throw Exception('Kayıt hatası: ${response.statusCode}');
    }
  }

  /// OAuth2 form ile giriş. Token döner ve AuthServisi'ne kaydeder.
  Future<String> girisYap(String email, String sifre) async {
    final response = await http.post(
      Uri.parse('$baseUrl/users/login'),
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: {'username': email, 'password': sifre},
    ).timeout(_timeout, onTimeout: () {
      throw Exception('Sunucuya ulaşılamadı (Zaman aşımı)');
    });

    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      final token = data['access_token'];
      await _auth.saveToken(token);
      return token;
    } else if (response.statusCode == 401) {
      throw Exception('E-posta veya şifre hatalı!');
    } else {
      throw Exception('Giriş hatası: ${response.statusCode}');
    }
  }

  /// Giriş yapmış kullanıcının profil bilgilerini getirir.
  Future<Kullanici> beniBilgileriniGetir() async {
    final headers = await _authHeaders();
    final response = await http.get(
      Uri.parse('$baseUrl/users/me'),
      headers: headers,
    ).timeout(_timeout);

    if (response.statusCode == 200) {
      return Kullanici.fromJson(json.decode(response.body));
    } else if (response.statusCode == 401) {
      throw Exception('Oturum süresi dolmuş. Tekrar giriş yapın.');
    } else {
      throw Exception('Profil getirme hatası: ${response.statusCode}');
    }
  }

  /// Profil bilgilerini günceller.
  Future<Kullanici> profilGuncelle({
    String? name,
    String? surname,
    String? email,
    String? password,
  }) async {
    final headers = await _authHeaders(contentType: 'application/json');
    final body = <String, dynamic>{};
    if (name != null) body['name'] = name;
    if (surname != null) body['surname'] = surname;
    if (email != null) body['email'] = email;
    if (password != null) body['password'] = password;

    final response = await http.patch(
      Uri.parse('$baseUrl/users/me'),
      headers: headers,
      body: json.encode(body),
    ).timeout(_timeout);

    if (response.statusCode == 200) {
      return Kullanici.fromJson(json.decode(response.body));
    } else {
      throw Exception('Güncelleme hatası: ${response.statusCode}');
    }
  }

  /// Profil fotoğrafı yükler.
  Future<Kullanici> profilFotoYukle(XFile photo) async {
    final token = await _auth.getToken();
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/users/me/upload-photo'),
    );
    request.headers['Authorization'] = 'Bearer $token';
    request.files.add(await http.MultipartFile.fromPath('photo', photo.path));

    final streamedResponse = await request.send().timeout(_timeout);
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 200) {
      return Kullanici.fromJson(json.decode(response.body));
    } else {
      throw Exception('Fotoğraf yükleme hatası: ${response.statusCode}');
    }
  }

  // ═══════════════════════════════════════════════════
  //  TARAMA / GARAJ İŞLEMLERİ
  // ═══════════════════════════════════════════════════

  /// Fotoğraf yükleyip yeni tarama oluşturur.
  /// [files] = seçilen fotoğraflar, [method] = "2d" veya "3d"
  Future<Scan> fotografYukle({
    required List<XFile> files,
    required String carName,
    required String method,
    String? description,
  }) async {
    final token = await _auth.getToken();
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/scans/upload_image'),
    );
    request.headers['Authorization'] = 'Bearer $token';
    request.fields['car_name'] = carName;
    request.fields['method'] = method;
    if (description != null) request.fields['description'] = description;

    for (var file in files) {
      request.files.add(await http.MultipartFile.fromPath('files', file.path));
    }

    final streamedResponse = await request.send().timeout(
      const Duration(seconds: 60), // Fotoğraf yükleme için uzun timeout
    );
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 201) {
      return Scan.fromJson(json.decode(response.body));
    } else if (response.statusCode == 402) {
      throw Exception('Yetersiz kredi!');
    } else if (response.statusCode == 400) {
      final detail = json.decode(response.body)['detail'] ?? 'Geçersiz istek';
      throw Exception(detail);
    } else {
      throw Exception('Yükleme hatası: ${response.statusCode}');
    }
  }

  /// Kullanıcının tamamlanmış garaj araçlarını listeler.
  Future<List<Scan>> garajiGetir() async {
    final headers = await _authHeaders();
    final response = await http.get(
      Uri.parse('$baseUrl/scans/garage'),
      headers: headers,
    ).timeout(_timeout);

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Scan.fromJson(e)).toList();
    } else {
      throw Exception('Garaj getirme hatası: ${response.statusCode}');
    }
  }

  /// Tek bir taramanın detayını getirir.
  Future<Scan> scanDetayGetir(int scanId) async {
    final headers = await _authHeaders();
    final response = await http.get(
      Uri.parse('$baseUrl/scans/$scanId'),
      headers: headers,
    ).timeout(_timeout);

    if (response.statusCode == 200) {
      return Scan.fromJson(json.decode(response.body));
    } else {
      throw Exception('Detay getirme hatası: ${response.statusCode}');
    }
  }

  /// Taramayı siler.
  Future<void> scanSil(int scanId) async {
    final headers = await _authHeaders();
    final response = await http.delete(
      Uri.parse('$baseUrl/scans/$scanId'),
      headers: headers,
    ).timeout(_timeout);

    if (response.statusCode != 200) {
      throw Exception('Silme hatası: ${response.statusCode}');
    }
  }

  // ═══════════════════════════════════════════════════
  //  EKLENTİLER (PLUGINS)
  // ═══════════════════════════════════════════════════

  /// Tüm jantları listeler. Opsiyonel kategori filtresi.
  Future<List<JantModel>> jantlariGetir({String? category}) async {
    final headers = await _authHeaders();
    String url = '$baseUrl/plugins/jants';
    if (category != null) url += '?category=$category';

    final response = await http.get(
      Uri.parse(url),
      headers: headers,
    ).timeout(_timeout);

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => JantModel.fromJson(e)).toList();
    } else {
      throw Exception('Jant getirme hatası: ${response.statusCode}');
    }
  }

  /// Tüm renkleri listeler.
  Future<List<RenkModel>> renkleriGetir() async {
    final headers = await _authHeaders();
    final response = await http.get(
      Uri.parse('$baseUrl/plugins/colors'),
      headers: headers,
    ).timeout(_timeout);

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => RenkModel.fromJson(e)).toList();
    } else {
      throw Exception('Renk getirme hatası: ${response.statusCode}');
    }
  }

  // ═══════════════════════════════════════════════════
  //  TOPLULUK (COMMUNITY)
  // ═══════════════════════════════════════════════════

  /// Keşfet feed'ini getirir.
  Future<List<FeedItem>> feedGetir() async {
    final headers = await _authHeaders();
    final response = await http.get(
      Uri.parse('$baseUrl/community/feed'),
      headers: headers,
    ).timeout(_timeout);

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => FeedItem.fromJson(e)).toList();
    } else {
      throw Exception('Feed getirme hatası: ${response.statusCode}');
    }
  }

  /// Beğeni toggle (beğen / geri al).
  Future<Map<String, dynamic>> begeniToggle(int scanId) async {
    final headers = await _authHeaders();
    final response = await http.post(
      Uri.parse('$baseUrl/community/$scanId/like'),
      headers: headers,
    ).timeout(_timeout);

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Beğeni hatası: ${response.statusCode}');
    }
  }

  /// Bir aracın yorumlarını listeler.
  Future<List<Yorum>> yorumlariGetir(int scanId) async {
    final headers = await _authHeaders();
    final response = await http.get(
      Uri.parse('$baseUrl/community/$scanId/comments'),
      headers: headers,
    ).timeout(_timeout);

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Yorum.fromJson(e)).toList();
    } else {
      throw Exception('Yorum getirme hatası: ${response.statusCode}');
    }
  }

  /// Yorum ekler.
  Future<Yorum> yorumEkle(int scanId, String content) async {
    final headers = await _authHeaders(contentType: 'application/json');
    final response = await http.post(
      Uri.parse('$baseUrl/community/$scanId/comments'),
      headers: headers,
      body: json.encode({'content': content}),
    ).timeout(_timeout);

    if (response.statusCode == 201) {
      return Yorum.fromJson(json.decode(response.body));
    } else {
      throw Exception('Yorum ekleme hatası: ${response.statusCode}');
    }
  }

  // ═══════════════════════════════════════════════════
  //  MAĞAZA (STORE)
  // ═══════════════════════════════════════════════════

  /// Mağaza paketlerini listeler.
  Future<List<Paket>> paketleriGetir() async {
    final headers = await _authHeaders();
    final response = await http.get(
      Uri.parse('$baseUrl/store/packages'),
      headers: headers,
    ).timeout(_timeout);

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Paket.fromJson(e)).toList();
    } else {
      throw Exception('Paket getirme hatası: ${response.statusCode}');
    }
  }

  /// Paket satın alır.
  Future<SatinAlmaSonuc> paketSatinAl(String packageId) async {
    final headers = await _authHeaders();
    final response = await http.post(
      Uri.parse('$baseUrl/store/purchase/$packageId'),
      headers: headers,
    ).timeout(_timeout);

    if (response.statusCode == 200) {
      return SatinAlmaSonuc.fromJson(json.decode(response.body));
    } else {
      throw Exception('Satın alma hatası: ${response.statusCode}');
    }
  }

  /// Kullanıcının kredi ve abonelik bilgisini getirir.
  Future<KrediBilgisi> krediBilgisiGetir() async {
    final headers = await _authHeaders();
    final response = await http.get(
      Uri.parse('$baseUrl/store/my-credits'),
      headers: headers,
    ).timeout(_timeout);

    if (response.statusCode == 200) {
      return KrediBilgisi.fromJson(json.decode(response.body));
    } else {
      throw Exception('Kredi bilgisi hatası: ${response.statusCode}');
    }
  }

  // ═══════════════════════════════════════════════════
  //  MODİFİKASYON
  // ═══════════════════════════════════════════════════

  /// Yeni modifikasyon kaydı oluşturur.
  Future<Map<String, dynamic>> modifikasyonOlustur({
    required int scanId,
    int? jantId,
    int? colorId,
  }) async {
    final headers = await _authHeaders(contentType: 'application/json');
    final body = <String, dynamic>{'scan_id': scanId};
    if (jantId != null) body['jant_id'] = jantId;
    if (colorId != null) body['color_id'] = colorId;

    final response = await http.post(
      Uri.parse('$baseUrl/modifications'),
      headers: headers,
      body: json.encode(body),
    ).timeout(_timeout);

    if (response.statusCode == 201) {
      return json.decode(response.body);
    } else {
      throw Exception('Modifikasyon hatası: ${response.statusCode}');
    }
  }

  /// Kullanıcının taslaklarını getirir.
  Future<List<Taslak>> taslaklariGetir() async {
    final headers = await _authHeaders();
    final response = await http.get(
      Uri.parse('$baseUrl/modifications/drafts'),
      headers: headers,
    ).timeout(_timeout);

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Taslak.fromJson(e)).toList();
    } else {
      throw Exception('Taslak getirme hatası: ${response.statusCode}');
    }
  }
}