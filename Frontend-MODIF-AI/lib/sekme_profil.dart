import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import 'dart:io';
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
  final bool isGuest;
  const SekmeProfil({
    super.key,
    this.kullanici,
    this.kredi = 0,
    this.onTopUpTap,
    this.onLangTap,
    this.onProfileUpdated,
    this.isGuest = false,
  });
  @override
  State<SekmeProfil> createState() => _SekmeProfilState();
}

class _SekmeProfilState extends State<SekmeProfil> {
  final Color anaRenk = const Color(0xFF257bf4);

  static const String _kvkkUrl = 'https://modifai.app/legal/kvkk';
  static const String _termsUrl = 'https://modifai.app/legal/terms';
  static const String _privacyUrl = 'https://modifai.app/legal/privacy';

  Future<void> _yasalSayfaAc(String baslik, String url) async {
    if (titresimAcik.value) HapticFeedback.lightImpact();
    final uri = Uri.parse(url);
    try {
      final canLaunch = await canLaunchUrl(uri);
      if (canLaunch) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      } else {
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
Kişisel verileriniz üçüncü kişilerle paylaşılmamaktadır.

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

4. KREDİ SİSTEMİ
• Krediler satın alındıktan sonra iade edilmez
• Kredi fiyatları değişikliğe tabidir

5. FİKRİ MÜLKİYET
AI tarafından üretilen görseller ve modeller, kullanıcıya ait olmak üzere lisanslanır.

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

4. VERİ GÜVENLİĞİ
Verileriniz şifreleme ve güvenli bağlantılar (HTTPS) ile korunmaktadır.

7. İLETİŞİM
Gizlilik politikamızla ilgili sorularınız için: modifai.destek@gmail.com''';
    }

    Navigator.push(context, MaterialPageRoute(builder: (c) {
      return Scaffold(
        backgroundColor: arkaplanRengi(),
        appBar: AppBar(
          backgroundColor: Colors.transparent, elevation: 0,
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

  void _temaSecDialoguGoster() {
    if (titresimAcik.value) HapticFeedback.lightImpact();
    showModalBottomSheet(
      context: context, backgroundColor: yuzeyRengi(),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) {
        return SafeArea(child: Column(mainAxisSize: MainAxisSize.min, children: [
          Padding(padding: const EdgeInsets.all(16), child: Text(t('theme_title'), style: TextStyle(color: yaziRengi(), fontSize: 20, fontWeight: FontWeight.bold))),
          ListTile(
            leading: Container(width: 40, height: 40, decoration: BoxDecoration(color: const Color(0xFF0A1017), shape: BoxShape.circle, border: Border.all(color: isDarkMode.value ? anaRenk : Colors.grey, width: isDarkMode.value ? 2 : 1)), child: const Icon(Icons.dark_mode, color: Colors.white, size: 20)),
            title: Text(t('theme_dark'), style: TextStyle(color: yaziRengi(), fontWeight: isDarkMode.value ? FontWeight.bold : FontWeight.normal)),
            trailing: isDarkMode.value ? Icon(Icons.check_circle, color: anaRenk) : null,
            onTap: () { temaKaydet(true); Navigator.pop(ctx); },
          ),
          ListTile(
            leading: Container(width: 40, height: 40, decoration: BoxDecoration(color: Colors.white, shape: BoxShape.circle, border: Border.all(color: !isDarkMode.value ? anaRenk : Colors.grey, width: !isDarkMode.value ? 2 : 1)), child: const Icon(Icons.light_mode, color: Color(0xFF1A1A2E), size: 20)),
            title: Text(t('theme_light'), style: TextStyle(color: yaziRengi(), fontWeight: !isDarkMode.value ? FontWeight.bold : FontWeight.normal)),
            trailing: !isDarkMode.value ? Icon(Icons.check_circle, color: anaRenk) : null,
            onTap: () { temaKaydet(false); Navigator.pop(ctx); },
          ),
          const SizedBox(height: 20),
        ]));
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

  // Task 11: Kullanıcı bilgilerini düzenle
  void _bilgileriDuzenleSayfasiAc() {
    if (titresimAcik.value) HapticFeedback.lightImpact();
    final k = widget.kullanici;
    final adCtrl = TextEditingController(text: k?.name ?? '');
    final soyadCtrl = TextEditingController(text: k?.surname ?? '');
    final emailCtrl = TextEditingController(text: k?.email ?? '');
    final telCtrl = TextEditingController(text: k?.phoneNumber ?? '');
    bool yukleniyor = false;

    Navigator.push(context, MaterialPageRoute(builder: (c) {
      return StatefulBuilder(builder: (ctx, setModalState) {
        return Scaffold(
          backgroundColor: arkaplanRengi(),
          appBar: AppBar(
            backgroundColor: Colors.transparent, elevation: 0,
            leading: IconButton(icon: Icon(Icons.arrow_back, color: yaziRengi()), onPressed: () => Navigator.pop(ctx)),
            title: Text(t('edit_profile_title'), style: TextStyle(color: yaziRengi(), fontSize: 16, fontWeight: FontWeight.bold)),
            centerTitle: true,
          ),
          body: SafeArea(child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              _duzenlemeAlani(adCtrl, t('edit_name'), Icons.person),
              const SizedBox(height: 16),
              _duzenlemeAlani(soyadCtrl, t('edit_surname'), Icons.person_outline),
              const SizedBox(height: 16),
              _duzenlemeAlani(emailCtrl, t('edit_email'), Icons.email, inputType: TextInputType.emailAddress),
              const SizedBox(height: 16),
              _duzenlemeAlani(telCtrl, t('edit_phone'), Icons.phone, inputType: TextInputType.phone),
              const SizedBox(height: 32),
              ElevatedButton(
                onPressed: yukleniyor ? null : () async {
                  setModalState(() => yukleniyor = true);
                  try {
                    await ApiServisi().profilGuncelle(
                      name: adCtrl.text.trim(),
                      surname: soyadCtrl.text.trim(),
                      email: emailCtrl.text.trim(),
                      phoneNumber: telCtrl.text.trim(),
                    );
                    widget.onProfileUpdated?.call();
                    if (ctx.mounted) {
                      ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text(t('profile_updated')), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating));
                      Navigator.pop(ctx);
                    }
                  } catch (e) {
                    if (ctx.mounted) ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text(e.toString().replaceAll("Exception: ", "")), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
                  } finally {
                    if (ctx.mounted) setModalState(() => yukleniyor = false);
                  }
                },
                style: ElevatedButton.styleFrom(backgroundColor: anaRenk, padding: const EdgeInsets.symmetric(vertical: 16), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
                child: yukleniyor
                    ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 3))
                    : Text(t('save_changes'), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white)),
              ),
            ]),
          )),
        );
      });
    }));
  }

  Widget _duzenlemeAlani(TextEditingController ctrl, String hint, IconData icon, {TextInputType inputType = TextInputType.text}) {
    return TextField(
      controller: ctrl,
      style: TextStyle(color: yaziRengi()),
      keyboardType: inputType,
      decoration: InputDecoration(
        filled: true, fillColor: yuzeyRengi(),
        hintText: hint, hintStyle: const TextStyle(color: Colors.grey),
        prefixIcon: Icon(icon, color: Colors.grey),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide(color: anaRenk, width: 2)),
      ),
    );
  }

  // Task 10: İletişim sayfası
  void _iletisimSayfasiAc() {
    if (titresimAcik.value) HapticFeedback.lightImpact();
    final konuCtrl = TextEditingController();
    final mesajCtrl = TextEditingController();
    XFile? ekFoto;
    bool gonderiliyor = false;

    Navigator.push(context, MaterialPageRoute(builder: (c) {
      return StatefulBuilder(builder: (ctx, setModalState) {
        return Scaffold(
          backgroundColor: arkaplanRengi(),
          appBar: AppBar(
            backgroundColor: Colors.transparent, elevation: 0,
            leading: IconButton(icon: Icon(Icons.arrow_back, color: yaziRengi()), onPressed: () => Navigator.pop(ctx)),
            title: Text(t('contact_title'), style: TextStyle(color: yaziRengi(), fontSize: 16, fontWeight: FontWeight.bold)),
            centerTitle: true,
          ),
          body: SafeArea(child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(16), border: Border.all(color: kartBorderRengi())),
                child: Column(children: [
                  Icon(Icons.support_agent, color: anaRenk, size: 48),
                  const SizedBox(height: 12),
                  Text(t('contact_btn'), style: TextStyle(color: yaziRengi(), fontSize: 18, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Text('info@modifiai.com', style: TextStyle(color: ikinciYaziRengi(), fontSize: 12)),
                ]),
              ),
              const SizedBox(height: 24),
              TextField(
                controller: konuCtrl, style: TextStyle(color: yaziRengi()),
                decoration: InputDecoration(filled: true, fillColor: yuzeyRengi(), hintText: t('contact_subject'), hintStyle: const TextStyle(color: Colors.grey), prefixIcon: const Icon(Icons.subject, color: Colors.grey), border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none), focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide(color: anaRenk, width: 2))),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: mesajCtrl, style: TextStyle(color: yaziRengi()), maxLines: 5,
                decoration: InputDecoration(filled: true, fillColor: yuzeyRengi(), hintText: t('contact_message'), hintStyle: const TextStyle(color: Colors.grey), border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none), focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide(color: anaRenk, width: 2))),
              ),
              const SizedBox(height: 16),
              // Fotoğraf ekleme
              InkWell(
                onTap: () async {
                  final picker = ImagePicker();
                  final photo = await picker.pickImage(source: ImageSource.gallery, maxWidth: 1920, imageQuality: 85);
                  if (photo != null) setModalState(() => ekFoto = photo);
                },
                borderRadius: BorderRadius.circular(16),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(16), border: Border.all(color: kartBorderRengi(), style: BorderStyle.solid)),
                  child: Row(children: [
                    Icon(Icons.attach_file, color: ikinciYaziRengi()),
                    const SizedBox(width: 12),
                    Expanded(child: Text(ekFoto != null ? ekFoto!.name : t('contact_attach'), style: TextStyle(color: ekFoto != null ? yaziRengi() : ikinciYaziRengi(), fontSize: 14))),
                    if (ekFoto != null) InkWell(onTap: () => setModalState(() => ekFoto = null), child: const Icon(Icons.close, color: Colors.redAccent, size: 20)),
                  ]),
                ),
              ),
              if (ekFoto != null) ...[
                const SizedBox(height: 12),
                ClipRRect(borderRadius: BorderRadius.circular(12), child: Image.file(File(ekFoto!.path), height: 120, width: double.infinity, fit: BoxFit.cover)),
              ],
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: gonderiliyor ? null : () async {
                  if (konuCtrl.text.trim().isEmpty || mesajCtrl.text.trim().isEmpty) {
                    ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text(t('contact_error')), backgroundColor: Colors.orange, behavior: SnackBarBehavior.floating));
                    return;
                  }
                  setModalState(() => gonderiliyor = true);
                  // E-posta gönder
                  final subject = Uri.encodeComponent(konuCtrl.text.trim());
                  final body = Uri.encodeComponent(mesajCtrl.text.trim());
                  final uri = Uri.parse('mailto:info@modifiai.com?subject=$subject&body=$body');
                  try {
                    await launchUrl(uri);
                  } catch (_) {}
                  if (ctx.mounted) {
                    ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text(t('contact_success')), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating));
                    Navigator.pop(ctx);
                  }
                },
                icon: gonderiliyor ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2)) : const Icon(Icons.send, color: Colors.white),
                label: Text(t('contact_send'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
                style: ElevatedButton.styleFrom(backgroundColor: anaRenk, padding: const EdgeInsets.symmetric(vertical: 16), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
              ),
            ]),
          )),
        );
      });
    }));
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
            if (!widget.isGuest)
              Container(
              margin: const EdgeInsets.all(24),
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(24), border: Border.all(color: kartBorderRengi())),
              child: Column(
                children: [
                  // Avatar
                  Stack(children: [
                    Container(
                      width: 80, height: 80,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(color: anaRenk.withValues(alpha: 0.5), width: 3),
                        image: profilUrl != null ? DecorationImage(image: NetworkImage(profilUrl), fit: BoxFit.cover) : null,
                        color: profilUrl == null ? arkaplanRengi() : null,
                      ),
                      child: profilUrl == null ? const Icon(Icons.person, color: Colors.grey, size: 40) : null,
                    ),
                    Positioned(bottom: 0, right: 0, child: InkWell(
                      onTap: () {
                        // BUG-14 FIX: Profil fotoğrafı düzenleme aktif
                        if (titresimAcik.value) HapticFeedback.lightImpact();
                        showModalBottomSheet(
                          context: context,
                          backgroundColor: yuzeyRengi(),
                          shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
                          builder: (ctx) {
                            return SafeArea(child: Column(mainAxisSize: MainAxisSize.min, children: [
                              Padding(padding: const EdgeInsets.all(16), child: Text(t('edit_profile_photo'), style: TextStyle(color: yaziRengi(), fontSize: 18, fontWeight: FontWeight.bold))),
                              ListTile(
                                leading: Icon(Icons.camera_alt, color: anaRenk),
                                title: Text(t('take_photo'), style: TextStyle(color: yaziRengi())),
                                onTap: () async {
                                  Navigator.pop(ctx);
                                  final photo = await ImagePicker().pickImage(source: ImageSource.camera, maxWidth: 800, imageQuality: 85);
                                  if (photo != null) {
                                    try {
                                      await ApiServisi().profilFotoYukle(photo);
                                      widget.onProfileUpdated?.call();
                                      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('profile_updated')), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating));
                                    } catch (e) {
                                      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceAll('Exception: ', '')), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
                                    }
                                  }
                                },
                              ),
                              ListTile(
                                leading: Icon(Icons.photo_library, color: anaRenk),
                                title: Text(t('choose_gallery'), style: TextStyle(color: yaziRengi())),
                                onTap: () async {
                                  Navigator.pop(ctx);
                                  final photo = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 800, imageQuality: 85);
                                  if (photo != null) {
                                    try {
                                      await ApiServisi().profilFotoYukle(photo);
                                      widget.onProfileUpdated?.call();
                                      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('profile_updated')), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating));
                                    } catch (e) {
                                      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceAll('Exception: ', '')), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
                                    }
                                  }
                                },
                              ),
                              const SizedBox(height: 16),
                            ]));
                          },
                        );
                      },
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
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(t('active_balance'), style: TextStyle(color: ikinciYaziRengi(), fontSize: 12)),
                          const SizedBox(height: 4),
                          Row(children: [
                            const Icon(Icons.diamond, color: Colors.amber, size: 24),
                            const SizedBox(width: 8),
                            Text('${widget.kredi}', style: premiumNumberStyle.copyWith(color: yaziRengi(), fontSize: 28)),
                          ]),
                        ]),
                        ElevatedButton(
                          onPressed: widget.onTopUpTap,
                          style: ElevatedButton.styleFrom(backgroundColor: anaRenk, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
                          child: Text(t('top_up'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                        ),
                      ],
                    ),
                  ),
                  // Task 3: İstatistik bölümü silindi (zaten ana sayfada var)
                ],
              ),
            ),
            // Ayarlar
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: widget.isGuest ? Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 24),
                  // Yasal bilgiler
                  Text(t('legal_title'), style: TextStyle(color: yaziRengi(), fontSize: 20, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 12),
                  _ayarButonu(t('kvkk'), Icons.shield, () => _yasalSayfaAc(t('kvkk'), _kvkkUrl)),
                  _ayarButonu(t('terms'), Icons.description, () => _yasalSayfaAc(t('terms'), _termsUrl)),
                  _ayarButonu(t('privacy'), Icons.privacy_tip, () => _yasalSayfaAc(t('privacy'), _privacyUrl)),
                  const SizedBox(height: 24),
                  // İletişim bölümü
                  Text(t('contact_title'), style: TextStyle(color: yaziRengi(), fontSize: 20, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 12),
                  _ayarButonu(t('contact_btn'), Icons.support_agent, _iletisimSayfasiAc),
                  const SizedBox(height: 48),
                  ElevatedButton.icon(
                    onPressed: () { yumusakGecisYap(context, const GirisSayfasi()); },
                    icon: const Icon(Icons.login, color: Colors.white),
                    label: const Text('Giriş Yap / Kayıt Ol', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                    style: ElevatedButton.styleFrom(backgroundColor: Colors.green, padding: const EdgeInsets.symmetric(vertical: 16), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
                  ),
                  const SizedBox(height: 100),
                ],
              ) : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(t('settings'), style: TextStyle(color: yaziRengi(), fontSize: 20, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                _ayarButonu(t('lang_select'), Icons.language, () => widget.onLangTap?.call()),
                _ayarButonu(t('theme_select'), Icons.palette, _temaSecDialoguGoster),
                _titresimAyarButonu(),
                // Task 11: Bilgileri düzenle — artık aktif
                _ayarButonu(t('edit_user'), Icons.person, _bilgileriDuzenleSayfasiAc),
                const SizedBox(height: 24),
                // Yasal bilgiler
                Text(t('legal_title'), style: TextStyle(color: yaziRengi(), fontSize: 20, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                _ayarButonu(t('kvkk'), Icons.shield, () => _yasalSayfaAc(t('kvkk'), _kvkkUrl)),
                _ayarButonu(t('terms'), Icons.description, () => _yasalSayfaAc(t('terms'), _termsUrl)),
                _ayarButonu(t('privacy'), Icons.privacy_tip, () => _yasalSayfaAc(t('privacy'), _privacyUrl)),
                const SizedBox(height: 24),
                // Task 10: İletişim bölümü
                Text(t('contact_title'), style: TextStyle(color: yaziRengi(), fontSize: 20, fontWeight: FontWeight.bold)),
                const SizedBox(height: 12),
                _ayarButonu(t('contact_btn'), Icons.support_agent, _iletisimSayfasiAc),
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

  Widget _titresimAyarButonu() {
    return ValueListenableBuilder<bool>(
      valueListenable: titresimAcik,
      builder: (context, isAcik, child) {
        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
          decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(12), border: Border.all(color: kartBorderRengi())),
          child: Row(
            children: [
              Expanded(child: Text('Titreşim', style: TextStyle(color: yaziRengi(), fontSize: 14, fontWeight: FontWeight.w500))),
              Switch(
                value: isAcik,
                activeColor: Colors.blueAccent,
                onChanged: (val) {
                  titresimKaydet(val);
                  if (val) if (titresimAcik.value) HapticFeedback.mediumImpact();
                },
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _ayarButonu(String etiket, IconData ikon, VoidCallback onTap, {Color? renk}) {
    return InkWell(
      onTap: onTap, borderRadius: BorderRadius.circular(12),
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(12), border: Border.all(color: kartBorderRengi())),
        child: Row(children: [
          Expanded(child: Text(etiket, style: TextStyle(color: renk ?? yaziRengi(), fontSize: 14, fontWeight: FontWeight.w500))),
          Icon(Icons.arrow_forward_ios, color: ikinciYaziRengi(), size: 14),
        ]),
      ),
    );
  }
}
