import 'dart:async';
import 'package:flutter/foundation.dart';
import 'servisler/api_servisi.dart';
import 'sayfalar_islem.dart';
import 'main.dart';
import 'package:flutter/material.dart';

/// Global render durumu yöneticisi.
/// Render sayfasından çıkılsa bile ilerleme durumu korunur
/// ve uygulama genelinde banner gösterilmesini sağlar.
/// 3D renderlar için arka planda API polling yapar.
class RenderDurumYonetici extends ChangeNotifier {
  // Singleton
  static final RenderDurumYonetici _instance = RenderDurumYonetici._internal();
  factory RenderDurumYonetici() => _instance;
  RenderDurumYonetici._internal();

  bool _aktifMi = false;
  double _ilerleme = 0.0;
  bool _tamamlandi = false;
  String _arabaAdi = '';
  String _method = '2d';
  int? _scanId;

  // Render sayfası aktif mi (banner'ı gizlemek için)
  bool _renderSayfasiAcik = false;

  // Arka plan polling timer'ı
  Timer? _pollTimer;

  bool get aktifMi => _aktifMi;
  double get ilerleme => _ilerleme;
  bool get tamamlandi => _tamamlandi;
  String get arabaAdi => _arabaAdi;
  String get method => _method;
  int? get scanId => _scanId;
  bool get renderSayfasiAcik => _renderSayfasiAcik;

  /// Banner gösterilmeli mi? (Render aktif + sayfada değiliz)
  bool get bannerGoster => _aktifMi && !_renderSayfasiAcik;

  void renderBaslat({
    required String arabaAdi,
    required String method,
    int? scanId,
  }) {
    _aktifMi = true;
    _ilerleme = 0.0;
    _tamamlandi = false;
    _arabaAdi = arabaAdi;
    _method = method;
    _scanId = scanId;
    _renderSayfasiAcik = true;
    notifyListeners();
  }

  void ilerlemeGuncelle(double deger) {
    _ilerleme = deger;
    notifyListeners();
  }

  void renderTamamla() {
    _tamamlandi = true;
    _ilerleme = 1.0;
    _pollTimer?.cancel();
    _pollTimer = null;
    
    // Yüzen ekranın kaybolması için render durumunu sıfırlayalım
    _aktifMi = false; 
    
    notifyListeners();

    // Global olarak Toast / SnackBar gösterelim
    final context = navigatorKey.currentContext;
    if (context != null) {
      ScaffoldMessenger.of(context).clearSnackBars();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.check_circle, color: Colors.white),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  _arabaAdi.isNotEmpty 
                      ? '$_arabaAdi modelinin üretimi tamamlandı! Modifikasyon stüdyosu hazır.'
                      : 'Aracınızın üretimi tamamlandı! Modifikasyon stüdyosu hazır.',
                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          backgroundColor: Colors.green,
          behavior: SnackBarBehavior.floating,
          duration: const Duration(seconds: 6),
          action: SnackBarAction(
            label: 'Modifiye Et',
            textColor: Colors.white,
            onPressed: () {
              navigatorKey.currentState?.push(
                MaterialPageRoute(
                  builder: (context) => ModifiyeSecimSayfasi(
                    scanId: _scanId,
                    carName: _arabaAdi,
                    method: _method,
                  ),
                ),
              );
            },
          ),
        ),
      );
    }
  }

  /// Backend veya simüle edilmiş progress durumunu kontrol eder ve periyodik olarak günceller.
  /// Render sayfası kapansa bile arka planda çalışmaya devam eder.
  void startPolling(int scanId, String method) {
    // Zaten aynı tarama için aktif bir timer varsa ve tamamlanmadıysa polling'i sürdür, sıfırlama!
    if (_pollTimer != null && _scanId == scanId && _method == method && !_tamamlandi) {
      _renderSayfasiAcik = true;
      notifyListeners();
      return;
    }

    _pollTimer?.cancel();
    _scanId = scanId;
    _method = method;
    _ilerleme = 0.0;
    _tamamlandi = false;
    _renderSayfasiAcik = true;

    // Hemen ilk kontrolü asenkron olarak başlat (0% takılmasını önlemek için)
    _tekilKontrol(scanId, method);

    // Her 5 saniyede bir backend'i kontrol et ve arayüzü ilerlet
    _pollTimer = Timer.periodic(const Duration(seconds: 5), (timer) async {
      await _tekilKontrol(scanId, method);
    });
  }

  Future<void> _tekilKontrol(int scanId, String method) async {
    try {
      final scan = await ApiServisi().scanDetayGetir(scanId);

      if (scan.isCompleted) {
        _pollTimer?.cancel();
        _pollTimer = null;
        renderTamamla();
        return;
      } else if (scan.status == 'failed') {
        _pollTimer?.cancel();
        _pollTimer = null;
        return;
      }

      // Kademeli artış hesaplama
      double yeniIlerleme = _ilerleme;
      if (method == '2d') {
        // 2D için simüle artış adımları (Maksimum %95'e kadar her adımda %20)
        yeniIlerleme = (_ilerleme + 0.20).clamp(0.0, 0.95);
      } else {
        // 3D için simüle artış adımları (Maksimum %95'e kadar her adımda %3)
        final apiProgress = (scan.progress).clamp(0, 100) / 100.0;
        if (apiProgress > _ilerleme) {
          yeniIlerleme = apiProgress;
        } else {
          yeniIlerleme = (_ilerleme + 0.03).clamp(0.0, 0.95);
        }
      }

      if (yeniIlerleme > _ilerleme && !_tamamlandi) {
        ilerlemeGuncelle(yeniIlerleme);
      }
    } catch (e) {
      debugPrint('Singleton scan poll hatası: $e');
      
      // Hata durumunda bile progress bar'ı ilerlet (kullanıcıya takılı hissettirmemek için)
      double yeniIlerleme = _ilerleme;
      if (method == '2d') {
        yeniIlerleme = (_ilerleme + 0.20).clamp(0.0, 0.95);
      } else {
        yeniIlerleme = (_ilerleme + 0.03).clamp(0.0, 0.95);
      }
      
      if (yeniIlerleme > _ilerleme && !_tamamlandi) {
        ilerlemeGuncelle(yeniIlerleme);
      }
    }
  }

  void renderSayfasiAcildi() {
    _renderSayfasiAcik = true;
    notifyListeners();
  }

  void renderSayfasiKapandi() {
    _renderSayfasiAcik = false;
    notifyListeners();
  }

  void sifirla() {
    _pollTimer?.cancel();
    _pollTimer = null;
    _aktifMi = false;
    _ilerleme = 0.0;
    _tamamlandi = false;
    _arabaAdi = '';
    _method = '2d';
    _scanId = null;
    _renderSayfasiAcik = false;
    notifyListeners();
  }
}
