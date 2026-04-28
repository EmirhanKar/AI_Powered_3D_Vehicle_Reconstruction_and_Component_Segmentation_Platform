import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import 'sistem_ve_dil.dart';
import 'ortak_widgetlar.dart';
import 'modeller/kullanici_model.dart';
import 'servisler/api_servisi.dart';
import 'servisler/auth_servisi.dart';
import 'sayfalar_ana.dart';

class SekmeProfil extends StatefulWidget {
  final Kullanici? kullanici;
  final int kredi;
  final VoidCallback? onTopUpTap;
  final VoidCallback? onLangTap;
  final VoidCallback? onProfileUpdated;
  const SekmeProfil({super.key, this.kullanici, this.kredi = 0, this.onTopUpTap, this.onLangTap, this.onProfileUpdated});
  @override
  State<SekmeProfil> createState() => _SekmeProfilState();
}

class _SekmeProfilState extends State<SekmeProfil> {
  final Color anaRenk = const Color(0xFF257bf4);

  // Madde 4: Yasal metinler — URL yönlendirmeli
  static const String _kvkkUrl = 'https://modifai.app/legal/kvkk';
  static const String _termsUrl = 'https://modifai.app/legal/terms';
  static const String _privacyUrl = 'https://modifai.app/legal/privacy';

  Future<void> _yasalSayfaAc(String baslik, String url) async {
    HapticFeedback.lightImpact();
    final uri = Uri.parse(url);
    try {
      final canLaunch = await canLaunchUrl(uri);
      if (canLaunch) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      } else {
        // URL açılamıyorsa uygulama içi taslak metni göster
        if (mounted) _taslakMetniGoster(baslik);
      }
    } catch (_) {
      if (mounted) _taslakMetniGoster(baslik);
    }
  }

  void _taslakMetniGoster(String baslik) {
    String icerik = '';
    if (baslik.contains('KVKK') || baslik.contains('Data')) {
      icerik = '''KVKK AYDINLATMA METNİ

Modif AI olarak kişisel verilerinizin güvenliği konusunda büyük önem veriyoruz.

6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK) kapsamında;

1. VERİ SORUMLUSU
Modif AI uygulama hizmetleri kapsamında veri sorumlusu olarak hareket etmekteyiz.

2. TOPLANAN KİŞİSEL VERİLER
• Ad, soyad, e-posta adresi
• Profil fotoğrafı
• Araç fotoğrafları ve 3D model verileri
• Uygulama kullanım istatistikleri

3. VERİLERİN İŞLENME AMAÇLARI
• Uygulama hizmetlerinin sunulması
• 3D model ve 2D modifikasyon oluşturulması
• Kullanıcı deneyiminin geliştirilmesi
• Yasal yükümlülüklerin yerine getirilmesi

4. VERİLERİN AKTARIMI
Kişisel verileriniz üçüncü kişilerle paylaşılmamaktadır. Sadece AI işleme servisleri kapsamında güvenli sunucularda işlenmektedir.

5. HAKLARINIZ
KVKK kapsamında; kişisel verilerinizin işlenip işlenmediğini öğrenme, silinmesini isteme ve itiraz etme haklarınız bulunmaktadır.

İletişim: modifai.destek@gmail.com''';
    } else if (baslik.contains('Kullanım') || baslik.contains('Terms')) {
      icerik = '''KULLANIM KOŞULLARI

Son güncellenme: ${DateTime.now().year}

1. KABUL
Modif AI uygulamasını kullanarak bu kullanım koşullarını kabul etmiş sayılırsınız.

2. HİZMET TANIMI
Modif AI, yapay zeka destekli araç modifiye ve 3D modelleme hizmeti sunan bir mobil uygulamadır.

3. KULLANICI YÜKÜMLÜLÜKLERİ
• Hesap bilgilerinizi güvenli tutmalısınız
• Yüklediğiniz fotoğrafların size ait olduğunu garanti edersiniz
• Uygulamayı kötü amaçlı kullanmayacağınızı taahhüt edersiniz

4. KREDİ SİSTEMİ
• Krediler satın alındıktan sonra iade edilmez
• Kredi fiyatları değişikliğe tabidir
• Abonelik süresi dolduğunda otomatik yenilenmez

5. FİKRİ MÜLKİYET
AI tarafından üretilen görseller ve modeller, kullanıcıya ait olmak üzere lisanslanır.

6. SORUMLULUK REDDİ
Uygulama "olduğu gibi" sunulmaktadır. Render kalitesi, fotoğraf kalitesine bağlıdır.

İletişim: modifai.destek@gmail.com''';
    } else {
      icerik = '''GİZLİLİK POLİTİKASI

Son güncellenme: ${DateTime.now().year}

1. GİRİŞ
Bu gizlilik politikası, Modif AI uygulamasının kişisel verilerinizi nasıl topladığını ve kullandığını açıklar.

2. TOPLANAN BİLGİLER
• Kayıt bilgileri: ad, soyad, e-posta
• Araç fotoğrafları
• Cihaz bilgileri ve kullanım verileri

3. BİLGİLERİN KULLANIMI
• Hizmet sunumu ve iyileştirmesi
• AI model işleme
• Bildirim gönderimi
• Güvenlik ve dolandırıcılık önleme

4. BİLGİ PAYLAŞIMI
Kişisel bilgileriniz üçüncü taraflarla satılmaz veya kiralanmaz. Yalnızca hizmet sağlayıcılarımızla (sunucu, AI işleme) sınırlı paylaşım yapılır.

5. VERİ GÜVENLİĞİ
Verileriniz şifreleme ve güvenli bağlantılar (HTTPS) ile korunmaktadır.

6. ÇEREZLER
Uygulama içi oturum yönetimi için yerel depolama kullanılır.

7. İLETİŞİM
Gizlilik politikamızla ilgili sorularınız için: modifai.destek@gmail.com''';
    }

    Navigator.push(context, MaterialPageRoute(builder: (c) {
      return Scaffold(
        backgroundColor: arkaplanRengi(),
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          leading: IconButton(icon: Icon(Icons.arrow_back, color: yaziRengi()), onPressed: () => Navigator.pop(c)),
          title: Text(baslik, style: TextStyle(color: yaziRengi(), fontSize: 16, fontWeight: FontWeight.bold)),
          centerTitle: true,
        ),
        body: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(16), border: Border.all(color: kartBorderRengi())),
            child: Text(icerik, style: TextStyle(color: yaziRengi(), fontSize: 13, height: 1.7)),
          ),
        ),
      );
    }));
  }

  // Madde 11: Tema seçimi
  void _temaSecDialoguGoster() {
    HapticFeedback.lightImpact();
    showModalBottomSheet(
      context: context,
      backgroundColor: yuzeyRengi(),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) {
        return SafeArea(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Padding(padding: const EdgeInsets.all(16), child: Text(t('theme_title'), style: TextStyle(color: yaziRengi(), fontSize: 20, fontWeight: FontWeight.bold))),
            ListTile(
              leading: Container(
                width: 40, height: 40,
                decoration: BoxDecoration(color: const Color(0xFF0A1017), shape: BoxShape.circle, border: Border.all(color: isDarkMode.value ? anaRenk : Colors.grey, width: isDarkMode.value ? 2 : 1)),
                child: const Icon(Icons.dark_mode, color: Colors.white, size: 20),
              ),
              title: Text(t('theme_dark'), style: TextStyle(color: yaziRengi(), fontWeight: isDarkMode.value ? FontWeight.bold : FontWeight.normal)),
              trailing: isDarkMode.value ? Icon(Icons.check_circle, color: anaRenk) : null,
              onTap: () { temaKaydet(true); Navigator.pop(ctx); },
            ),
            ListTile(
              leading: Container(
                width: 40, height: 40,
                decoration: BoxDecoration(color: Colors.white, shape: BoxShape.circle, border: Border.all(color: !isDarkMode.value ? anaRenk : Colors.grey, width: !isDarkMode.value ? 2 : 1)),
                child: const Icon(Icons.light_mode, color: Color(0xFF1A1A2E), size: 20),
              ),
              title: Text(t('theme_light'), style: TextStyle(color: yaziRengi(), fontWeight: !isDarkMode.value ? FontWeight.bold : FontWeight.normal)),
              trailing: !isDarkMode.value ? Icon(Icons.check_circle, color: anaRenk) : null,
              onTap: () { temaKaydet(false); Navigator.pop(ctx); },
            ),
            const SizedBox(height: 20),
          ]),
        );
      },
    );
  }

  void _hesapSilDialoguGoster() {
    showDialog(context: context, builder: (ctx) => AlertDialog(
      backgroundColor: yuzeyRengi(),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      title: Text(t('delete_account_title'), style: TextStyle(color: yaziRengi(), fontWeight: FontWeight.bold)),
      content: Text(t('delete_account_confirm'), style: TextStyle(color: ikinciYaziRengi())),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: Text(t('cancel'), style: const TextStyle(color: Colors.grey))),
        ElevatedButton(
          onPressed: () async {
            Navigator.pop(ctx);
            try {
              await ApiServisi().hesapSil();
              await AuthServisi().logout();
              if (mounted) yumusakGecisYap(context, const GirisSayfasi(), eskiSayfayiKapat: true);
            } catch (e) {
              if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString()), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
            }
          },
          style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
          child: Text(t('delete_account_btn'), style: const TextStyle(color: Colors.white)),
        ),
      ],
    ));
  }

  @override
  Widget build(BuildContext context) {
    final k = widget.kullanici;
    final profilUrl = ApiServisi.buildImageUrl(k?.profilImageUrl);

    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.only(top: 80),
        child: Column(
          children: [
            // Profil kartı
            Container(
              margin: const EdgeInsets.all(24),
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(24), border: Border.all(color: kartBorderRengi())),
              child: Column(children: [
                // Avatar
                Stack(children: [
                  Container(
                    width: 80, height: 80,
                    decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: anaRenk.withOpacity(0.5), width: 3), image: profilUrl != null ? DecorationImage(image: NetworkImage(profilUrl), fit: BoxFit.cover) : null, color: profilUrl == null ? arkaplanRengi() : null),
                    child: profilUrl == null ? const Icon(Icons.person, color: Colors.grey, size: 40) : null,
                  ),
                  Positioned(bottom: 0, right: 0, child: InkWell(
                    onTap: () { ortakYakindaToastGoster(context); },
                    child: Container(padding: const EdgeInsets.all(4), decoration: BoxDecoration(color: anaRenk, shape: BoxShape.circle, border: Border.all(color: yuzeyRengi(), width: 2)), child: const Icon(Icons.edit, color: Colors.white, size: 14)),
                  )),
                ]),
                const SizedBox(height: 16),
                Text(k?.fullName ?? '...', style: TextStyle(color: yaziRengi(), fontSize: 22, fontWeight: FontWeight.bold)),
                Text(k?.email ?? '', style: TextStyle(color: ikinciYaziRengi(), fontSize: 12)),
                const SizedBox(height: 20),
                // Kredi bilgisi
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(color: arkaplanRengi(), borderRadius: BorderRadius.circular(16)),
                  child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                    Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(t('active_balance'), style: TextStyle(color: ikinciYaziRengi(), fontSize: 12)),
                      const SizedBox(height: 4),
                      Row(children: [const Icon(Icons.diamond, color: Colors.amber, size: 24), const SizedBox(width: 8), Text('${widget.kredi}', style: premiumNumberStyle.copyWith(color: yaziRengi(), fontSize: 28))]),
                    ]),
                    ElevatedButton(
                      onPressed: widget.onTopUpTap,
                      style: ElevatedButton.styleFrom(backgroundColor: anaRenk, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
                      child: Text(t('top_up'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                    ),
                  ]),
                ),
                const SizedBox(height: 12),
                // İstatistikler
                Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
                  _profilIstatistik(Icons.view_in_ar, '${k?.renderImage ?? 0}', t('total_renders')),
                  Container(width: 1, height: 30, color: kartBorderRengi()),
                  _profilIstatistik(Icons.image, '${k?.createImage ?? 0}', t('created')),
                ]),
              ]),
            ),
            // Ayarlar
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(t('settings'), style: TextStyle(color: yaziRengi(), fontSize: 20, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                _ayarButonu(t('lang_select'), Icons.language, () => widget.onLangTap?.call()),
                _ayarButonu(t('theme_select'), Icons.palette, _temaSecDialoguGoster),
                _ayarButonu(t('edit_user'), Icons.person, () => ortakYakindaToastGoster(context)),
                _ayarButonu(t('history'), Icons.history, () => ortakYakindaToastGoster(context)),
                const SizedBox(height: 24),
                // Yasal bilgiler
                Text(t('legal_title'), style: TextStyle(color: yaziRengi(), fontSize: 20, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                _ayarButonu(t('kvkk'), Icons.shield, () => _yasalSayfaAc(t('kvkk'), _kvkkUrl)),
                _ayarButonu(t('terms'), Icons.description, () => _yasalSayfaAc(t('terms'), _termsUrl)),
                _ayarButonu(t('privacy'), Icons.privacy_tip, () => _yasalSayfaAc(t('privacy'), _privacyUrl)),
                const SizedBox(height: 24),
                // Çıkış ve hesap silme
                _ayarButonu(t('logout'), Icons.logout, () async {
                  await AuthServisi().logout();
                  if (mounted) yumusakGecisYap(context, const GirisSayfasi(), eskiSayfayiKapat: true);
                }, renk: Colors.orangeAccent),
                _ayarButonu(t('delete_account'), Icons.delete_forever, _hesapSilDialoguGoster, renk: Colors.redAccent),
                const SizedBox(height: 100),
              ]),
            ),
          ],
        ),
      ),
    );
  }

  Widget _profilIstatistik(IconData ikon, String deger, String etiket) {
    return Column(children: [
      Icon(ikon, color: anaRenk, size: 20),
      const SizedBox(height: 4),
      Text(deger, style: premiumNumberStyle.copyWith(color: yaziRengi(), fontSize: 18)),
      Text(etiket, style: TextStyle(color: ikinciYaziRengi(), fontSize: 10)),
    ]);
  }

  Widget _ayarButonu(String etiket, IconData ikon, VoidCallback onTap, {Color? renk}) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(12), border: Border.all(color: kartBorderRengi())),
        child: Row(children: [
          Icon(ikon, color: renk ?? anaRenk, size: 20),
          const SizedBox(width: 12),
          Expanded(child: Text(etiket, style: TextStyle(color: renk ?? yaziRengi(), fontSize: 14, fontWeight: FontWeight.w500))),
          Icon(Icons.arrow_forward_ios, color: ikinciYaziRengi(), size: 14),
        ]),
      ),
    );
  }
}