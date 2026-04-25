import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'dart:async';
import 'dart:math';
import 'sistem_ve_dil.dart';
import 'sayfalar_ana.dart'; // Oyun bitince Ana Sayfa'ya dönmek için

// --- RENDER (İŞLENİYOR) VE OYUN SAYFASI ---
class RenderSayfasi extends StatefulWidget {
  const RenderSayfasi({super.key});

  @override
  State<RenderSayfasi> createState() => _RenderSayfasiState();
}

class _RenderSayfasiState extends State<RenderSayfasi> with SingleTickerProviderStateMixin {
  late AnimationController _animasyonKontrolcusu;
  final int _toplamSureSaniye = 180;

  int _arabaSeridi = 1;
  int _oyunSkoru = 0;
  int _enIyiSkor = 0;
  Timer? _oyunZamanlayicisi;
  bool _oyunAktif = true;
  bool _oyunBitti = false;

  bool _nitroAktif = false;
  bool _kilPayiGoster = false;

  double _yolCizgisiY = 0.0;
  double _trafikY = -1.0;
  int _trafikSeridi = 1;
  final List<String> _trafikAraclari = ['🚓', '🚕', '🚙', '🚑', '🚒', '🏍️'];
  String _secilenTrafikAraci = '🚕';

  double _nitroY = -1.5;
  int _nitroSeridi = 0;

  @override
  void initState() {
    super.initState();
    _animasyonKontrolcusu = AnimationController(vsync: this, duration: Duration(seconds: _toplamSureSaniye))
      ..addListener(() { setState(() {}); })
      ..addStatusListener((status) { if (status == AnimationStatus.completed) { _oyunAktif = false; _oyunZamanlayicisi?.cancel(); } });
    _animasyonKontrolcusu.forward();
    _oyunuBaslat();
  }

  // Oyunu başlatan ve döngüyü kuran fonksiyon
  void _oyunuBaslat() {
    _oyunAktif = true; _oyunBitti = false; _oyunSkoru = 0; _trafikY = -1.0; _nitroY = -1.5; _arabaSeridi = 1; _nitroAktif = false; _kilPayiGoster = false;
    _secilenTrafikAraci = _trafikAraclari[Random().nextInt(_trafikAraclari.length)];

    _oyunZamanlayicisi = Timer.periodic(const Duration(milliseconds: 30), (timer) {
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
            _oyunSkoru += 50; _kilPayiGoster = true;
            Timer(const Duration(milliseconds: 1000), () { if (mounted) setState(() => _kilPayiGoster = false); });
          } else { _oyunSkoru += 10; }
          _trafikY = -1.0; _trafikSeridi = Random().nextInt(3); _secilenTrafikAraci = _trafikAraclari[Random().nextInt(_trafikAraclari.length)];
        }

        _nitroY += 0.04 * toplamHiz;
        if (_nitroY > 1.2) {
          _nitroY = -1.0 - (Random().nextDouble() * 4.0);
          _nitroSeridi = Random().nextInt(3);
          if (_nitroSeridi == _trafikSeridi) _nitroSeridi = (_nitroSeridi + 1) % 3;
        }

        if (_trafikY > 0.65 && _trafikY < 1.0 && _arabaSeridi == _trafikSeridi) {
          HapticFeedback.heavyImpact();
          _oyunBitti = true;
          if (_oyunSkoru > _enIyiSkor) _enIyiSkor = _oyunSkoru;
          _oyunZamanlayicisi?.cancel();
        }

        if (!_oyunBitti && _nitroY > 0.65 && _nitroY < 1.0 && _arabaSeridi == _nitroSeridi) {
          HapticFeedback.mediumImpact();
          _nitroAktif = true; _nitroY = -2.0; _oyunSkoru += 30;
          Timer(const Duration(seconds: 3), () { if (mounted) setState(() { _nitroAktif = false; }); });
        }
      });
    });
  }

  void _seritDegistir(bool sagaMi) {
    if (!mounted || !_oyunAktif || _oyunBitti) return;
    HapticFeedback.lightImpact();
    setState(() { if (sagaMi && _arabaSeridi < 2) { _arabaSeridi++; } else if (!sagaMi && _arabaSeridi > 0) { _arabaSeridi--; } });
  }

  @override
  void dispose() { _oyunZamanlayicisi?.cancel(); _animasyonKontrolcusu.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<String>(
        valueListenable: appLanguage,
        builder: (context, lang, child) {
          final Color anaRenk = const Color(0xFF257bf4);
          final Color koyuArkaplan = const Color(0xFF0A1017);
          final Color koyuYuzey = const Color(0xFF182434);

          int gecenSaniye = (_animasyonKontrolcusu.value * _toplamSureSaniye).toInt();
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
                  Padding(
                    padding: const EdgeInsets.all(20.0),
                    child: Container(
                      padding: const EdgeInsets.all(20),
                      decoration: BoxDecoration(color: koyuYuzey, borderRadius: BorderRadius.circular(20), border: Border.all(color: Colors.white.withOpacity(0.05))),
                      child: Column(
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Row(children: [Icon(islemBittiMi ? Icons.check_circle : Icons.memory, color: islemBittiMi ? Colors.green : anaRenk), const SizedBox(width: 8), Text(islemBittiMi ? t('completed_up') : t('ai_processing'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))]),
                              Text('%$yuzde', style: premiumNumberStyle.copyWith(color: islemBittiMi ? Colors.green : anaRenk, fontSize: 18)),
                            ],
                          ),
                          const SizedBox(height: 16),
                          LinearProgressIndicator(value: _animasyonKontrolcusu.value, minHeight: 6, backgroundColor: Colors.grey.shade800, valueColor: AlwaysStoppedAnimation<Color>(islemBittiMi ? Colors.green : anaRenk), borderRadius: BorderRadius.circular(4)),
                          const SizedBox(height: 8),
                          Align(alignment: Alignment.centerRight, child: Text(islemBittiMi ? t('ready') : '${t('remaining')}${kalanSaniye ~/ 60}${t('min')} ${kalanSaniye % 60}${t('sec')}', style: premiumNumberStyle.copyWith(color: Colors.grey, fontSize: 11, fontWeight: FontWeight.normal))),
                        ],
                      ),
                    ),
                  ),

                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20.0),
                      child: GestureDetector(
                        onTapDown: (details) { if (details.globalPosition.dx < MediaQuery.of(context).size.width / 2) { _seritDegistir(false); } else { _seritDegistir(true); } },
                        child: Container(
                          decoration: BoxDecoration(color: const Color(0xFF1a1c23), borderRadius: BorderRadius.circular(20), border: Border.all(color: Colors.white.withOpacity(0.1), width: 2), boxShadow: [BoxShadow(color: _nitroAktif ? Colors.orange.withOpacity(0.3) : anaRenk.withOpacity(0.1), blurRadius: 15, spreadRadius: 2)]),
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(20),
                            child: Stack(
                              children: [
                                for (int i = 0; i < 5; i++) Align(alignment: Alignment(-0.33, (_yolCizgisiY + (i * 0.4)) % 2 - 1), child: Container(width: 4, height: 40, color: Colors.white.withOpacity(0.3))),
                                for (int i = 0; i < 5; i++) Align(alignment: Alignment(0.33, (_yolCizgisiY + (i * 0.4)) % 2 - 1), child: Container(width: 4, height: 40, color: Colors.white.withOpacity(0.3))),

                                Positioned(
                                    top: 16, left: 16,
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Container(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6), decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(12)), child: Text('${t('score')}$_oyunSkoru', style: premiumNumberStyle.copyWith(color: Colors.yellow, fontSize: 16))),
                                        const SizedBox(height: 6),
                                        Container(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6), decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(12)), child: Text('${t('best')}$_enIyiSkor', style: premiumNumberStyle.copyWith(color: Colors.white, fontSize: 11))),
                                      ],
                                    )
                                ),

                                if (_kilPayiGoster && !_oyunBitti) Align(alignment: Alignment.center, child: Text(t('close_call'), textAlign: TextAlign.center, style: const TextStyle(color: Colors.orangeAccent, fontSize: 32, fontWeight: FontWeight.bold, fontStyle: FontStyle.italic))),
                                if (!islemBittiMi && !_oyunBitti) Align(alignment: Alignment(trafikX, _trafikY), child: Text(_secilenTrafikAraci, style: const TextStyle(fontSize: 45))),
                                if (!islemBittiMi && !_oyunBitti) Align(alignment: Alignment(nitroX, _nitroY), child: const Text('⚡', style: TextStyle(fontSize: 35))),
                                if (!_oyunBitti) Align(alignment: Alignment(arabaX, 0.8), child: const Text('🏎️', style: TextStyle(fontSize: 60))),
                                if (_nitroAktif && !islemBittiMi && !_oyunBitti) Align(alignment: Alignment(arabaX, 0.95), child: const Text('🔥', style: TextStyle(fontSize: 30))),

                                if (islemBittiMi)
                                  Container(color: Colors.black.withOpacity(0.8), child: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [const Icon(Icons.emoji_events, color: Colors.amber, size: 60), const SizedBox(height: 10), Text(t('render_finished'), style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold))]))),
                                if (_oyunBitti)
                                  Container(
                                    color: Colors.black.withOpacity(0.85),
                                    child: Center(
                                      child: Column(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          Text(t('crashed'), style: const TextStyle(color: Colors.redAccent, fontSize: 28, fontWeight: FontWeight.bold)),
                                          const SizedBox(height: 12),
                                          Text('${t('score')}$_oyunSkoru', style: premiumNumberStyle.copyWith(color: Colors.white, fontSize: 18)),
                                          const SizedBox(height: 24),
                                          ElevatedButton.icon(onPressed: () { HapticFeedback.mediumImpact(); _oyunuBaslat(); }, icon: const Icon(Icons.refresh, color: Colors.white), label: Text(t('play_again'), style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)), style: ElevatedButton.styleFrom(backgroundColor: anaRenk, padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)))),
                                          const SizedBox(height: 30),
                                          Container(
                                            padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: Colors.white.withOpacity(0.05), borderRadius: BorderRadius.circular(12)),
                                            child: Column(children: [Text(t('top_of_week'), style: const TextStyle(color: Colors.grey, fontWeight: FontWeight.bold)), const SizedBox(height: 8), Text('1. ${t('coming_soon')}', style: const TextStyle(color: Colors.grey, fontSize: 12)), Text('2. ${t('coming_soon')}', style: const TextStyle(color: Colors.grey, fontSize: 12)), Text('3. ${t('coming_soon')}', style: const TextStyle(color: Colors.grey, fontSize: 12))]),
                                          )
                                        ],
                                      ),
                                    ),
                                  )
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),

                  const SizedBox(height: 20),

                  Container(
                    height: 160, padding: const EdgeInsets.only(left: 20, top: 10, bottom: 20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(t('community_legends'), style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 12),
                        Expanded(
                          child: ListView(
                            scrollDirection: Axis.horizontal,
                            children: [
                              _vitrinKartiOlustur('https://images.unsplash.com/photo-1544829099-b9a0c07fad1a?q=80&w=1000', '@Kaan_Drift', 'Supra MK4'), const SizedBox(width: 12),
                              _vitrinKartiOlustur('https://images.unsplash.com/photo-1503376713222-25ec13d8cbb8?q=80&w=1000', '@Ahmet3D', 'Porsche 911'), const SizedBox(width: 12),
                              _vitrinKartiOlustur('https://images.unsplash.com/photo-1614200179396-2bdb77ebf81b?q=80&w=1000', '@Ali_Racer', 'GTR R34'), const SizedBox(width: 20),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),

                  if (islemBittiMi)
                    Padding(
                      padding: const EdgeInsets.only(left: 20, right: 20, bottom: 20),
                      child: ElevatedButton(onPressed: () { HapticFeedback.mediumImpact(); Navigator.pushReplacement(context, MaterialPageRoute(builder: (context) => const AnaSayfa())); }, style: ElevatedButton.styleFrom(backgroundColor: Colors.green, minimumSize: const Size(double.infinity, 50), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))), child: Text(t('return_garage'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white))),
                    ),
                ],
              ),
            ),
          );
        }
    );
  }

  Widget _vitrinKartiOlustur(String resimUrl, String kullaniciAdi, String arabaAdi) {
    return Container(
      width: 120, decoration: BoxDecoration(borderRadius: BorderRadius.circular(12), image: DecorationImage(image: NetworkImage(resimUrl), fit: BoxFit.cover)),
      child: Container(
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(12), gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Colors.transparent, Colors.black.withOpacity(0.8)])),
        padding: const EdgeInsets.all(8),
        child: Column(mainAxisAlignment: MainAxisAlignment.end, crossAxisAlignment: CrossAxisAlignment.start, children: [Text(arabaAdi, style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)), Text(kullaniciAdi, style: const TextStyle(color: Colors.grey, fontSize: 8))]),
      ),
    );
  }
}