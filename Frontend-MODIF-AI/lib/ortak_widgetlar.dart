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
            color: yuzeyRengi().withValues(alpha: isDarkMode.value ? 0.4 : 0.85),
            border: Border(bottom: BorderSide(color: kartBorderRengi(), width: 0.5)),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 12.0),
          child: child,
        ),
      ),
    );
  }
}

void ortadanSecimDialoguGoster(BuildContext context) {
  if (titresimAcik.value) HapticFeedback.lightImpact();
  showDialog(
    context: context,
    builder: (BuildContext context) {
      return AlertDialog(
        backgroundColor: yuzeyRengi(),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(t('photo_source'), textAlign: TextAlign.center, style: TextStyle(color: yaziRengi(), fontWeight: FontWeight.bold)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: Icon(Icons.camera_alt, color: yaziRengi()),
              title: Text(t('take_photo'), style: TextStyle(color: yaziRengi())),
              onTap: () {
                Navigator.pop(context);
                if (titresimAcik.value) HapticFeedback.selectionClick();
                ortakYakindaToastGoster(context);
              },
            ),
            const Divider(color: Colors.white10),
            ListTile(
              leading: Icon(Icons.photo_library, color: yaziRengi()),
              title: Text(t('choose_gallery'), style: TextStyle(color: yaziRengi())),
              onTap: () {
                Navigator.pop(context);
                if (titresimAcik.value) HapticFeedback.selectionClick();
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
  if (titresimAcik.value) HapticFeedback.lightImpact();
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



// Madde 7: ArabaKartiOlusturucu — işlevsel düzenle/paylaş/sil/3 nokta
class ArabaKartiOlusturucu {
  static Widget olustur(
    String baslik,
    String altBaslik,
    String resimUrl,
    String zaman,
    Color anaRenk,
    Color koyuYuzey, {
    int? scanId,
    VoidCallback? onDuzenle,
    VoidCallback? onPaylas,
    VoidCallback? onSil,
    VoidCallback? onDetay,
    bool showEditButton = true,
    VoidCallback? onGoster,
  }) {
    return Container(
      decoration: BoxDecoration(color: koyuYuzey, borderRadius: BorderRadius.circular(16), border: Border.all(color: kartBorderRengi())),
      child: Column(
        children: [
          Stack(
            children: [
              ClipRRect(borderRadius: const BorderRadius.vertical(top: Radius.circular(16)), child: Image.network(resimUrl, height: 150, width: double.infinity, fit: BoxFit.cover, loadingBuilder: (c, child, progress) { if (progress == null) return child; return Container(height: 150, width: double.infinity, color: koyuYuzey, child: Center(child: CircularProgressIndicator(strokeWidth: 2, color: anaRenk.withValues(alpha: 0.5)))); }, errorBuilder: (context, error, stackTrace) => Container(height: 150, width: double.infinity, color: koyuYuzey, child: Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [Icon(Icons.directions_car, color: ikinciYaziRengi(), size: 40), const SizedBox(height: 4), Text('Görsel yüklenemedi', style: TextStyle(color: ikinciYaziRengi(), fontSize: 10))]))))),
              Positioned(top: 10, right: 10, child: Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), decoration: BoxDecoration(color: Colors.black.withValues(alpha: 0.7), borderRadius: BorderRadius.circular(4)), child: Row(children: [const Icon(Icons.circle, color: Colors.green, size: 8), const SizedBox(width: 4), Text(t('completed'), style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold))]))),
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
                    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(baslik, style: TextStyle(color: yaziRengi(), fontSize: 16, fontWeight: FontWeight.bold)), Text(altBaslik, style: TextStyle(color: ikinciYaziRengi(), fontSize: 12))])),
                    // 3 nokta menüsü
                    PopupMenuButton<String>(
                      icon: Icon(Icons.more_vert, color: ikinciYaziRengi()),
                      color: yuzeyRengi(),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      onSelected: (value) {
                        switch (value) {
                          case 'detay': onDetay?.call(); break;
                          case 'sil': onSil?.call(); break;
                        }
                      },
                      itemBuilder: (ctx) => [
                        PopupMenuItem(value: 'detay', child: Row(children: [const Icon(Icons.info_outline, color: Colors.blueAccent, size: 18), const SizedBox(width: 8), Text(t('detail_btn'), style: TextStyle(color: yaziRengi()))])),
                        PopupMenuItem(value: 'sil', child: Row(children: [const Icon(Icons.delete_outline, color: Colors.redAccent, size: 18), const SizedBox(width: 8), Text(t('delete_btn'), style: const TextStyle(color: Colors.redAccent))])),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Divider(color: kartBorderRengi(), height: 1),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(children: [Icon(Icons.schedule, color: ikinciYaziRengi(), size: 14), const SizedBox(width: 4), Text(zaman, style: TextStyle(color: ikinciYaziRengi(), fontSize: 12))]),
                    Row(
                      children: [
                        // Paylaş butonu
                        InkWell(
                          onTap: onPaylas,
                          borderRadius: BorderRadius.circular(8),
                          child: Container(padding: const EdgeInsets.all(6), decoration: BoxDecoration(color: Colors.green.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(8)), child: const Icon(Icons.share, color: Colors.green, size: 16)),
                        ),
                        const SizedBox(width: 8),
                        // Göster butonu (Opsiyonel)
                        if (onGoster != null) ...[
                          InkWell(
                            onTap: onGoster,
                            borderRadius: BorderRadius.circular(8),
                            child: Container(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8), decoration: BoxDecoration(color: anaRenk, borderRadius: BorderRadius.circular(8)), child: const Text('Göster', style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold))),
                          ),
                          const SizedBox(width: 8),
                        ],
                        // Düzenle butonu
                        if (showEditButton)
                          InkWell(
                            onTap: onDuzenle,
                            borderRadius: BorderRadius.circular(8),
                            child: Container(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8), decoration: BoxDecoration(color: anaRenk, borderRadius: BorderRadius.circular(8)), child: Text(t('edit'), style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold))),
                          ),
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

// SİNEMATİK SAYFA GEÇİŞ MOTORU — Slide + Fade kombinasyonu
void yumusakGecisYap(BuildContext context, Widget gidilecekSayfa, {bool eskiSayfayiKapat = false}) {
  if (titresimAcik.value) HapticFeedback.lightImpact();

  var gecisAyari = PageRouteBuilder(
    transitionDuration: const Duration(milliseconds: 450),
    reverseTransitionDuration: const Duration(milliseconds: 350),
    pageBuilder: (context, animation, secondaryAnimation) => gidilecekSayfa,
    transitionsBuilder: (context, animation, secondaryAnimation, child) {
      final curvedAnimation = CurvedAnimation(
        parent: animation,
        curve: Curves.easeOutCubic,
        reverseCurve: Curves.easeInCubic,
      );
      return SlideTransition(
        position: Tween<Offset>(
          begin: const Offset(0.08, 0.0),
          end: Offset.zero,
        ).animate(curvedAnimation),
        child: FadeTransition(
          opacity: Tween<double>(begin: 0.0, end: 1.0).animate(curvedAnimation),
          child: child,
        ),
      );
    },
  );

  if (eskiSayfayiKapat) {
    Navigator.pushReplacement(context, gecisAyari);
  } else {
    Navigator.push(context, gecisAyari);
  }
}