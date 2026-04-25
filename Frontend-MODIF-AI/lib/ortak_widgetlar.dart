import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'dart:ui';
import 'sistem_ve_dil.dart';

// GLASSMORPHISM HEADER
class GlassHeader extends StatelessWidget {
  final Widget child;
  const GlassHeader({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          decoration: BoxDecoration(
            color: const Color(0xFF182434).withOpacity(0.4),
            border: const Border(bottom: BorderSide(color: Colors.white10, width: 0.5)),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 12.0),
          child: child,
        ),
      ),
    );
  }
}

void ortadanSecimDialoguGoster(BuildContext context) {
  HapticFeedback.lightImpact();
  showDialog(
    context: context,
    builder: (BuildContext context) {
      return AlertDialog(
        backgroundColor: const Color(0xFF182434),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(t('photo_source'), textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.camera_alt, color: Colors.white),
              title: Text(t('take_photo'), style: const TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.pop(context);
                HapticFeedback.selectionClick();
                ortakYakindaToastGoster(context);
              },
            ),
            const Divider(color: Colors.white10),
            ListTile(
              leading: const Icon(Icons.photo_library, color: Colors.white),
              title: Text(t('choose_gallery'), style: const TextStyle(color: Colors.white)),
              onTap: () {
                Navigator.pop(context);
                HapticFeedback.selectionClick();
                ortakYakindaToastGoster(context);
              },
            ),
          ],
        ),
      );
    },
  );
}

void ortakYakindaToastGoster(BuildContext context) {
  HapticFeedback.lightImpact();
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Row(
        children: [
          const Icon(Icons.info_outline, color: Colors.white),
          const SizedBox(width: 12),
          Expanded(child: Text(t('coming_soon_toast'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
        ],
      ),
      backgroundColor: Colors.deepOrange,
      duration: const Duration(seconds: 2),
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      margin: const EdgeInsets.all(20),
    ),
  );
}

// ETKİLEŞİMLİ KEŞFET GÖNDERİSİ KARTI
class KesfetGonderisiCard extends StatefulWidget {
  final String resimUrl;
  final String kullaniciAdi;
  final String baslik;
  final int baslangicAlev;
  final bool isFire;

  const KesfetGonderisiCard({
    Key? key,
    required this.resimUrl,
    required this.kullaniciAdi,
    required this.baslik,
    required this.baslangicAlev,
    this.isFire = false,
  }) : super(key: key);

  @override
  State<KesfetGonderisiCard> createState() => _KesfetGonderisiCardState();
}

class _KesfetGonderisiCardState extends State<KesfetGonderisiCard> {
  late int alevSayisi;
  bool begenildi = false;

  @override
  void initState() {
    super.initState();
    alevSayisi = widget.baslangicAlev;
  }

  void _alevTikla() {
    HapticFeedback.selectionClick();
    setState(() {
      if (begenildi) {
        alevSayisi--;
        begenildi = false;
      } else {
        alevSayisi++;
        begenildi = true;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final Color koyuYuzey = const Color(0xFF182434);

    return Container(
      decoration: BoxDecoration(
        color: koyuYuzey,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: widget.isFire ? Colors.deepOrange : Colors.white.withOpacity(0.05)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: ClipRRect(
              borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
              child: Image.network(
                widget.resimUrl,
                width: double.infinity,
                fit: BoxFit.cover,
                errorBuilder: (context, error, stackTrace) => Container(color: Colors.black26, child: const Icon(Icons.image_not_supported, color: Colors.grey)),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(12.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(widget.baslik, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold), maxLines: 1, overflow: TextOverflow.ellipsis),
                const SizedBox(height: 2),
                Text('${t('by')}${widget.kullaniciAdi}', style: const TextStyle(color: Colors.grey, fontSize: 10), maxLines: 1, overflow: TextOverflow.ellipsis),
                const SizedBox(height: 8),

                InkWell(
                  onTap: _alevTikla,
                  borderRadius: BorderRadius.circular(12),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 300),
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: begenildi ? Colors.deepOrange.withOpacity(0.2) : Colors.deepOrange.withOpacity(0.05),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: begenildi ? Colors.deepOrangeAccent : Colors.deepOrange.withOpacity(0.5)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text('🔥', style: TextStyle(fontSize: 14)),
                        const SizedBox(width: 4),
                        Text(
                          alevSayisi.toString(),
                          style: premiumNumberStyle.copyWith(
                            color: begenildi ? Colors.white : Colors.deepOrange,
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                )
              ],
            ),
          )
        ],
      ),
    );
  }
}

class ArabaKartiOlusturucu {
  static Widget olustur(String baslik, String altBaslik, String resimUrl, String zaman, Color anaRenk, Color koyuYuzey) {
    return Container(
      decoration: BoxDecoration(color: koyuYuzey, borderRadius: BorderRadius.circular(16), border: Border.all(color: Colors.white.withOpacity(0.05))),
      child: Column(
        children: [
          Stack(
            children: [
              ClipRRect(borderRadius: const BorderRadius.vertical(top: Radius.circular(16)), child: Image.network(resimUrl, height: 150, width: double.infinity, fit: BoxFit.cover, errorBuilder: (context, error, stackTrace) => Container(height: 150, width: double.infinity, color: Colors.black26, child: const Icon(Icons.directions_car, color: Colors.grey, size: 40)))),
              Positioned(top: 10, right: 10, child: Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), decoration: BoxDecoration(color: Colors.black.withOpacity(0.7), borderRadius: BorderRadius.circular(4)), child: Row(children: [const Icon(Icons.circle, color: Colors.green, size: 8), const SizedBox(width: 4), Text(t('completed'), style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold))]))),
            ],
          ),
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(baslik, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)), Text(altBaslik, style: const TextStyle(color: Colors.grey, fontSize: 12))]),
                    const Icon(Icons.more_vert, color: Colors.grey),
                  ],
                ),
                const SizedBox(height: 16),
                const Divider(color: Colors.white10, height: 1),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(children: [const Icon(Icons.schedule, color: Colors.grey, size: 14), const SizedBox(width: 4), Text(zaman, style: const TextStyle(color: Colors.grey, fontSize: 12))]),
                    Row(
                      children: [
                        Container(padding: const EdgeInsets.all(6), decoration: BoxDecoration(color: Colors.white.withOpacity(0.05), borderRadius: BorderRadius.circular(8)), child: const Icon(Icons.share, color: Colors.white, size: 16)),
                        const SizedBox(width: 8),
                        Container(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8), decoration: BoxDecoration(color: anaRenk, borderRadius: BorderRadius.circular(8)), child: Text(t('edit'), style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold))),
                      ],
                    )
                  ],
                )
              ],
            ),
          )
        ],
      ),
    );
  }
}
// SİNEMATİK (ERİME) SAYFA GEÇİŞ MOTORU
void yumusakGecisYap(BuildContext context, Widget gidilecekSayfa, {bool eskiSayfayiKapat = false}) {
  HapticFeedback.lightImpact(); // Tıklama hissiyatı

  var gecisAyari = PageRouteBuilder(
    transitionDuration: const Duration(milliseconds: 400), // Geçiş hızı
    pageBuilder: (context, animation, secondaryAnimation) => gidilecekSayfa,
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      return FadeTransition(
        opacity: animation,
        child: child,
      );
    },
  );

  // Eğer giriş yapma veya render başlama gibi geri dönülmeyecek bir sayfa ise eskisini kapat:
  if (eskiSayfayiKapat) {
    Navigator.pushReplacement(context, gecisAyari);
  } else {
    // Normal ileri gitme:
    Navigator.push(context, gecisAyari);
  }
}