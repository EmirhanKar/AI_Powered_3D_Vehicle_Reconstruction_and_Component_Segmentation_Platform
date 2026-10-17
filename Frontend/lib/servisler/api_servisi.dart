import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'auth_servisi.dart';
import '../config.dart'; // baseUrl buradan geliyor
import '../modeller/kullanici_model.dart';
import '../modeller/scan_model.dart';
import '../modeller/community_model.dart';
import '../modeller/plugin_model.dart';
import '../modeller/magaza_model.dart';
import '../modeller/draft_model.dart';

class ApiServisi {
  // baseUrl artık AppConfig'den geliyor
  static String get baseUrl => AppConfig.baseUrl;
  static Duration get _timeout => AppConfig.defaultTimeout;

  final AuthServisi _auth = AuthServisi();

  // ═══════════════════════════════════════════════════
  //  YARDIMCI METOTLAR
  // ═══════════════════════════════════════════════════

  static String? buildImageUrl(String? path) => AppConfig.buildImageUrl(path);

  /// 🌟 AKILLI HEADER MOTORU: 
  /// Eğer URL ngrok içeriyorsa bypass başlığını otomatik ekler, lokalde/deployda eklemez.
  /// Böylece ileride kodları değiştirmek zorunda kalmazsın.
  Future<Map<String, String>> _authHeaders({String? contentType}) async {
    final headers = await _auth.getAuthHeaders();
    if (contentType != null) headers['Content-Type'] = contentType;
    
    if (baseUrl.contains('ngrok')) {
      headers['ngrok-skip-browser-warning'] = 'true';
    }
    return headers;
  }

  // ═══════════════════════════════════════════════════
  //  KULLANICI İŞLEMLERİ (AUTH)
  // ═══════════════════════════════════════════════════

  Future<Kullanici> kayitOl({
    required String name,
    required String surname,
    required String email,
    required String password,
    String phoneNumber = '',
  }) async {
    final Map<String, String> headers = {'Content-Type': 'application/json'};
    if (baseUrl.contains('ngrok')) {
      headers['ngrok-skip-browser-warning'] = 'true';
    }

    final response = await http
        .post(
          Uri.parse('$baseUrl/users/register'),
          headers: headers,
          body: json.encode({
            'name': name,
            'surname': surname,
            'email': email,
            'password': password,
            'phone_number': phoneNumber,
          }),
        )
        .timeout(_timeout);

    if (response.statusCode == 201) {
      return Kullanici.fromJson(json.decode(response.body));
    } else if (response.statusCode == 400) {
      throw Exception('Bu e-posta zaten kayıtlı!');
    } else {
      throw Exception('Kayıt hatası: ${response.statusCode}');
    }
  }

  Future<String> girisYap(String email, String sifre) async {
    final Map<String, String> headers = {'Content-Type': 'application/x-www-form-urlencoded'};
    if (baseUrl.contains('ngrok')) {
      headers['ngrok-skip-browser-warning'] = 'true';
    }

    final response = await http
        .post(
          Uri.parse('$baseUrl/users/login'),
          headers: headers,
          body: {'username': email, 'password': sifre},
        )
        .timeout(
          _timeout,
          onTimeout: () {
            throw Exception('Sunucuya ulaşılamadı (Zaman aşımı)');
          },
        );

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

  Future<Kullanici> beniBilgileriniGetir() async {
    final headers = await _authHeaders();
    final response = await http
        .get(Uri.parse('$baseUrl/users/me'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      return Kullanici.fromJson(json.decode(response.body));
    } else if (response.statusCode == 401) {
      throw Exception('Oturum süresi dolmuş. Tekrar giriş yapın.');
    } else {
      throw Exception('Profil getirme hatası: ${response.statusCode}');
    }
  }

  Future<Kullanici> profilGuncelle({
    String? name,
    String? surname,
    String? email,
    String? phoneNumber,
    String? password,
  }) async {
    final headers = await _authHeaders(contentType: 'application/json');
    final body = <String, dynamic>{};
    if (name != null) body['name'] = name;
    if (surname != null) body['surname'] = surname;
    if (email != null) body['email'] = email;
    if (phoneNumber != null) body['phone_number'] = phoneNumber;
    if (password != null) body['password'] = password;

    final response = await http
        .patch(
          Uri.parse('$baseUrl/users/me'),
          headers: headers,
          body: json.encode(body),
        )
        .timeout(_timeout);

    if (response.statusCode == 200) {
      return Kullanici.fromJson(json.decode(response.body));
    } else {
      throw Exception('Güncelleme hatası: ${response.statusCode}');
    }
  }

  Future<Kullanici> profilFotoYukle(XFile photo) async {
    final token = await _auth.getToken();
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/users/me/upload-photo'),
    );
    request.headers['Authorization'] = 'Bearer $token';
    if (baseUrl.contains('ngrok')) {
      request.headers['ngrok-skip-browser-warning'] = 'true';
    }
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
    if (baseUrl.contains('ngrok')) {
      request.headers['ngrok-skip-browser-warning'] = 'true';
    }
    request.fields['car_name'] = carName;
    request.fields['method'] = method;
    if (description != null) request.fields['description'] = description;

    for (var file in files) {
      request.files.add(await http.MultipartFile.fromPath('files', file.path));
    }

    final streamedResponse = await request.send().timeout(
      AppConfig.uploadTimeout,
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

  Future<List<Scan>> garajiGetir() async {
    final headers = await _authHeaders();
    final response = await http
        .get(Uri.parse('$baseUrl/scans/garage'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Scan.fromJson(e)).toList();
    } else {
      throw Exception('Garaj getirme hatası: ${response.statusCode}');
    }
  }

  Future<Scan> scanDetayGetir(int scanId) async {
    final headers = await _authHeaders();
    final response = await http
        .get(Uri.parse('$baseUrl/scans/$scanId'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      return Scan.fromJson(json.decode(response.body));
    } else {
      throw Exception('Detay getirme hatası: ${response.statusCode}');
    }
  }

  Future<void> scanSil(int scanId) async {
    final headers = await _authHeaders();
    final response = await http
        .delete(Uri.parse('$baseUrl/scans/$scanId'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode != 200) {
      throw Exception('Silme hatası: ${response.statusCode}');
    }
  }

  Future<Map<String, dynamic>> aracTespitEt(XFile photo) async {
    final token = await _auth.getToken();
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/scans/detect_car'),
    );
    request.headers['Authorization'] = 'Bearer $token';
    if (baseUrl.contains('ngrok')) {
      request.headers['ngrok-skip-browser-warning'] = 'true';
    }
    request.files.add(await http.MultipartFile.fromPath('image', photo.path));

    final streamedResponse = await request.send().timeout(const Duration(seconds: 15));
    final response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Araç tespit hatası: ${response.statusCode}');
    }
  }

  // ═══════════════════════════════════════════════════
  //  EKLENTİLER (PLUGINS)
  // ═══════════════════════════════════════════════════

  Future<List<JantModel>> jantlariGetir({String? category}) async {
    final headers = await _authHeaders();
    String url = '$baseUrl/plugins/jants';
    if (category != null) url += '?category=$category';

    final response = await http
        .get(Uri.parse(url), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => JantModel.fromJson(e)).toList();
    } else {
      throw Exception('Jant getirme hatası: ${response.statusCode}');
    }
  }

  Future<List<RenkModel>> renkleriGetir() async {
    final headers = await _authHeaders();
    final response = await http
        .get(Uri.parse('$baseUrl/plugins/colors'), headers: headers)
        .timeout(_timeout);

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

  Future<List<FeedItem>> feedGetir() async {
    final headers = await _authHeaders();
    final response = await http
        .get(Uri.parse('$baseUrl/community/feed'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => FeedItem.fromJson(e)).toList();
    } else {
      throw Exception('Feed getirme hatası: ${response.statusCode}');
    }
  }

  Future<List<FeedItem>> exploreTopGetir() async {
    final headers = await _authHeaders();
    final response = await http
        .get(Uri.parse('$baseUrl/community/explore/top'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => FeedItem.fromJson(e)).toList();
    } else {
      throw Exception('Top explore getirme hatası: ${response.statusCode}');
    }
  }

  Future<Map<String, dynamic>> begeniToggle(int scanId) async {
    final headers = await _authHeaders();
    final response = await http
        .post(Uri.parse('$baseUrl/community/$scanId/like'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Beğeni hatası: ${response.statusCode}');
    }
  }

  Future<List<Yorum>> yorumlariGetir(int scanId) async {
    final headers = await _authHeaders();
    final response = await http
        .get(Uri.parse('$baseUrl/community/$scanId/comments'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Yorum.fromJson(e)).toList();
    } else {
      throw Exception('Yorum getirme hatası: ${response.statusCode}');
    }
  }

  Future<Yorum> yorumEkle(int scanId, String content) async {
    final headers = await _authHeaders(contentType: 'application/json');
    final response = await http
        .post(
          Uri.parse('$baseUrl/community/$scanId/comments'),
          headers: headers,
          body: json.encode({'content': content}),
        )
        .timeout(_timeout);

    if (response.statusCode == 201) {
      return Yorum.fromJson(json.decode(response.body));
    } else {
      throw Exception('Yorum ekleme hatası: ${response.statusCode}');
    }
  }

  Future<Map<String, dynamic>> yorumBegeniToggle(int commentId) async {
    final headers = await _authHeaders();
    final response = await http
        .post(Uri.parse('$baseUrl/community/comments/$commentId/like'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Yorum beğeni hatası: ${response.statusCode}');
    }
  }

  Future<void> yorumSil(int commentId) async {
    final headers = await _authHeaders();
    final response = await http
        .delete(Uri.parse('$baseUrl/community/comments/$commentId'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode != 200 && response.statusCode != 204) {
      throw Exception('Yorum silme hatası: ${response.statusCode}');
    }
  }

  // ═══════════════════════════════════════════════════
  //  MAĞAZA (STORE)
  // ═══════════════════════════════════════════════════

  Future<List<Paket>> paketleriGetir() async {
    final headers = await _authHeaders();
    final response = await http
        .get(Uri.parse('$baseUrl/store/packages'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Paket.fromJson(e)).toList();
    } else {
      throw Exception('Paket getirme hatası: ${response.statusCode}');
    }
  }

  Future<SatinAlmaSonuc> paketSatinAl(String packageId) async {
    final headers = await _authHeaders();
    final response = await http
        .post(Uri.parse('$baseUrl/store/purchase/$packageId'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      return SatinAlmaSonuc.fromJson(json.decode(response.body));
    } else {
      throw Exception('Satın alma hatası: ${response.statusCode}');
    }
  }

  Future<KrediBilgisi> krediBilgisiGetir() async {
    final headers = await _authHeaders();
    final response = await http
        .get(Uri.parse('$baseUrl/store/my-credits'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      return KrediBilgisi.fromJson(json.decode(response.body));
    } else {
      throw Exception('Kredi bilgisi hatası: ${response.statusCode}');
    }
  }

  // ═══════════════════════════════════════════════════
  //  MODİFİKASYON
  // ═══════════════════════════════════════════════════

  Future<Map<String, dynamic>> modifikasyonKredileriGetir() async {
    final headers = await _authHeaders();
    final response = await http
        .get(Uri.parse('$baseUrl/modifications/costs'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Modifikasyon kredi bilgisi hatası: ${response.statusCode}');
    }
  }

  Future<Map<String, dynamic>> modifikasyonOlustur({
    required int scanId,
    int? jantId,
    int? colorId,
    String? paintLocation,
  }) async {
    final headers = await _authHeaders(contentType: 'application/json');
    final body = <String, dynamic>{'scan_id': scanId};
    if (jantId != null) body['jant_id'] = jantId;
    if (colorId != null) body['color_id'] = colorId;
    if (paintLocation != null) body['paint_location'] = paintLocation;

    final response = await http
        .post(
          Uri.parse('$baseUrl/modifications'),
          headers: headers,
          body: json.encode(body),
        )
        .timeout(_timeout);

    if (response.statusCode == 201) {
      return json.decode(response.body);
    } else if (response.statusCode == 402) {
      final d = json.decode(response.body);
      throw Exception(d['detail'] ?? 'Yetersiz kredi!');
    } else if (response.statusCode == 400) {
      final d = json.decode(response.body);
      throw Exception(d['detail'] ?? '3D model henüz hazır değil.');
    } else {
      String errMsg = 'Modifikasyon hatası: ${response.statusCode}';
      try {
        final d = json.decode(response.body);
        if (d['detail'] != null) errMsg = d['detail'];
      } catch (_) {}
      throw Exception(errMsg);
    }
  }

  Future<Map<String, dynamic>> modifikasyonGuncelle({
    required int modificationId,
    int? jantId,
    int? colorId,
    String? paintLocation,
  }) async {
    final headers = await _authHeaders(contentType: 'application/json');
    final body = <String, dynamic>{};
    if (jantId != null) body['jant_id'] = jantId;
    if (colorId != null) body['color_id'] = colorId;
    if (paintLocation != null) body['paint_location'] = paintLocation;

    final response = await http
        .patch(
          Uri.parse('$baseUrl/modifications/$modificationId'),
          headers: headers,
          body: json.encode(body),
        )
        .timeout(_timeout);

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else if (response.statusCode == 402) {
      final d = json.decode(response.body);
      throw Exception(d['detail'] ?? 'Yetersiz kredi!');
    } else {
      String errMsg = 'Modifikasyon güncelleme hatası: ${response.statusCode}';
      try {
        final d = json.decode(response.body);
        if (d['detail'] != null) errMsg = d['detail'];
      } catch (_) {}
      throw Exception(errMsg);
    }
  }

  Future<List<Taslak>> taslaklariGetir() async {
    final headers = await _authHeaders();
    final response = await http
        .get(Uri.parse('$baseUrl/modifications/drafts'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      final List<dynamic> data = json.decode(response.body);
      return data.map((e) => Taslak.fromJson(e)).toList();
    } else {
      throw Exception('Taslak getirme hatası: ${response.statusCode}');
    }
  }

  // ═══════════════════════════════════════════════════
  //  TRIPO3D AI İŞLEMLERİ
  // ═══════════════════════════════════════════════════

  Future<Map<String, dynamic>> tripoHealthCheck() async {
    final response = await http
        .get(Uri.parse('$baseUrl/tripo/health'))
        .timeout(_timeout);

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Tripo3D sağlık kontrolü hatası: ${response.statusCode}');
    }
  }

  Future<Map<String, dynamic>> tripoGetBalance() async {
    final headers = await _authHeaders();
    final response = await http
        .get(Uri.parse('$baseUrl/tripo/balance'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Tripo3D bakiye sorgulama hatası: ${response.statusCode}');
    }
  }

  Future<Map<String, dynamic>> tripoGetCreditCosts() async {
    final headers = await _authHeaders();
    final response = await http
        .get(Uri.parse('$baseUrl/tripo/credits/costs'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Tripo3D kredi maliyeti sorgulama hatası: ${response.statusCode}');
    }
  }

  Future<String> tripoImageTo3D(int scanId, {String modelVersion = 'default'}) async {
    final headers = await _authHeaders(contentType: 'application/json');
    final response = await http
        .post(
          Uri.parse('$baseUrl/tripo/image-to-3d'),
          headers: headers,
          body: json.encode({
            'scan_id': scanId,
            'model_version': modelVersion,
          }),
        )
        .timeout(_timeout);

    if (response.statusCode == 202) {
      final data = json.decode(response.body);
      return data['task_id'];
    } else {
      throw Exception('Tripo3D image-to-3d hatası: ${response.statusCode}');
    }
  }

  Future<String> tripoMultiImageTo3D(int scanId, {String modelVersion = 'default'}) async {
    final headers = await _authHeaders(contentType: 'application/json');
    final response = await http
        .post(
          Uri.parse('$baseUrl/tripo/multi-image-to-3d'),
          headers: headers,
          body: json.encode({
            'scan_id': scanId,
            'model_version': modelVersion,
          }),
        )
        .timeout(_timeout);

    if (response.statusCode == 202) {
      final data = json.decode(response.body);
      return data['task_id'];
    } else {
      throw Exception('Tripo3D multi-image-to-3d hatası: ${response.statusCode}');
    }
  }

  Future<String> tripoTextTo3D(String prompt, {String modelVersion = 'default'}) async {
    final headers = await _authHeaders(contentType: 'application/json');
    final response = await http
        .post(
          Uri.parse('$baseUrl/tripo/text-to-3d'),
          headers: headers,
          body: json.encode({
            'prompt': prompt,
            'model_version': modelVersion,
          }),
        )
        .timeout(_timeout);

    if (response.statusCode == 202) {
      final data = json.decode(response.body);
      return data['task_id'];
    } else {
      throw Exception('Tripo3D text-to-3d hatası: ${response.statusCode}');
    }
  }

  Future<Map<String, dynamic>> tripoGetTaskStatus(String taskId) async {
    final headers = await _authHeaders();
    final response = await http
        .get(Uri.parse('$baseUrl/tripo/task/$taskId'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Tripo3D task durum hatası: ${response.statusCode}');
    }
  }

  // ═══════════════════════════════════════════════════
  //  HESAP SİLME
  // ═══════════════════════════════════════════════════

  Future<void> hesapSil() async {
    final headers = await _authHeaders();
    final response = await http
        .delete(Uri.parse('$baseUrl/users/me'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode != 200 && response.statusCode != 204) {
      throw Exception('Hesap silme hatası: ${response.statusCode}');
    }
  }

  // ═══════════════════════════════════════════════════
  //  TOPLULUKLA PAYLAŞMA
  // ═══════════════════════════════════════════════════

  Future<Map<String, dynamic>> toplulugaPaylas(int scanId) async {
    final headers = await _authHeaders();
    final response = await http
        .post(Uri.parse('$baseUrl/community/$scanId/share'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200 || response.statusCode == 201) {
      return json.decode(response.body);
    } else {
      throw Exception('Paylaşma hatası: ${response.statusCode}');
    }
  }

  Future<Map<String, dynamic>> kesfettenKaldir(int scanId) async {
    final headers = await _authHeaders();
    final response = await http
        .post(Uri.parse('$baseUrl/community/$scanId/unshare'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200 || response.statusCode == 201) {
      return json.decode(response.body);
    } else {
      throw Exception('Keşfetten kaldırma hatası: ${response.statusCode}');
    }
  }

  // ═══════════════════════════════════════════════════
  //  DAVET (REFERRAL) — +50 KREDİ
  // ═══════════════════════════════════════════════════

  Future<Map<String, dynamic>> davetPaylas() async {
    final headers = await _authHeaders();
    final response = await http
        .post(Uri.parse('$baseUrl/store/referral'), headers: headers)
        .timeout(_timeout);

    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Davet hatası: ${response.statusCode}');
    }
  }

  Future<List<Map<String, dynamic>>> oyunLiderlikTablosuGetir(String gameType) async {
    final headers = await _authHeaders();
    try {
      final response = await http
          .get(Uri.parse('$baseUrl/users/game/leaderboard?game_type=$gameType'), headers: headers)
          .timeout(_timeout);
      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        return data.cast<Map<String, dynamic>>();
      }
    } catch (_) {}
    return [];
  }

  Future<void> oyunSkoruKaydet(int skor, String gameType) async {
    final headers = await _authHeaders(contentType: 'application/json');
    try {
      await http.post(
        Uri.parse('$baseUrl/users/game/score'),
        headers: headers,
        body: json.encode({'score': skor, 'game_type': gameType}),
      ).timeout(_timeout);
    } catch (_) {}
  }
}