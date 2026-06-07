import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'dart:convert';
import 'sistem_ve_dil.dart';

class BildirimModeli {
  final String baslik;
  final String icerik;
  final String tarih;
  final String tip; // 'render', 'kampanya'
  final String? ikon;

  BildirimModeli({required this.baslik, required this.icerik, required this.tarih, required this.tip, this.ikon});

  Map<String, dynamic> toJson() => {'baslik': baslik, 'icerik': icerik, 'tarih': tarih, 'tip': tip, 'ikon': ikon};

  factory BildirimModeli.fromJson(Map<String, dynamic> json) => BildirimModeli(
    baslik: json['baslik'] ?? '',
    icerik: json['icerik'] ?? '',
    tarih: json['tarih'] ?? '',
    tip: json['tip'] ?? 'render',
    ikon: json['ikon'],
  );
}

// Bildirim sayısı global ValueNotifier
final ValueNotifier<int> okunmamisBildirimSayisi = ValueNotifier(0);

class BildirimServisi {
  static const String _key = 'bildirimler';
  static const String _readCountKey = 'okunan_bildirim_sayisi';

  static Future<List<BildirimModeli>> bildirimleriGetir() async {
    final prefs = await SharedPreferences.getInstance();
    final data = prefs.getStringList(_key) ?? [];
    return data.map((e) => BildirimModeli.fromJson(json.decode(e))).toList().reversed.toList();
  }

  static Future<void> bildirimEkle(BildirimModeli bildirim) async {
    final prefs = await SharedPreferences.getInstance();
    final data = prefs.getStringList(_key) ?? [];
    data.add(json.encode(bildirim.toJson()));
    await prefs.setStringList(_key, data);
    // Badge güncelle
    await okunmamisSayisiniGuncelle();
  }

  static Future<void> renderBildirimiOlustur({required String arabaAdi, required String method}) async {
    final now = DateTime.now();
    final tarihStr = '${now.day.toString().padLeft(2, '0')}.${now.month.toString().padLeft(2, '0')}.${now.year}';
    final saatStr = '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}';
    final methodStr = method == '3d' ? '3D' : '2D';
    await bildirimEkle(BildirimModeli(
      baslik: 'Render Tamamlandı! 🎉',
      icerik: '$tarihStr tarihinde $saatStr saatinde $arabaAdi $methodStr ${t('render_notif')}',
      tarih: '$tarihStr $saatStr',
      tip: 'render',
      ikon: '🏎️',
    ));
  }

  static Future<void> kampanyaBildirimiOlustur({required String baslik, required String icerik}) async {
    final now = DateTime.now();
    final tarihStr = '${now.day.toString().padLeft(2, '0')}.${now.month.toString().padLeft(2, '0')}.${now.year}';
    final saatStr = '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}';
    await bildirimEkle(BildirimModeli(
      baslik: baslik,
      icerik: icerik,
      tarih: '$tarihStr $saatStr',
      tip: 'kampanya',
      ikon: '🎁',
    ));
  }

  // --- Badge sayısı yönetimi ---
  static Future<void> okunmamisSayisiniGuncelle() async {
    final prefs = await SharedPreferences.getInstance();
    final toplamBildirim = (prefs.getStringList(_key) ?? []).length;
    final okunanSayi = prefs.getInt(_readCountKey) ?? 0;
    final okunmamis = toplamBildirim - okunanSayi;
    okunmamisBildirimSayisi.value = okunmamis > 0 ? okunmamis : 0;
  }

  static Future<void> tumunuOkunduIsaretle() async {
    final prefs = await SharedPreferences.getInstance();
    final toplamBildirim = (prefs.getStringList(_key) ?? []).length;
    await prefs.setInt(_readCountKey, toplamBildirim);
    okunmamisBildirimSayisi.value = 0;
  }
}

class BildirimSayfasi extends StatefulWidget {
  const BildirimSayfasi({super.key});
  @override
  State<BildirimSayfasi> createState() => _BildirimSayfasiState();
}

class _BildirimSayfasiState extends State<BildirimSayfasi> {
  late Future<List<BildirimModeli>> _bildirimFuture;

  @override
  void initState() {
    super.initState();
    _bildirimFuture = BildirimServisi.bildirimleriGetir();
    // Sayfaya girince bildirimleri okundu yap
    BildirimServisi.tumunuOkunduIsaretle();
  }

  @override
  Widget build(BuildContext context) {
    final Color anaRenk = const Color(0xFF257bf4);
    final Color koyuArkaplan = arkaplanRengi();
    final Color koyuYuzey = yuzeyRengi();

    return Scaffold(
      backgroundColor: koyuArkaplan,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(icon: Icon(Icons.arrow_back, color: yaziRengi()), onPressed: () => Navigator.pop(context)),
        title: Text(t('notifications_title'), style: TextStyle(color: yaziRengi(), fontSize: 18, fontWeight: FontWeight.bold)),
        centerTitle: true,
      ),
      body: FutureBuilder<List<BildirimModeli>>(
        future: _bildirimFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) return Center(child: CircularProgressIndicator(color: anaRenk));
          final bildirimler = snapshot.data ?? [];
          if (bildirimler.isEmpty) {
            return Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Container(padding: const EdgeInsets.all(24), decoration: BoxDecoration(color: koyuYuzey, shape: BoxShape.circle), child: const Icon(Icons.notifications_off_outlined, color: Colors.grey, size: 48)),
              const SizedBox(height: 16),
              Text(t('no_notifications'), style: const TextStyle(color: Colors.grey, fontSize: 16)),
            ]));
          }
          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: bildirimler.length,
            itemBuilder: (context, index) {
              final bildirim = bildirimler[index];
              final isRender = bildirim.tip == 'render';
              return Container(
                margin: const EdgeInsets.only(bottom: 12),
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: koyuYuzey,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: isRender ? anaRenk.withValues(alpha: 0.2) : Colors.orange.withValues(alpha: 0.2)),
                ),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(color: (isRender ? anaRenk : Colors.orange).withValues(alpha: 0.1), shape: BoxShape.circle),
                    child: Text(bildirim.ikon ?? (isRender ? '🏎️' : '🎁'), style: const TextStyle(fontSize: 20)),
                  ),
                  const SizedBox(width: 12),
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(bildirim.baslik, style: TextStyle(color: yaziRengi(), fontWeight: FontWeight.bold, fontSize: 14)),
                    const SizedBox(height: 4),
                    Text(bildirim.icerik, style: TextStyle(color: ikinciYaziRengi(), fontSize: 12, height: 1.4)),
                    const SizedBox(height: 6),
                    Text(bildirim.tarih, style: TextStyle(color: Colors.grey.withValues(alpha: 0.5), fontSize: 10)),
                  ])),
                ]),
              );
            },
          );
        },
      ),
    );
  }
}
