import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'dart:async';
import 'dart:math';
import 'sistem_ve_dil.dart';
import 'sayfalar_ana.dart';
import 'sayfalar_islem.dart';
import 'sekme_bildirim.dart';
import 'servisler/api_servisi.dart';
import 'modeller/community_model.dart';
import 'render_state.dart';

// --- RENDER (İŞLENİYOR) VE OYUN SAYFASI ---
class RenderSayfasi extends StatefulWidget {
  final String carName;
  final String method;
  final int? scanId;
  const RenderSayfasi({super.key, this.carName = '', this.method = '2d', this.scanId});

  @override
  State<RenderSayfasi> createState() => _RenderSayfasiState();
}

class _RenderSayfasiState extends State<RenderSayfasi>
    with SingleTickerProviderStateMixin {
  static const int RENDER_SURE_2D = 60; // saniye
  static const int RENDER_SURE_3D = 180; // saniye

  late AnimationController _animasyonKontrolcusu;
  late final int _toplamSureSaniye;

  // Scan Status Değişkenleri
  bool _scanHata = false;

  List<Map<String, dynamic>> _carLeaderboard = [];
  List<Map<String, dynamic>> _birdLeaderboard = [];
  List<FeedItem> _exploreItems = [];
  String _kusKaybetmeNedeni = '';
  double _accumulatedDrag = 0.0;
  bool _dragConsumed = false;

  int _enIyiSkor = 0;
  int _oyunSkoru = 0;
  Timer? _oyunZamanlayicisi;
  bool _oyunAktif = true;
  bool _oyunBitti = false;

  bool _nitroAktif = false;
  bool _kilPayiGoster = false;

  String _renderDurumMesaji = '';
  int _durumMesajIndex = 0;
  Timer? _durumMesajTimer;

  // Eski araba oyunu değişkenleri
  int _arabaSeridi = 1; // 0: Sol, 1: Orta, 2: Sağ
  double _yolCizgisiY = 0.0;
  double _trafikY = -1.0;
  int _trafikSeridi = 1;
  final List<String> _trafikAraclari = ['🚓', '🚕', '🚙', '🚑', '🚒', '🏍️'];
  String _secilenTrafikAraci = '🚕';
  double _nitroY = -1.5;
  int _nitroSeridi = 0;
  double _trafikHiz = 0.025;
  Timer? _kilPayiTimer;

  // ======== OYUN SEÇİCİ ========
  bool _kusOyunuSecili = false; // false = araba, true = kuş

  // ======== FLAPPY BIRD DEĞİŞKENLERİ ========
  double _kusY = 0.0; // -1.0 ile 1.0 arası (ekran ortası = 0)
  double _kusHiz = 0.0; // dikey hız
  static const double _yercekimi = 0.0025;
  static const double _ziplamGuc = -0.045;
  int _kusSkoru = 0;
  int _kusEnIyiSkor = 0;
  bool _kusOyunuBitti = false;
  bool _kusOyunuBasladi = false;
  Timer? _kusOyunZamanlayicisi;

  // Borular
  List<_BoruCifti> _borular = [];
  double _boruHiz = 0.015;
  double _boruOlusturmaZamani = 0;
  static const double _boruGenislik = 0.12; // normalized genişlik
  static const double _boruBosluk = 0.35; // boru arasındaki boşluk (normalized)

  // Bonus göster
  bool _kusDodgeGoster = false;

  // Arkaplan paralaks
  double _arkaplanOffset = 0.0;

  @override
  void initState() {
    super.initState();
    _toplamSureSaniye = widget.method == '2d' ? RENDER_SURE_2D : RENDER_SURE_3D;
    _animasyonKontrolcusu = AnimationController(
      vsync: this,
      duration: Duration(seconds: _toplamSureSaniye),
    );
    _animasyonKontrolcusu.forward();
    
    // Global render state başlat
    RenderDurumYonetici().renderBaslat(
      arabaAdi: widget.carName,
      method: widget.method,
      scanId: widget.scanId,
    );
    _oyunuBaslat();
    _renderDurumMesajlariniBaslat();
    _exploreYukle();
    _liderlikYukle();

    // Hem 2D hem 3D için: singleton'da arka plan polling/timer başlat ve dinleyici ekle
    RenderDurumYonetici().startPolling(widget.scanId ?? 0, widget.method);
    RenderDurumYonetici().addListener(_renderYoneticiDinleyici);
  }

  void _renderYoneticiDinleyici() {
    if (!mounted) return;
    setState(() {});
    
    if (RenderDurumYonetici().tamamlandi) {
      RenderDurumYonetici().removeListener(_renderYoneticiDinleyici);
      
      if (titresimAcik.value) HapticFeedback.mediumImpact();
      final currentScanId = RenderDurumYonetici().scanId;
      final currentCarName = RenderDurumYonetici().arabaAdi;
      final currentMethod = RenderDurumYonetici().method;
      
      RenderDurumYonetici().sifirla();
      
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (c) => ModifiyeSecimSayfasi(
            scanId: currentScanId,
            carName: currentCarName,
            method: currentMethod,
          ),
        ),
      );
    }
  }


  Future<void> _exploreYukle() async {
    try {
      final items = await ApiServisi().exploreTopGetir();
      if (mounted) {
        setState(() {
          _exploreItems = items;
        });
      }
    } catch (_) {}
  }

  Future<void> _liderlikYukle() async {
    try {
      final carL = await ApiServisi().oyunLiderlikTablosuGetir('car_racing');
      final birdL = await ApiServisi().oyunLiderlikTablosuGetir('fly_bird');
      if (mounted) {
        setState(() {
          _carLeaderboard = carL;
          _birdLeaderboard = birdL;
        });
      }
    } catch (_) {}
  }

  // ========== ARABA OYUNU ==========
  void _oyunuBaslat() {
    // BUG-24 FIX: Önceki timer'ı iptal et (çift game loop önlemi)
    _oyunZamanlayicisi?.cancel();
    _kilPayiTimer?.cancel();
    _oyunAktif = true;
    _oyunBitti = false;
    _oyunSkoru = 0;
    _arabaSeridi = 1;
    _yolCizgisiY = 0.0;
    _trafikY = -1.0;
    _trafikSeridi = Random().nextInt(3);
    _secilenTrafikAraci = _trafikAraclari[Random().nextInt(_trafikAraclari.length)];
    _nitroAktif = false;
    _kilPayiGoster = false;
    _nitroY = -1.5;
    _nitroSeridi = Random().nextInt(3);
    _trafikHiz = 0.015;

    _oyunZamanlayicisi = Timer.periodic(const Duration(milliseconds: 30), (timer) {
      if (!mounted || !_oyunAktif || _oyunBitti) return;
      setState(() {
        // Yol çizgisi animasyonu
        _yolCizgisiY += _nitroAktif ? 0.042 : 0.03;
        if (_yolCizgisiY >= 1.0) _yolCizgisiY = 0.0;

        // Trafik aracı hareketi
        double currentSpeed = _nitroAktif ? _trafikHiz * 1.4 : _trafikHiz;
        _trafikY += currentSpeed;

        // Nitro hareketi
        if (_nitroY > -1.5) {
          _nitroY += currentSpeed;
          if (_nitroY > 1.3) _nitroY = -1.5;
        }

        // Trafik aracı ekrandan çıktı → yeni oluştur
        if (_trafikY > 1.3) {
          _trafikY = -1.0;
          _trafikSeridi = Random().nextInt(3);
          _secilenTrafikAraci = _trafikAraclari[Random().nextInt(_trafikAraclari.length)];
          _oyunSkoru += 10;
          // Her 50 puan hızı artır
          _trafikHiz = (0.015 + (_oyunSkoru * 0.0003)).clamp(0.015, 0.055);
          // %25 ihtimalle nitro spawn et
          if (_nitroY <= -1.5 && Random().nextDouble() < 0.25) {
            _nitroY = -1.0;
            _nitroSeridi = (_trafikSeridi + 1 + Random().nextInt(2)) % 3;
          }
        }

        // Nitro toplama kontrolü
        if (_nitroY > -1.5 && _arabaSeridi == _nitroSeridi && (_nitroY - 0.80).abs() < 0.15) {
          _nitroAktif = true;
          _nitroY = -1.5;
          if (titresimAcik.value) HapticFeedback.mediumImpact();
          Future.delayed(const Duration(seconds: 3), () {
            if (mounted) setState(() => _nitroAktif = false);
          });
        }

        // Kıl payı: aynı Y seviyesinde yan şeritte
        if (!_kilPayiGoster && (_trafikY - 0.80).abs() < 0.15 && (_arabaSeridi - _trafikSeridi).abs() == 1) {
          _kilPayiGoster = true;
          _oyunSkoru += 50;
          if (titresimAcik.value) HapticFeedback.lightImpact();
          _kilPayiTimer = Timer(const Duration(milliseconds: 900), () {
            if (mounted) setState(() => _kilPayiGoster = false);
          });
        }

        // Çarpışma kontrolü (oyuncu Y=0.80)
        if (_arabaSeridi == _trafikSeridi && (_trafikY - 0.80).abs() < 0.15) {
          _oyunBitir();
        }
      });
    });
  }

  void _oyunBitir() {
    if (titresimAcik.value) HapticFeedback.heavyImpact();
    _oyunBitti = true;
    if (_oyunSkoru > _enIyiSkor) _enIyiSkor = _oyunSkoru;
    _oyunZamanlayicisi?.cancel();
    ApiServisi().oyunSkoruKaydet(_oyunSkoru, "car_racing").then((_) => _liderlikYukle());
  }

  // ========== KUŞ OYUNU ==========
  void _kusOyunuBaslat() {
    _kusOyunZamanlayicisi?.cancel();
    _kusY = 0.0;
    _kusHiz = 0.0;
    _kusSkoru = 0;
    _kusOyunuBitti = false;
    _kusOyunuBasladi = false;
    _borular = [];
    _boruHiz = 0.015;
    _boruOlusturmaZamani = 0;
    _kusDodgeGoster = false;
    _arkaplanOffset = 0.0;
    _kusKaybetmeNedeni = '';

    _kusOyunZamanlayicisi = Timer.periodic(const Duration(milliseconds: 16), (timer) {
      if (!mounted) return;
      if (!_kusOyunuBasladi || _kusOyunuBitti) {
        // Sadece arkaplanı hareket ettir
        setState(() {
          _arkaplanOffset += 0.0005;
        });
        return;
      }
      setState(() {
        // Yerçekimi uygula
        _kusHiz += _yercekimi;
        _kusY += _kusHiz;

        // Arkaplan paralaks
        _arkaplanOffset += 0.002;

        // Tavan ve zemine çarpışma
        if (_kusY > 0.85) {
          _kusY = 0.85;
          _kusKaybetmeNedeni = t('bird_game_over_fell');
          _kusOyunuBitir();
          return;
        }
        if (_kusY < -0.90) {
          _kusKaybetmeNedeni = t('bird_game_over_burnt');
          _kusOyunuBitir();
          return;
        }

        // Boru hareketi
        _boruOlusturmaZamani += 1;
        // Her ~120 frame'de yeni boru çifti oluştur
        if (_boruOlusturmaZamani >= 120) {
          _boruOlusturmaZamani = 0;
          double gapCenter = -0.4 + Random().nextDouble() * 0.8; // -0.4 ile 0.4 arası
          _borular.add(_BoruCifti(
            x: 1.2,
            gapCenter: gapCenter,
            gecildi: false,
          ));
        }

        // Boruları hareket ettir ve geçiş kontrolü
        for (int i = _borular.length - 1; i >= 0; i--) {
          _borular[i].x -= _boruHiz;

          // Ekrandan çıkan boruları sil (Smooth offscreen removal)
          if (_borular[i].x < -1.3) {
            _borular.removeAt(i);
            continue;
          }

          // Kuşun boruyu geçip geçmediğini kontrol et
          double kusBurunX = 0.0; // kuş ekranın ~%35'inde sabit
          if (!_borular[i].gecildi && _borular[i].x + _boruGenislik / 2 < kusBurunX) {
            _borular[i].gecildi = true;
            _kusSkoru++;
            if (titresimAcik.value) HapticFeedback.lightImpact();

            // Her 5 puanda bonus göster
            if (_kusSkoru % 5 == 0) {
              _kusDodgeGoster = true;
              Timer(const Duration(milliseconds: 600), () {
                if (mounted) setState(() => _kusDodgeGoster = false);
              });
            }

            // Hızı artır
            _boruHiz = (0.015 + (_kusSkoru * 0.0005)).clamp(0.015, 0.04);
          }

          // Çarpışma kontrolü
          double boruSolX = _borular[i].x - _boruGenislik / 2;
          double boruSagX = _borular[i].x + _boruGenislik / 2;

          if (kusBurunX > boruSolX - 0.02 && kusBurunX < boruSagX + 0.01) {
            double ustBoruAlt = _borular[i].gapCenter - _boruBosluk / 2;
            double altBoruUst = _borular[i].gapCenter + _boruBosluk / 2;

            if (_kusY < ustBoruAlt + 0.03 || _kusY > altBoruUst - 0.03) {
              _kusKaybetmeNedeni = t('bird_game_over_pipe');
              _kusOyunuBitir();
              return;
            }
          }
        }
      });
    });
  }

  void _kusZipla() {
    if (_kusOyunuBitti) return;
    if (!_kusOyunuBasladi) {
      _kusOyunuBasladi = true;
    }
    if (titresimAcik.value) HapticFeedback.lightImpact();
    setState(() {
      _kusHiz = _ziplamGuc;
    });
  }

  void _kusOyunuBitir() {
    if (titresimAcik.value) HapticFeedback.heavyImpact();
    _kusOyunuBitti = true;
    if (_kusSkoru > _kusEnIyiSkor) _kusEnIyiSkor = _kusSkoru;
    _kusOyunZamanlayicisi?.cancel();
    ApiServisi().oyunSkoruKaydet(_kusSkoru, "fly_bird").then((_) => _liderlikYukle());
  }

  @override
  void dispose() {
    _oyunZamanlayicisi?.cancel();
    _kilPayiTimer?.cancel();
    _durumMesajTimer?.cancel();
    _kusOyunZamanlayicisi?.cancel();
    RenderDurumYonetici().removeListener(_renderYoneticiDinleyici);
    _animasyonKontrolcusu.dispose();
    // Render sayfası kapandığında banner görünsün
    RenderDurumYonetici().renderSayfasiKapandi();
    super.dispose();
  }

  // Task 7: 10 saniye arayla render durum mesajlarını göster
  void _renderDurumMesajlariniBaslat() {
    final mesajlar = [
      t('render_status_1'),
      t('render_status_2'),
      t('render_status_3'),
      t('render_status_4'),
      t('render_status_5'),
      t('render_status_6'),
    ];
    _renderDurumMesaji = mesajlar[0];
    _durumMesajIndex = 0;

    _durumMesajTimer = Timer.periodic(const Duration(seconds: 10), (timer) {
      if (!mounted || RenderDurumYonetici().tamamlandi) {
        timer.cancel();
        return;
      }
      setState(() {
        _durumMesajIndex = (_durumMesajIndex + 1) % mesajlar.length;
        _renderDurumMesaji = mesajlar[_durumMesajIndex];
      });
    });
  }

  // Oyun değiştirme
  void _oyunDegistir(bool kusOyunu) {
    if (_kusOyunuSecili == kusOyunu) return;
    setState(() {
      _kusOyunuSecili = kusOyunu;
    });
    if (kusOyunu) {
      _oyunZamanlayicisi?.cancel();
      _kusOyunuBaslat();
    } else {
      _kusOyunZamanlayicisi?.cancel();
      _oyunuBaslat();
    }
  }

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<String>(
      valueListenable: appLanguage,
      builder: (context, lang, child) {
        final Color anaRenk = const Color(0xFF257bf4);
        final Color koyuArkaplan = arkaplanRengi();
        final Color koyuYuzey = yuzeyRengi();
        final manager = RenderDurumYonetici();
        double progressVal = manager.ilerleme;
        int yuzde = (progressVal * 100).toInt();
        bool islemBittiMi = manager.tamamlandi;
        int gecenSaniye = (progressVal * _toplamSureSaniye).toInt();
        int kalanSaniye = _toplamSureSaniye - gecenSaniye;

        return Scaffold(
          backgroundColor: koyuArkaplan,
          body: SafeArea(
            child: Column(
              children: [
                // Geri / Minimize butonu
                Padding(
                  padding: const EdgeInsets.only(left: 10.0, right: 20.0, top: 10.0, bottom: 5.0),
                  child: Row(
                    children: [
                      IconButton(
                        icon: const Icon(Icons.arrow_back_ios_new, color: Colors.white, size: 20),
                        onPressed: () {
                          if (titresimAcik.value) HapticFeedback.lightImpact();
                          RenderDurumYonetici().renderSayfasiKapandi();
                          Navigator.of(context).pop();
                        },
                      ),
                      const SizedBox(width: 8),
                      Text(
                        t('ai_studio'),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),
                // Üst progress bar + AI işliyor
                Padding(
                  padding: const EdgeInsets.all(20.0),
                  child: GestureDetector(
                    onTap: islemBittiMi
                        ? () {
                            if (titresimAcik.value) HapticFeedback.mediumImpact();
                            final currentScanId = RenderDurumYonetici().scanId;
                            final currentCarName = RenderDurumYonetici().arabaAdi;
                            final currentMethod = RenderDurumYonetici().method;
                            RenderDurumYonetici().sifirla();
                            Navigator.pushReplacement(
                              context,
                              MaterialPageRoute(
                                builder: (context) => ModifiyeSecimSayfasi(
                                  scanId: currentScanId,
                                  carName: currentCarName,
                                  method: currentMethod,
                                ),
                              ),
                            );
                          }
                        : null,
                    child: Container(
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(
                        color: koyuYuzey,
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(
                          color: islemBittiMi
                              ? Colors.green.withValues(alpha: 0.5)
                              : Colors.white.withValues(alpha: 0.05),
                        ),
                        boxShadow: islemBittiMi
                            ? [
                                BoxShadow(
                                  color: Colors.green.withValues(alpha: 0.2),
                                  blurRadius: 12,
                                ),
                              ]
                            : [],
                      ),
                      child: Column(
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Flexible(
                                child: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(
                                      islemBittiMi
                                          ? Icons.check_circle
                                          : Icons.memory,
                                      color: islemBittiMi
                                          ? Colors.green
                                          : anaRenk,
                                    ),
                                    const SizedBox(width: 8),
                                    Flexible(
                                      child: Text(
                                        islemBittiMi
                                            ? t('render_done_banner')
                                            : t('ai_processing'),
                                        style: TextStyle(
                                          color: Colors.white,
                                          fontWeight: FontWeight.bold,
                                          fontSize: islemBittiMi ? 13 : 14,
                                        ),
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                              Text(
                                '%$yuzde',
                                style: premiumNumberStyle.copyWith(
                                  color: islemBittiMi ? Colors.green : anaRenk,
                                  fontSize: 18,
                                ),
                              ),
                            ],
                          ),
                          if (!islemBittiMi) ...[
                            const SizedBox(height: 6),
                            AnimatedSwitcher(
                              duration: const Duration(milliseconds: 500),
                              child: Text(
                                _renderDurumMesaji.isNotEmpty ? _renderDurumMesaji : t('ai_processing_desc'),
                                key: ValueKey<String>(_renderDurumMesaji),
                                style: const TextStyle(
                                  color: Colors.grey,
                                  fontSize: 11,
                                ),
                              ),
                            ),
                          ],
                          const SizedBox(height: 12),
                          LinearProgressIndicator(
                            value: progressVal,
                            minHeight: 6,
                            backgroundColor: Colors.grey.shade800,
                            valueColor: AlwaysStoppedAnimation<Color>(
                              islemBittiMi ? Colors.green : anaRenk,
                            ),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          const SizedBox(height: 12),
                          if (islemBittiMi)
                            Align(
                              alignment: Alignment.centerRight,
                              child: Text(
                                t('render_done_banner'),
                                style: premiumNumberStyle.copyWith(
                                  color: Colors.green,
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                ),

                // ======== OYUN SEÇİCİ ========
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20.0),
                  child: Container(
                    decoration: BoxDecoration(
                      color: koyuYuzey,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
                    ),
                    padding: const EdgeInsets.all(4),
                    child: Row(
                      children: [
                        Expanded(
                          child: GestureDetector(
                            onTap: () => _oyunDegistir(false),
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 250),
                              padding: const EdgeInsets.symmetric(vertical: 10),
                              decoration: BoxDecoration(
                                color: !_kusOyunuSecili
                                    ? anaRenk.withValues(alpha: 0.2)
                                    : Colors.transparent,
                                borderRadius: BorderRadius.circular(10),
                                border: !_kusOyunuSecili
                                    ? Border.all(color: anaRenk.withValues(alpha: 0.5))
                                    : null,
                              ),
                              child: Center(
                                child: Text(
                                  t('car_game'),
                                  style: TextStyle(
                                    color: !_kusOyunuSecili ? Colors.white : Colors.grey,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 13,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 4),
                        Expanded(
                          child: GestureDetector(
                            onTap: () => _oyunDegistir(true),
                            child: AnimatedContainer(
                              duration: const Duration(milliseconds: 250),
                              padding: const EdgeInsets.symmetric(vertical: 10),
                              decoration: BoxDecoration(
                                color: _kusOyunuSecili
                                    ? const Color(0xFF4CAF50).withValues(alpha: 0.2)
                                    : Colors.transparent,
                                borderRadius: BorderRadius.circular(10),
                                border: _kusOyunuSecili
                                    ? Border.all(color: const Color(0xFF4CAF50).withValues(alpha: 0.5))
                                    : null,
                              ),
                              child: Center(
                                child: Text(
                                  t('bird_game'),
                                  style: TextStyle(
                                    color: _kusOyunuSecili ? Colors.white : Colors.grey,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 13,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

                const SizedBox(height: 12),

                // Oyun alanı
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20.0),
                    child: _kusOyunuSecili
                        ? _kusOyunuWidget(anaRenk, islemBittiMi)
                        : _arabaOyunuWidget(anaRenk, islemBittiMi),
                  ),
                ),

                const SizedBox(height: 20),

                // Topluluğun Efsaneleri - basınca keşfete gitsin
                GestureDetector(
                  onTap: () {
                    if (titresimAcik.value) HapticFeedback.lightImpact();
                    RenderDurumYonetici().renderSayfasiKapandi();
                    Navigator.pushAndRemoveUntil(
                      context,
                      MaterialPageRoute(
                        builder: (c) => const AnaSayfa(initialIndex: 2),
                      ),
                      (r) => false,
                    );
                  },
                  child: Container(
                    padding: const EdgeInsets.only(
                      left: 20,
                      top: 10,
                      bottom: 20,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          t('community_legends'),
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 12),
                        SizedBox(
                          height: 110,
                          child: _exploreItems.isEmpty
                              ? const Center(child: Text('Keşfedilecek araç bulunamadı.', style: TextStyle(color: Colors.grey, fontSize: 12)))
                              : ListView.builder(
                                  scrollDirection: Axis.horizontal,
                                  itemCount: _exploreItems.length,
                                  itemBuilder: (context, index) {
                                    final item = _exploreItems[index];
                                    final thumb = ApiServisi.buildImageUrl(item.thumbnailUrl) ?? 'https://images.unsplash.com/photo-1603386329225-868f9b1ee6c9?q=80&w=1000';
                                    return Padding(
                                      padding: const EdgeInsets.only(right: 12.0),
                                      child: _vitrinKartiOlustur(
                                        thumb,
                                        item.ownerName,
                                        item.carName,
                                      ),
                                    );
                                  },
                                ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  // ========== ARABA OYUNU WİDGETI ==========
  Widget _arabaOyunuWidget(Color anaRenk, bool islemBittiMi) {
    return GestureDetector(
      onTapDown: (details) {
        if (!mounted || !_oyunAktif) return;
        if (_oyunBitti) {
          if (RenderDurumYonetici().tamamlandi) return;
          _oyunuBaslat();
          return;
        }
        // Gameplay lane changes are handled by horizontal drag/swipe gestures!
      },
      onHorizontalDragStart: (details) {
        _accumulatedDrag = 0.0;
        _dragConsumed = false;
      },
      onHorizontalDragUpdate: (details) {
        if (!mounted || !_oyunAktif || _oyunBitti || _dragConsumed) return;
        _accumulatedDrag += details.delta.dx;
        const double threshold = 40.0;
        if (_accumulatedDrag.abs() >= threshold) {
          if (titresimAcik.value) HapticFeedback.lightImpact();
          setState(() {
            if (_accumulatedDrag < 0) {
              if (_arabaSeridi > 0) _arabaSeridi--;
            } else {
              if (_arabaSeridi < 2) _arabaSeridi++;
            }
          });
          _dragConsumed = true;
        }
      },
      child: Container(
        decoration: BoxDecoration(
          color: const Color(0xFF0F172A),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: Colors.white.withValues(alpha: 0.1),
            width: 2,
          ),
          boxShadow: [
            BoxShadow(
              color: anaRenk.withValues(alpha: 0.15),
              blurRadius: 15,
              spreadRadius: 2,
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: Stack(
            children: [
              // Yol arka planı
              Positioned.fill(
                child: Container(
                  color: const Color(0xFF1A2332),
                ),
              ),

              // Animasyonlu yol çizgileri (3 adet)
              ...[0, 1, 2].map((lane) {
                final laneX = lane == 0 ? -0.33 : (lane == 1 ? 0.33 : 0.0);
                return const SizedBox.shrink();
              }),

              // Sol şerit çizgisi (animasyonlu)
              Positioned(
                left: 0, right: 0, top: 0, bottom: 0,
                child: CustomPaint(
                  painter: _YolCizgisiPainter(
                    offset: _yolCizgisiY,
                    nitroAktif: _nitroAktif,
                  ),
                ),
              ),

              // Trafik aracı
              if (!_oyunBitti) Align(
                alignment: Alignment(
                  _trafikSeridi == 0 ? -0.6 : (_trafikSeridi == 1 ? 0.0 : 0.6),
                  _trafikY,
                ),
                child: Text(
                  _secilenTrafikAraci,
                  style: const TextStyle(fontSize: 48),
                ),
              ),

              // Nitro paketi
              if (!_oyunBitti && _nitroY > -1.5) Align(
                alignment: Alignment(
                  _nitroSeridi == 0 ? -0.6 : (_nitroSeridi == 1 ? 0.0 : 0.6),
                  _nitroY,
                ),
                child: const Text('⚡', style: TextStyle(fontSize: 38)),
              ),

              // Oyuncu arabası
              if (!_oyunBitti) Align(
                alignment: Alignment(
                  _arabaSeridi == 0 ? -0.6 : (_arabaSeridi == 1 ? 0.0 : 0.6),
                  0.80,
                ),
                child: Text(
                  '🏎️',
                  style: const TextStyle(fontSize: 52),
                ),
              ),

              // Nitro aktif ise alev efekti
              if (_nitroAktif && !_oyunBitti) Align(
                alignment: Alignment(
                  _arabaSeridi == 0 ? -0.6 : (_arabaSeridi == 1 ? 0.0 : 0.6),
                  0.96,
                ),
                child: const Text('🔥', style: TextStyle(fontSize: 28)),
              ),

              // Kıl payı yazısı
              if (_kilPayiGoster && !_oyunBitti) Align(
                alignment: const Alignment(0, 0.3),
                child: Text(
                  t('close_call'),
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.orangeAccent,
                    fontSize: 32,
                    fontWeight: FontWeight.bold,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ),

              // İlk oyun talimatı
              if (_oyunSkoru == 0 && !_oyunBitti) Align(
                alignment: const Alignment(0, -0.3),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.touch_app, color: Colors.white.withValues(alpha: 0.6), size: 40),
                    const SizedBox(height: 8),
                    Text(
                      'Şerit değiştirmek için sola/sağa kaydır!',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.6),
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),

              // Skor göstergesi
              Positioned(
                top: 16, left: 16,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(12)),
                      child: Text('${t('score')}$_oyunSkoru', style: premiumNumberStyle.copyWith(color: Colors.yellow, fontSize: 16)),
                    ),
                    const SizedBox(height: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(12)),
                      child: Text('${t('best')}$_enIyiSkor', style: premiumNumberStyle.copyWith(color: Colors.white, fontSize: 11)),
                    ),
                  ],
                ),
              ),

              // Nitro aktif göstergesi
              if (_nitroAktif && !_oyunBitti) Positioned(
                top: 16, right: 16,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.deepOrangeAccent,
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(color: Colors.deepOrange.withValues(alpha: 0.5), blurRadius: 8),
                    ],
                  ),
                  child: const Text('⚡ NİTRO!', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13)),
                ),
              ),

              // Oyun bitti overlay
              if (_oyunBitti) Container(
                color: Colors.black.withValues(alpha: 0.85),
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        islemBittiMi ? t('render_done_text') : t('crashed'),
                        style: TextStyle(
                          color: islemBittiMi ? Colors.green : Colors.redAccent,
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${t('score')}$_oyunSkoru',
                        style: premiumNumberStyle.copyWith(color: Colors.white, fontSize: 16),
                      ),
                      const SizedBox(height: 12),
                      if (!islemBittiMi)
                        ElevatedButton.icon(
                          onPressed: () {
                            if (titresimAcik.value) HapticFeedback.mediumImpact();
                            _oyunuBaslat();
                          },
                          icon: const Icon(Icons.refresh, color: Colors.white, size: 18),
                          label: Text(t('play_again'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13)),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: anaRenk,
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          ),
                        )
                      else
                        ElevatedButton.icon(
                          onPressed: () {
                            if (titresimAcik.value) HapticFeedback.mediumImpact();
                            RenderDurumYonetici().sifirla();
                            Navigator.pushReplacement(
                              context,
                              MaterialPageRoute(builder: (c) => const AnaSayfa(initialIndex: 1)),
                            );
                          },
                          icon: const Icon(Icons.garage, color: Colors.white, size: 18),
                          label: Text(t('return_garage'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13)),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.green,
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          ),
                        ),
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.05),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          children: [
                            Text(t('top_of_week'), style: const TextStyle(color: Colors.grey, fontWeight: FontWeight.bold, fontSize: 13)),
                            const SizedBox(height: 6),
                            if (_carLeaderboard.isEmpty)
                              ...List.generate(3, (i) => Text('${i + 1}. ${t('coming_soon')}', style: const TextStyle(color: Colors.grey, fontSize: 11)))
                            else
                              ..._carLeaderboard.take(3).toList().asMap().entries.map((entry) {
                                final idx = entry.key + 1;
                                final item = entry.value;
                                return Text('$idx. ${item['username']} - ${item['score']}', style: const TextStyle(color: Colors.white, fontSize: 11));
                              }),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ========== KUŞ OYUNU WİDGETI ==========
  Widget _kusOyunuWidget(Color anaRenk, bool islemBittiMi) {
    return GestureDetector(
      onTapDown: (_) {
        if (_kusOyunuBitti) {
          if (islemBittiMi) return;
          _kusOyunuBaslat();
          // İlk dokunuşta otomatik zıplasın
          Future.microtask(() => _kusZipla());
        } else {
          _kusZipla();
        }
      },
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: Colors.white.withValues(alpha: 0.1),
            width: 2,
          ),
          boxShadow: [
            BoxShadow(
              color: const Color(0xFF4CAF50).withValues(alpha: 0.15),
              blurRadius: 15,
              spreadRadius: 2,
            ),
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: Stack(
            children: [
              // Gökyüzü gradient arka plan
              Positioned.fill(
                child: CustomPaint(
                  painter: _GokyuzuPainter(offset: _arkaplanOffset),
                ),
              ),

              // Zemin
              Positioned(
                left: 0,
                right: 0,
                bottom: 0,
                height: 40,
                child: CustomPaint(
                  painter: _ZeminPainter(offset: _arkaplanOffset),
                ),
              ),

              // Borular
              ..._borular.map((boru) {
                return _boruWidget(boru);
              }),

              // Kuş
              if (!_kusOyunuBitti)
                Align(
                  alignment: Alignment(-0.3, _kusY),
                  child: Transform.rotate(
                    angle: (_kusHiz * 15).clamp(-0.5, 0.8),
                    child: Transform.scale(
                      scaleX: -1,
                      child: const Text(
                        '🚗',
                        style: TextStyle(fontSize: 38),
                      ),
                    ),
                  ),
                ),

              // Skor göstergesi
              Positioned(
                top: 16, left: 16,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: Colors.black54,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        '${t('bird_score')}$_kusSkoru',
                        style: premiumNumberStyle.copyWith(color: Colors.yellow, fontSize: 16),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: Colors.black54,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        '${t('bird_best')}$_kusEnIyiSkor',
                        style: premiumNumberStyle.copyWith(color: Colors.white, fontSize: 11),
                      ),
                    ),
                  ],
                ),
              ),

              // Dodge bonus göstergesi
              if (_kusDodgeGoster && !_kusOyunuBitti)
                Align(
                  alignment: const Alignment(0, 0),
                  child: Text(
                    t('bird_dodge'),
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: Colors.greenAccent,
                      fontSize: 30,
                      fontWeight: FontWeight.bold,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ),

              // Başlamadan önceki talimat
              if (!_kusOyunuBasladi && !_kusOyunuBitti)
                Align(
                  alignment: const Alignment(0, -0.1),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.touch_app, color: Colors.white.withValues(alpha: 0.7), size: 50),
                      const SizedBox(height: 12),
                      Text(
                        t('bird_tap_to_fly'),
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.8),
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                ),

              // Oyun bitti overlay
              if (_kusOyunuBitti) Container(
                color: Colors.black.withValues(alpha: 0.85),
                child: Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        islemBittiMi ? t('render_done_text') : _kusKaybetmeNedeni,
                        style: TextStyle(
                          color: islemBittiMi ? Colors.green : Colors.redAccent,
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${t('bird_score')}$_kusSkoru',
                        style: premiumNumberStyle.copyWith(color: Colors.white, fontSize: 16),
                      ),
                      if (_kusSkoru == _kusEnIyiSkor && _kusSkoru > 0)
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text(
                            '🏆 ${t('bird_best')}$_kusEnIyiSkor',
                            style: premiumNumberStyle.copyWith(color: Colors.amber, fontSize: 13),
                          ),
                        ),
                      const SizedBox(height: 12),
                      if (!islemBittiMi)
                        ElevatedButton.icon(
                          onPressed: () {
                            if (titresimAcik.value) HapticFeedback.mediumImpact();
                            _kusOyunuBaslat();
                          },
                          icon: const Icon(Icons.refresh, color: Colors.white, size: 18),
                          label: Text(t('play_again'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13)),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF4CAF50),
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          ),
                        )
                      else
                        ElevatedButton.icon(
                          onPressed: () {
                            if (titresimAcik.value) HapticFeedback.mediumImpact();
                            RenderDurumYonetici().sifirla();
                            Navigator.pushReplacement(
                              context,
                              MaterialPageRoute(builder: (c) => const AnaSayfa(initialIndex: 1)),
                            );
                          },
                          icon: const Icon(Icons.garage, color: Colors.white, size: 18),
                          label: Text(t('return_garage'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13)),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.green,
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          ),
                        ),
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.05),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          children: [
                            Text(t('top_of_week'), style: const TextStyle(color: Colors.grey, fontWeight: FontWeight.bold, fontSize: 13)),
                            const SizedBox(height: 6),
                            if (_birdLeaderboard.isEmpty)
                              ...List.generate(3, (i) => Text('${i + 1}. ${t('coming_soon')}', style: const TextStyle(color: Colors.grey, fontSize: 11)))
                            else
                              ..._birdLeaderboard.take(3).toList().asMap().entries.map((entry) {
                                final idx = entry.key + 1;
                                final item = entry.value;
                                return Text('$idx. ${item['username']} - ${item['score']}', style: const TextStyle(color: Colors.white, fontSize: 11));
                              }),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // Boru çifti widget — CustomPaint ile çizilen borular
  Widget _boruWidget(_BoruCifti boru) {
    return Positioned.fill(
      child: CustomPaint(
        painter: _BoruPainter(
          boruX: boru.x,
          gapCenter: boru.gapCenter,
          boruGenislik: _boruGenislik,
          boruBosluk: _boruBosluk,
        ),
      ),
    );
  }

  Widget _vitrinKartiOlustur(
    String resimUrl,
    String kullaniciAdi,
    String arabaAdi,
  ) {
    return Container(
      width: 120,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        image: DecorationImage(
          image: NetworkImage(resimUrl),
          fit: BoxFit.cover,
        ),
      ),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Colors.transparent, Colors.black.withValues(alpha: 0.8)],
          ),
        ),
        padding: const EdgeInsets.all(8),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.end,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              arabaAdi,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 10,
                fontWeight: FontWeight.bold,
              ),
            ),
            Text(
              kullaniciAdi,
              style: const TextStyle(color: Colors.grey, fontSize: 8),
            ),
          ],
        ),
      ),
    );
  }
}

// ========== BORU ÇİFTİ MODEL ==========
class _BoruCifti {
  double x; // -1.0 ile 1.0+ arası
  double gapCenter; // boşluğun merkezi
  bool gecildi;

  _BoruCifti({
    required this.x,
    required this.gapCenter,
    this.gecildi = false,
  });
}

// ========== GÖKYÜZÜ PAINTER ==========
class _GokyuzuPainter extends CustomPainter {
  final double offset;

  _GokyuzuPainter({required this.offset});

  @override
  void paint(Canvas canvas, Size size) {
    // Gökyüzü gradient
    final skyGradient = LinearGradient(
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
      colors: [
        const Color(0xFF0D1B2A),
        const Color(0xFF1B2838),
        const Color(0xFF2D4356),
        const Color(0xFF1A2332),
      ],
      stops: const [0.0, 0.3, 0.7, 1.0],
    );
    final skyPaint = Paint()
      ..shader = skyGradient.createShader(Rect.fromLTWH(0, 0, size.width, size.height));
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), skyPaint);

    // Yıldızlar
    final starPaint = Paint()..color = Colors.white.withOpacity(0.4);
    final rng = Random(42);
    for (int i = 0; i < 30; i++) {
      double x = (rng.nextDouble() * size.width + offset * 20) % size.width;
      double y = rng.nextDouble() * size.height * 0.6;
      double r = rng.nextDouble() * 1.5 + 0.5;
      canvas.drawCircle(Offset(x, y), r, starPaint);
    }

    // Uzak binalar silueti
    final buildingPaint = Paint()..color = const Color(0xFF0A1520);
    final rngB = Random(99);
    for (int i = 0; i < 15; i++) {
      double baseX = (i * size.width / 15 + offset * 15) % (size.width + 60) - 30;
      double h = 30 + rngB.nextDouble() * 80;
      double w = 15 + rngB.nextDouble() * 25;
      canvas.drawRect(
        Rect.fromLTWH(baseX, size.height - 40 - h, w, h + 40),
        buildingPaint,
      );
    }

    // Yakın binalar silueti
    final nearBuildingPaint = Paint()..color = const Color(0xFF0D1825);
    for (int i = 0; i < 10; i++) {
      double baseX = (i * size.width / 10 + offset * 40) % (size.width + 80) - 40;
      double h = 50 + rngB.nextDouble() * 60;
      double w = 20 + rngB.nextDouble() * 35;
      canvas.drawRect(
        Rect.fromLTWH(baseX, size.height - 40 - h, w, h + 40),
        nearBuildingPaint,
      );
      // Pencereler
      final windowPaint = Paint()..color = Colors.amber.withOpacity(0.15);
      for (int row = 0; row < (h / 15).floor(); row++) {
        for (int col = 0; col < (w / 10).floor(); col++) {
          if (rngB.nextBool()) {
            canvas.drawRect(
              Rect.fromLTWH(baseX + 3 + col * 10, size.height - 40 - h + 5 + row * 15, 5, 8),
              windowPaint,
            );
          }
        }
      }
    }
  }

  @override
  bool shouldRepaint(covariant _GokyuzuPainter oldDelegate) =>
      oldDelegate.offset != offset;
}

// ========== ZEMİN PAINTER ==========
class _ZeminPainter extends CustomPainter {
  final double offset;

  _ZeminPainter({required this.offset});

  @override
  void paint(Canvas canvas, Size size) {
    // Zemin
    final groundPaint = Paint()..color = const Color(0xFF2D5016);
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, size.height), groundPaint);

    // Çim efekti
    final grassPaint = Paint()..color = const Color(0xFF3A6B1E);
    for (int i = 0; i < 40; i++) {
      double x = ((i * size.width / 40) + offset * 200) % size.width;
      canvas.drawRect(Rect.fromLTWH(x, 0, 3, 6), grassPaint);
    }

    // Üst kenar çizgisi
    final edgePaint = Paint()
      ..color = const Color(0xFF8B6914)
      ..strokeWidth = 3;
    canvas.drawLine(Offset(0, 0), Offset(size.width, 0), edgePaint);
  }

  @override
  bool shouldRepaint(covariant _ZeminPainter oldDelegate) =>
      oldDelegate.offset != offset;
}

// ========== BORU PAINTER ==========
class _BoruPainter extends CustomPainter {
  final double boruX;
  final double gapCenter;
  final double boruGenislik;
  final double boruBosluk;

  _BoruPainter({
    required this.boruX,
    required this.gapCenter,
    required this.boruGenislik,
    required this.boruBosluk,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // Boru X pozisyonunu piksel'e çevir (-1 ile 1 arası → 0 ile size.width)
    double pixelX = (boruX + 1.0) / 2.0 * size.width;
    double pixelW = boruGenislik * size.width;

    // Gap merkezi Y → piksel
    double gapCenterPixel = (gapCenter + 1.0) / 2.0 * size.height;
    double gapHeightPixel = boruBosluk * size.height;

    double topPipeBottom = gapCenterPixel - gapHeightPixel / 2;
    double bottomPipeTop = gapCenterPixel + gapHeightPixel / 2;

    // Boru renkleri
    final pipePaint = Paint()..color = const Color(0xFF2E7D32);
    final pipeEdgePaint = Paint()..color = const Color(0xFF1B5E20);
    final pipeHighlightPaint = Paint()..color = const Color(0xFF4CAF50).withOpacity(0.4);
    final capPaint = Paint()..color = const Color(0xFF388E3C);

    double capExtraWidth = 6;
    double capHeight = 16;

    // Üst boru gövdesi
    if (topPipeBottom > 0) {
      canvas.drawRect(
        Rect.fromLTWH(pixelX - pixelW / 2, 0, pixelW, topPipeBottom),
        pipePaint,
      );
      // Highlight şerit
      canvas.drawRect(
        Rect.fromLTWH(pixelX - pixelW / 2 + 3, 0, 5, topPipeBottom),
        pipeHighlightPaint,
      );
      // Kenar çizgi
      canvas.drawLine(
        Offset(pixelX - pixelW / 2, 0),
        Offset(pixelX - pixelW / 2, topPipeBottom),
        pipeEdgePaint..strokeWidth = 2,
      );
      canvas.drawLine(
        Offset(pixelX + pixelW / 2, 0),
        Offset(pixelX + pixelW / 2, topPipeBottom),
        pipeEdgePaint..strokeWidth = 2,
      );
      // Alt kap (ağız)
      canvas.drawRect(
        Rect.fromLTWH(
          pixelX - pixelW / 2 - capExtraWidth,
          topPipeBottom - capHeight,
          pixelW + capExtraWidth * 2,
          capHeight,
        ),
        capPaint,
      );
    }

    // Alt boru gövdesi
    if (bottomPipeTop < size.height) {
      double bottomHeight = size.height - bottomPipeTop;
      canvas.drawRect(
        Rect.fromLTWH(pixelX - pixelW / 2, bottomPipeTop, pixelW, bottomHeight),
        pipePaint,
      );
      // Highlight şerit
      canvas.drawRect(
        Rect.fromLTWH(pixelX - pixelW / 2 + 3, bottomPipeTop, 5, bottomHeight),
        pipeHighlightPaint,
      );
      // Kenar çizgi
      canvas.drawLine(
        Offset(pixelX - pixelW / 2, bottomPipeTop),
        Offset(pixelX - pixelW / 2, size.height),
        pipeEdgePaint..strokeWidth = 2,
      );
      canvas.drawLine(
        Offset(pixelX + pixelW / 2, bottomPipeTop),
        Offset(pixelX + pixelW / 2, size.height),
        pipeEdgePaint..strokeWidth = 2,
      );
      // Üst kap (ağız)
      canvas.drawRect(
        Rect.fromLTWH(
          pixelX - pixelW / 2 - capExtraWidth,
          bottomPipeTop,
          pixelW + capExtraWidth * 2,
          capHeight,
        ),
        capPaint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _BoruPainter oldDelegate) =>
      oldDelegate.boruX != boruX || oldDelegate.gapCenter != gapCenter;
}

// Animasyonlu yol çizgileri painter
class _YolCizgisiPainter extends CustomPainter {
  final double offset; // 0.0 - 1.0 arası hareket
  final bool nitroAktif;

  _YolCizgisiPainter({required this.offset, required this.nitroAktif});

  @override
  void paint(Canvas canvas, Size size) {
    final laneLinePaint = Paint()
      ..color = Colors.white.withOpacity(0.15)
      ..strokeWidth = 2.0;

    // Şerit çizgileri (sol ve sağ ayırım)
    final double laneWidth = size.width / 3;
    for (int lane = 1; lane < 3; lane++) {
      final double x = laneWidth * lane;
      // Kesik çizgi
      const double dashHeight = 30.0;
      const double gapHeight = 20.0;
      final double period = dashHeight + gapHeight;
      final double startOffset = (offset * period * 2) % period;
      double y = -period + startOffset;
      while (y < size.height) {
        canvas.drawLine(
          Offset(x, y),
          Offset(x, y + dashHeight),
          laneLinePaint,
        );
        y += period;
      }
    }

    // Yol kenar çizgileri
    final edgePaint = Paint()
      ..color = Colors.white.withOpacity(0.08)
      ..strokeWidth = 3.0;
    canvas.drawLine(Offset(0, 0), Offset(0, size.height), edgePaint);
    canvas.drawLine(Offset(size.width, 0), Offset(size.width, size.height), edgePaint);
  }

  @override
  bool shouldRepaint(covariant _YolCizgisiPainter oldDelegate) =>
      oldDelegate.offset != offset || oldDelegate.nitroAktif != nitroAktif;
}
