import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'dart:async';
import 'dart:math';
import 'sistem_ve_dil.dart';
import 'sayfalar_ana.dart';
import 'sekme_bildirim.dart';
import 'servisler/api_servisi.dart';
import 'modeller/community_model.dart';

// --- RENDER (İŞLENİYOR) VE OYUN SAYFASI ---
class RenderSayfasi extends StatefulWidget {
  final String carName;
  final String method;
  const RenderSayfasi({super.key, this.carName = '', this.method = '2d'});

  @override
  State<RenderSayfasi> createState() => _RenderSayfasiState();
}

class _RenderSayfasiState extends State<RenderSayfasi>
    with SingleTickerProviderStateMixin {
  late AnimationController _animasyonKontrolcusu;
  late final int _toplamSureSaniye;

  int _arabaSeridi = 1;
  int _oyunSkoru = 0;
  int _enIyiSkor = 0;
  Timer? _oyunZamanlayicisi;
  bool _oyunAktif = true;
  bool _oyunBitti = false;

  bool _nitroAktif = false;
  bool _kilPayiGoster = false;

  String _renderDurumMesaji = ''; // Task 7: Render durum mesajı
  int _durumMesajIndex = 0;
  Timer? _durumMesajTimer;

  double _yolCizgisiY = 0.0;
  double _trafikY = -1.0;
  int _trafikSeridi = 1;
  final List<String> _trafikAraclari = ['🚓', '🚕', '🚙', '🚑', '🚒', '🏍️'];
  String _secilenTrafikAraci = '🚕';

  double _nitroY = -1.5;
  int _nitroSeridi = 0;

  List<Map<String, dynamic>> _liderlikTablosu = [];
  List<FeedItem> _efsaneler = [];

  @override
  void initState() {
    super.initState();
    _toplamSureSaniye = widget.method == '2d' ? 60 : 180;
    
    _liderlikTablosuVeEfsaneleriGetir();
    _animasyonKontrolcusu =
        AnimationController(
            vsync: this,
            duration: Duration(seconds: _toplamSureSaniye),
          )
          ..addListener(() {
            setState(() {});
          })
          ..addStatusListener((status) {
            if (status == AnimationStatus.completed) {
              // Madde 9: Oyun devam ediyor, sadece banner gösteriliyor
              // Render tamamlandı — bildirim oluştur
              // Bildirim oluştur
              BildirimServisi.renderBildirimiOlustur(
                arabaAdi: widget.carName,
                method: widget.method,
              );
            }
          });
    _animasyonKontrolcusu.forward();
    _oyunuBaslat();
    _renderDurumMesajlariniBaslat();
  }

  Future<void> _liderlikTablosuVeEfsaneleriGetir() async {
    try {
      final tablo = await ApiServisi().oyunLiderlikTablosuGetir();
      final feed = await ApiServisi().feedGetir();
      feed.sort((a, b) => b.likeCount.compareTo(a.likeCount));
      
      if (mounted) {
        setState(() {
          _liderlikTablosu = tablo;
          _efsaneler = feed.take(3).toList();
        });
      }
    } catch (_) {}
  }

  // Oyunu başlatan ve döngüyü kuran fonksiyon
  void _oyunuBaslat() {
    // BUG-24 FIX: Önceki timer'ı iptal et (çift game loop önlemi)
    _oyunZamanlayicisi?.cancel();
    _oyunAktif = true;
    _oyunBitti = false;
    _oyunSkoru = 0;
    _trafikY = -1.0;
    _nitroY = -1.5;
    _arabaSeridi = 1;
    _nitroAktif = false;
    _kilPayiGoster = false;
    _secilenTrafikAraci =
        _trafikAraclari[Random().nextInt(_trafikAraclari.length)];

    _oyunZamanlayicisi = Timer.periodic(const Duration(milliseconds: 30), (
      timer,
    ) {
      if (!mounted || !_oyunAktif || _oyunBitti) return;
      setState(() {
        int zorlukSeviyesi = _oyunSkoru ~/ 200;
        double dinamikHizCarpani = 1.0 + (zorlukSeviyesi * 0.10);
        double toplamHiz = dinamikHizCarpani * (_nitroAktif ? 2.0 : 1.0);

        _yolCizgisiY += 0.05 * toplamHiz;
        if (_yolCizgisiY > 1.0) _yolCizgisiY = 0.0;

        _trafikY += 0.04 * toplamHiz;
        if (_trafikY > 1.2) {
          if ((_arabaSeridi - _trafikSeridi).abs() == 1) {
            _oyunSkoru += 50;
            _kilPayiGoster = true;
            Timer(const Duration(milliseconds: 1000), () {
              if (mounted) setState(() => _kilPayiGoster = false);
            });
          } else {
            _oyunSkoru += 10;
          }
          _trafikY = -1.0;
          _trafikSeridi = Random().nextInt(3);
          _secilenTrafikAraci =
              _trafikAraclari[Random().nextInt(_trafikAraclari.length)];
        }

        _nitroY += 0.04 * toplamHiz;
        if (_nitroY > 1.2) {
          _nitroY = -1.0 - (Random().nextDouble() * 4.0);
          _nitroSeridi = Random().nextInt(3);
          if (_nitroSeridi == _trafikSeridi)
            _nitroSeridi = (_nitroSeridi + 1) % 3;
        }

        if (_trafikY > 0.65 &&
            _trafikY < 1.0 &&
            _arabaSeridi == _trafikSeridi) {
          if (titresimAcik.value) HapticFeedback.heavyImpact();
          _oyunBitti = true;
          if (_oyunSkoru > _enIyiSkor) _enIyiSkor = _oyunSkoru;
          _oyunZamanlayicisi?.cancel();
          ApiServisi().oyunSkoruKaydet(_oyunSkoru).then((_) {
            _liderlikTablosuVeEfsaneleriGetir();
          });
        }

        if (!_oyunBitti &&
            _nitroY > 0.65 &&
            _nitroY < 1.0 &&
            _arabaSeridi == _nitroSeridi) {
          if (titresimAcik.value) HapticFeedback.mediumImpact();
          _nitroAktif = true;
          _nitroY = -2.0;
          _oyunSkoru += 30;
          Timer(const Duration(seconds: 3), () {
            if (mounted)
              setState(() {
                _nitroAktif = false;
              });
          });
        }
      });
    });
  }

  void _seritDegistir(bool sagaMi) {
    if (!mounted || !_oyunAktif || _oyunBitti) return;
    if (titresimAcik.value) HapticFeedback.lightImpact();
    setState(() {
      if (sagaMi && _arabaSeridi < 2) {
        _arabaSeridi++;
      } else if (!sagaMi && _arabaSeridi > 0) {
        _arabaSeridi--;
      }
    });
  }

  @override
  void dispose() {
    _oyunZamanlayicisi?.cancel();
    _durumMesajTimer?.cancel();
    _animasyonKontrolcusu.dispose();
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
      if (!mounted || _animasyonKontrolcusu.value >= 1.0) {
        timer.cancel();
        return;
      }
      setState(() {
        _durumMesajIndex = (_durumMesajIndex + 1) % mesajlar.length;
        _renderDurumMesaji = mesajlar[_durumMesajIndex];
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<String>(
      valueListenable: appLanguage,
      builder: (context, lang, child) {
        final Color anaRenk = const Color(0xFF257bf4);
        final Color koyuArkaplan = arkaplanRengi();
        final Color koyuYuzey = yuzeyRengi();

        int gecenSaniye = (_animasyonKontrolcusu.value * _toplamSureSaniye)
            .toInt();
        int kalanSaniye = _toplamSureSaniye - gecenSaniye;
        int yuzde = (_animasyonKontrolcusu.value * 100).toInt();
        bool islemBittiMi = _animasyonKontrolcusu.value == 1.0;

        double arabaX = (_arabaSeridi - 1) * 0.8;
        double trafikX = (_trafikSeridi - 1) * 0.8;
        double nitroX = (_nitroSeridi - 1) * 0.8;

        return Scaffold(
          backgroundColor: koyuArkaplan,
          body: SafeArea(
            child: Column(
              children: [
                // Üst progress bar + AI işliyor
                Padding(
                  padding: const EdgeInsets.all(20.0),
                  child: GestureDetector(
                    onTap: islemBittiMi
                        ? () {
                            if (titresimAcik.value) HapticFeedback.mediumImpact();
                            Navigator.pushReplacement(
                              context,
                              MaterialPageRoute(
                                builder: (context) => const AnaSayfa(),
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
                            value: _animasyonKontrolcusu.value,
                            minHeight: 6,
                            backgroundColor: Colors.grey.shade800,
                            valueColor: AlwaysStoppedAnimation<Color>(
                              islemBittiMi ? Colors.green : anaRenk,
                            ),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          const SizedBox(height: 12),
                          if (islemBittiMi)
                            ElevatedButton.icon(
                              onPressed: () {
                                if (titresimAcik.value) HapticFeedback.mediumImpact();
                                Navigator.pushReplacement(context, MaterialPageRoute(builder: (context) => const AnaSayfa()));
                              },
                              icon: const Icon(Icons.garage, color: Colors.white),
                              label: Text(t('return_garage'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                              style: ElevatedButton.styleFrom(backgroundColor: Colors.green, padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
                            )
                          else
                            Align(
                              alignment: Alignment.centerRight,
                              child: Text(
                                '${t('remaining')}${kalanSaniye ~/ 60}${t('min')} ${kalanSaniye % 60}${t('sec')}',
                                style: premiumNumberStyle.copyWith(
                                  color: Colors.grey,
                                  fontSize: 11,
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                ),

                // Oyun alanı - sürükleme ile kontrol
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 20.0),
                    child: GestureDetector(
                      onHorizontalDragEnd: (details) {
                        if (details.primaryVelocity == null) return;
                        if (details.primaryVelocity! > 0) {
                          _seritDegistir(true);
                        } // Sağa sürükle
                        else if (details.primaryVelocity! < 0) {
                          _seritDegistir(false);
                        } // Sola sürükle
                      },
                      child: Container(
                        decoration: BoxDecoration(
                          color: const Color(0xFF1a1c23),
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                            color: Colors.white.withValues(alpha: 0.1),
                            width: 2,
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: _nitroAktif
                                  ? Colors.orange.withValues(alpha: 0.3)
                                  : anaRenk.withValues(alpha: 0.1),
                              blurRadius: 15,
                              spreadRadius: 2,
                            ),
                          ],
                        ),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(20),
                          child: Stack(
                            children: [
                              for (int i = 0; i < 5; i++)
                                Align(
                                  alignment: Alignment(
                                    -0.33,
                                    (_yolCizgisiY + (i * 0.4)) % 2 - 1,
                                  ),
                                  child: Container(
                                    width: 4,
                                    height: 40,
                                    color: Colors.white.withValues(alpha: 0.3),
                                  ),
                                ),
                              for (int i = 0; i < 5; i++)
                                Align(
                                  alignment: Alignment(
                                    0.33,
                                    (_yolCizgisiY + (i * 0.4)) % 2 - 1,
                                  ),
                                  child: Container(
                                    width: 4,
                                    height: 40,
                                    color: Colors.white.withValues(alpha: 0.3),
                                  ),
                                ),

                              Positioned(
                                top: 16,
                                left: 16,
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 12,
                                        vertical: 6,
                                      ),
                                      decoration: BoxDecoration(
                                        color: Colors.black54,
                                        borderRadius: BorderRadius.circular(12),
                                      ),
                                      child: Text(
                                        '${t('score')}$_oyunSkoru',
                                        style: premiumNumberStyle.copyWith(
                                          color: Colors.yellow,
                                          fontSize: 16,
                                        ),
                                      ),
                                    ),
                                    const SizedBox(height: 6),
                                    Container(
                                      padding: const EdgeInsets.symmetric(
                                        horizontal: 12,
                                        vertical: 6,
                                      ),
                                      decoration: BoxDecoration(
                                        color: Colors.black54,
                                        borderRadius: BorderRadius.circular(12),
                                      ),
                                      child: Text(
                                        '${t('best')}$_enIyiSkor',
                                        style: premiumNumberStyle.copyWith(
                                          color: Colors.white,
                                          fontSize: 11,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),

                              if (_kilPayiGoster && !_oyunBitti)
                                Align(
                                  alignment: Alignment.center,
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
                              if (!_oyunBitti)
                                Align(
                                  alignment: Alignment(trafikX, _trafikY),
                                  child: Text(
                                    _secilenTrafikAraci,
                                    style: const TextStyle(fontSize: 45),
                                  ),
                                ),
                              if (!_oyunBitti)
                                Align(
                                  alignment: Alignment(nitroX, _nitroY),
                                  child: const Text(
                                    '⚡',
                                    style: TextStyle(fontSize: 35),
                                  ),
                                ),
                              if (!_oyunBitti)
                                Align(
                                  alignment: Alignment(arabaX, 0.8),
                                  child: const Text(
                                    '🏎️',
                                    style: TextStyle(fontSize: 60),
                                  ),
                                ),
                              if (_nitroAktif && !_oyunBitti)
                                Align(
                                  alignment: Alignment(arabaX, 0.95),
                                  child: const Text(
                                    '🔥',
                                    style: TextStyle(fontSize: 30),
                                  ),
                                ),

                              // Oyun bitti overlay
                              if (_oyunBitti)
                                Container(
                                  color: Colors.black.withValues(alpha: 0.85),
                                  child: Center(
                                    child: Column(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Text(
                                          t('crashed'),
                                          style: const TextStyle(
                                            color: Colors.redAccent,
                                            fontSize: 28,
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                        const SizedBox(height: 12),
                                        Text(
                                          '${t('score')}$_oyunSkoru',
                                          style: premiumNumberStyle.copyWith(
                                            color: Colors.white,
                                            fontSize: 18,
                                          ),
                                        ),
                                        const SizedBox(height: 24),
                                        ElevatedButton.icon(
                                          onPressed: () {
                                            if (titresimAcik.value) HapticFeedback.mediumImpact();
                                            _oyunuBaslat();
                                          },
                                          icon: const Icon(
                                            Icons.refresh,
                                            color: Colors.white,
                                          ),
                                          label: Text(
                                            t('play_again'),
                                            style: const TextStyle(
                                              color: Colors.white,
                                              fontSize: 16,
                                              fontWeight: FontWeight.bold,
                                            ),
                                          ),
                                          style: ElevatedButton.styleFrom(
                                            backgroundColor: anaRenk,
                                            padding: const EdgeInsets.symmetric(
                                              horizontal: 24,
                                              vertical: 12,
                                            ),
                                            shape: RoundedRectangleBorder(
                                              borderRadius:
                                                  BorderRadius.circular(12),
                                            ),
                                          ),
                                        ),
                                        const SizedBox(height: 30),
                                        Container(
                                          padding: const EdgeInsets.all(12),
                                          decoration: BoxDecoration(
                                            color: Colors.white.withValues(alpha:
                                              0.05,
                                            ),
                                            borderRadius: BorderRadius.circular(
                                              12,
                                            ),
                                          ),
                                          child: Column(
                                            children: [
                                              Text(
                                                t('top_of_week'),
                                                style: const TextStyle(
                                                  color: Colors.grey,
                                                  fontWeight: FontWeight.bold,
                                                ),
                                              ),
                                              const SizedBox(height: 8),
                                              if (_liderlikTablosu.isEmpty)
                                                const Text('Henüz skor yok', style: TextStyle(color: Colors.grey, fontSize: 12))
                                              else
                                                ..._liderlikTablosu.asMap().entries.map((entry) {
                                                  return Text('${entry.key + 1}. ${entry.value["username"]} - ${entry.value["score"]}', style: const TextStyle(color: Colors.grey, fontSize: 12));
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
                    ),
                  ),
                ),

                const SizedBox(height: 20),

                // Topluluğun Efsaneleri - basınca keşfete gitsin
                GestureDetector(
                  onTap: () {
                    if (titresimAcik.value) HapticFeedback.lightImpact();
                    Navigator.pushAndRemoveUntil(
                      context,
                      MaterialPageRoute(
                        builder: (c) => const AnaSayfa(initialIndex: 1),
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
                      mainAxisSize: MainAxisSize.min, // <-- ekle
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
                          // <-- Expanded yerine SizedBox
                          height: 110, // sabit yükseklik
                          child: ListView(
                            scrollDirection: Axis.horizontal,
                            children: [
                              if (_efsaneler.isNotEmpty)
                                ..._efsaneler.map((e) {
                                  final fotoUrl = ApiServisi.buildImageUrl(e.thumbnailUrl) ?? 'https://images.unsplash.com/photo-1617788138017-80ad40651399?q=80&w=1000';
                                  return Row(
                                    children: [
                                      _vitrinKartiOlustur(fotoUrl, '@${e.ownerName}', e.carName),
                                      const SizedBox(width: 12),
                                    ],
                                  );
                                })
                              else
                                const Center(child: Text('Yükleniyor...', style: TextStyle(color: Colors.grey, fontSize: 12))),
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
        );
      },
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
