import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'sistem_ve_dil.dart';
import 'ortak_widgetlar.dart';
import 'sayfalar_islem.dart';
import 'sekme_anasayfa.dart';
import 'sekme_kesfet.dart';
import 'sekme_magaza.dart';
import 'sekme_profil.dart';
import 'sekme_bildirim.dart';
import 'servisler/api_servisi.dart';
import 'servisler/auth_servisi.dart';
import 'modeller/kullanici_model.dart';

// ── SPLASH SCREEN ──
class AcilisSayfasi extends StatefulWidget {
  const AcilisSayfasi({super.key});
  @override
  State<AcilisSayfasi> createState() => _AcilisSayfasiState();
}

class _AcilisSayfasiState extends State<AcilisSayfasi> {
  @override
  void initState() {
    super.initState();
    _checkAuth();
  }

  Future<void> _checkAuth() async {
    await Future.delayed(const Duration(seconds: 2));
    if (!mounted) return;
    final isLoggedIn = await AuthServisi().isLoggedIn();
    if (isLoggedIn) {
      yumusakGecisYap(context, const AnaSayfa(), eskiSayfayiKapat: true);
    } else {
      yumusakGecisYap(context, const GirisSayfasi(), eskiSayfayiKapat: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: arkaplanRengi(),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(width: 200, height: 200, decoration: const BoxDecoration(image: DecorationImage(image: AssetImage('assets/LOGO101.png'), fit: BoxFit.contain))),
            const SizedBox(height: 24),
            Text('Modif AI', style: TextStyle(color: yaziRengi(), fontSize: 40, fontWeight: FontWeight.bold, letterSpacing: 3.0)),
            const SizedBox(height: 8),
            const Text('AI CAR TUNING STUDIO', style: TextStyle(color: Colors.blueAccent, fontSize: 12, letterSpacing: 2.0)),
            const SizedBox(height: 60),
            const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Color(0xFF257bf4), strokeWidth: 2)),
          ],
        ),
      ),
    );
  }
}

// ── GİRİŞ SAYFASI ──
class GirisSayfasi extends StatefulWidget {
  const GirisSayfasi({super.key});
  @override
  State<GirisSayfasi> createState() => _GirisSayfasiState();
}

class _GirisSayfasiState extends State<GirisSayfasi> {
  final TextEditingController kullaniciAdiGirdisi = TextEditingController();
  final TextEditingController sifreGirdisi = TextEditingController();
  bool _isYukleniyor = false;
  bool _showTutorial = true;

  Future<void> _girisYap(BuildContext context) async {
    HapticFeedback.mediumImpact();
    String email = kullaniciAdiGirdisi.text.trim();
    String sifre = sifreGirdisi.text.trim();
    if (email.isEmpty || sifre.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('Lütfen tüm alanları doldurun!')), backgroundColor: Colors.orange, behavior: SnackBarBehavior.floating));
      return;
    }
    setState(() { _isYukleniyor = true; });
    try {
      await ApiServisi().girisYap(email, sifre);
      if (mounted) yumusakGecisYap(context, const AnaSayfa(), eskiSayfayiKapat: true);
    } catch (hata) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(hata.toString().replaceAll("Exception: ", "")), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
    } finally {
      if (mounted) setState(() { _isYukleniyor = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<String>(
      valueListenable: appLanguage,
      builder: (context, lang, child) {
        final Color anaRenk = const Color(0xFF257bf4);
        final Color koyuArkaplan = const Color(0xFF0A1017);
        final Color koyuYuzey = const Color(0xFF182434);
        return Scaffold(
          backgroundColor: koyuArkaplan,
          resizeToAvoidBottomInset: true,
          body: Stack(
            children: [
              Positioned.fill(child: Image.network('https://images.unsplash.com/photo-1542282088-fe8426682b8f?q=80&w=1000&auto=format&fit=crop', fit: BoxFit.cover)),
              Positioned.fill(child: Container(decoration: BoxDecoration(gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Colors.transparent, koyuArkaplan.withOpacity(0.8), koyuArkaplan], stops: const [0.0, 0.6, 1.0])))),
              SafeArea(
                child: Align(
                  alignment: Alignment.bottomCenter,
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 20.0),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Center(
                          child: Stack(
                            alignment: Alignment.center,
                            children: [
                              Container(
                                width: 90,
                                height: 90,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  gradient: LinearGradient(
                                    colors: [anaRenk.withOpacity(0.6), anaRenk.withOpacity(0.1)],
                                    begin: Alignment.topLeft,
                                    end: Alignment.bottomRight,
                                  ),
                                  boxShadow: [
                                    BoxShadow(color: anaRenk.withOpacity(0.4), blurRadius: 24, spreadRadius: 4),
                                  ],
                                ),
                              ),
                              const Icon(Icons.directions_car_filled, size: 48, color: Colors.white),
                              const Positioned(right: 16, top: 16, child: Icon(Icons.auto_awesome, size: 24, color: Colors.amber)),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text(t('app_title'), textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontSize: 32, fontWeight: FontWeight.bold, letterSpacing: 1.5)),
                        const SizedBox(height: 8),
                        Text(t('welcome_title'), textAlign: TextAlign.center, style: const TextStyle(color: Colors.grey, fontSize: 14)),
                        const SizedBox(height: 48),
                        TextField(controller: kullaniciAdiGirdisi, style: const TextStyle(color: Colors.white), decoration: InputDecoration(filled: true, fillColor: koyuYuzey.withOpacity(0.8), hintText: t('username'), hintStyle: const TextStyle(color: Colors.grey), prefixIcon: const Icon(Icons.person, color: Colors.grey), border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none), focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide(color: anaRenk, width: 2)))),
                        const SizedBox(height: 16),
                        TextField(controller: sifreGirdisi, obscureText: true, style: const TextStyle(color: Colors.white), decoration: InputDecoration(filled: true, fillColor: koyuYuzey.withOpacity(0.8), hintText: t('password'), hintStyle: const TextStyle(color: Colors.grey), prefixIcon: const Icon(Icons.lock, color: Colors.grey), border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none), focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide(color: anaRenk, width: 2)))),
                        const SizedBox(height: 24),
                        ElevatedButton(
                          onPressed: _isYukleniyor ? null : () => _girisYap(context),
                          style: ElevatedButton.styleFrom(backgroundColor: anaRenk, padding: const EdgeInsets.symmetric(vertical: 16), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)), elevation: 8),
                          child: _isYukleniyor ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 3)) : Text(t('login'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white)),
                        ),
                        const SizedBox(height: 16),
                        TextButton(
                          onPressed: () => yumusakGecisYap(context, const KayitSayfasi()),
                          child: RichText(text: TextSpan(text: t('no_account'), style: const TextStyle(color: Colors.grey, fontSize: 14), children: [TextSpan(text: t('signup'), style: TextStyle(color: anaRenk, fontWeight: FontWeight.bold))])),
                        ),
                        const SizedBox(height: 32),
                      ],
                    ),
                  ),
                ),
              ),
              if (_showTutorial)
                Positioned.fill(
                  child: Container(
                    color: koyuArkaplan.withOpacity(0.95),
                    child: SafeArea(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.auto_fix_high, size: 80, color: anaRenk),
                          const SizedBox(height: 32),
                          Text(t('onboarding_1'), textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold, height: 1.2)),
                          const SizedBox(height: 16),
                          Text(t('onboarding_2'), textAlign: TextAlign.center, style: const TextStyle(color: Colors.grey, fontSize: 16)),
                          const SizedBox(height: 64),
                          ElevatedButton(
                            onPressed: () => setState(() => _showTutorial = false),
                            style: ElevatedButton.styleFrom(backgroundColor: anaRenk, padding: const EdgeInsets.symmetric(horizontal: 48, vertical: 16), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
                            child: Text(t('onboarding_start'), style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                          )
                        ]
                      )
                    )
                  )
                ),
            ],
          ),
        );
      },
    );
  }
}

// ── KAYIT SAYFASI ──
class KayitSayfasi extends StatefulWidget {
  const KayitSayfasi({super.key});
  @override
  State<KayitSayfasi> createState() => _KayitSayfasiState();
}

class _KayitSayfasiState extends State<KayitSayfasi> {
  final _adCtrl = TextEditingController();
  final _soyadCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _sifreCtrl = TextEditingController();
  bool _isYukleniyor = false;

  Future<void> _kayitOl() async {
    if (_adCtrl.text.trim().isEmpty || _soyadCtrl.text.trim().isEmpty || _emailCtrl.text.trim().isEmpty || _sifreCtrl.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Lütfen tüm alanları doldurun!'), backgroundColor: Colors.orange, behavior: SnackBarBehavior.floating));
      return;
    }
    if (_sifreCtrl.text.trim().length < 8) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Şifre en az 8 karakter olmalı!'), backgroundColor: Colors.orange, behavior: SnackBarBehavior.floating));
      return;
    }
    setState(() => _isYukleniyor = true);
    try {
      await ApiServisi().kayitOl(name: _adCtrl.text.trim(), surname: _soyadCtrl.text.trim(), email: _emailCtrl.text.trim(), password: _sifreCtrl.text.trim());
      await ApiServisi().girisYap(_emailCtrl.text.trim(), _sifreCtrl.text.trim());
      if (mounted) yumusakGecisYap(context, const AnaSayfa(), eskiSayfayiKapat: true);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceAll("Exception: ", "")), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
    } finally {
      if (mounted) setState(() => _isYukleniyor = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final Color anaRenk = const Color(0xFF257bf4);
    final Color koyuArkaplan = arkaplanRengi();
    final Color koyuYuzey = yuzeyRengi();
    InputDecoration _dec(String hint, IconData icon) => InputDecoration(filled: true, fillColor: koyuYuzey.withOpacity(0.8), hintText: hint, hintStyle: const TextStyle(color: Colors.grey), prefixIcon: Icon(icon, color: Colors.grey), border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none), focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide(color: anaRenk, width: 2)));

    return Scaffold(
      backgroundColor: koyuArkaplan,
      appBar: AppBar(backgroundColor: Colors.transparent, elevation: 0, leading: IconButton(icon: Icon(Icons.arrow_back, color: yaziRengi()), onPressed: () => Navigator.pop(context)), title: Text(t('signup'), style: TextStyle(color: yaziRengi())), centerTitle: true),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Icon(Icons.person_add, size: 64, color: yaziRengi()),
              const SizedBox(height: 32),
              TextField(controller: _adCtrl, style: TextStyle(color: yaziRengi()), decoration: _dec('Ad', Icons.person)),
              const SizedBox(height: 16),
              TextField(controller: _soyadCtrl, style: TextStyle(color: yaziRengi()), decoration: _dec('Soyad', Icons.person_outline)),
              const SizedBox(height: 16),
              TextField(controller: _emailCtrl, style: TextStyle(color: yaziRengi()), keyboardType: TextInputType.emailAddress, decoration: _dec('E-posta', Icons.email)),
              const SizedBox(height: 16),
              TextField(controller: _sifreCtrl, obscureText: true, style: TextStyle(color: yaziRengi()), decoration: _dec('Şifre (min 8 karakter)', Icons.lock)),
              const SizedBox(height: 32),
              ElevatedButton(
                onPressed: _isYukleniyor ? null : _kayitOl,
                style: ElevatedButton.styleFrom(backgroundColor: anaRenk, padding: const EdgeInsets.symmetric(vertical: 16), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
                child: _isYukleniyor ? const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 3)) : Text(t('signup'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── ANA SAYFA (TAB YÖNETİCİSİ) ──
class AnaSayfa extends StatefulWidget {
  final int initialIndex;
  const AnaSayfa({super.key, this.initialIndex = 0});
  @override
  State<AnaSayfa> createState() => _AnaSayfaState();
}

class _AnaSayfaState extends State<AnaSayfa> {
  late int _seciliSayfaIndex;
  final Color anaRenk = const Color(0xFF257bf4);

  bool _yukleniyor = true;
  
  Kullanici? _kullanici;
  int _kredi = 0;

  @override
  void initState() {
    super.initState();
    _seciliSayfaIndex = widget.initialIndex;
    _kullaniciBilgileriniYukle();
    // Bildirim badge'ini yükle
    BildirimServisi.okunmamisSayisiniGuncelle();
  }

  Future<void> _kullaniciBilgileriniYukle() async {
    try {
      final kullanici = await ApiServisi().beniBilgileriniGetir();
      final krediInfo = await ApiServisi().krediBilgisiGetir();
      if (mounted) setState(() { _kullanici = kullanici; _kredi = krediInfo.credits; _yukleniyor = false; });
    } catch (e) {
      if (mounted) setState(() => _yukleniyor = false);
    }
  }

  void _diliSec() {
    showModalBottomSheet(context: context, backgroundColor: yuzeyRengi(), shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))), builder: (context) {
      return SafeArea(child: Column(mainAxisSize: MainAxisSize.min, children: [
        Padding(padding: const EdgeInsets.all(16.0), child: Text(t('select_lang_title'), style: TextStyle(color: yaziRengi(), fontSize: 18, fontWeight: FontWeight.bold))),
        ListTile(leading: const Text('🇹🇷', style: TextStyle(fontSize: 24)), title: Text('Türkçe', style: TextStyle(color: yaziRengi())), onTap: () { appLanguage.value = 'tr'; Navigator.pop(context); }),
        ListTile(leading: const Text('🇬🇧', style: TextStyle(fontSize: 24)), title: Text('English', style: TextStyle(color: yaziRengi())), onTap: () { appLanguage.value = 'en'; Navigator.pop(context); }),
        const SizedBox(height: 20),
      ]));
    });
  }

  Widget _sayfaIceriginiGetir() {
    switch (_seciliSayfaIndex) {
      case 0: return SekmeAnaSayfa(kullanici: _kullanici, kredi: _kredi);
      case 1: return const SekmeKesfet();
      case 2: return SekmeMagaza(onCreditsChanged: _kullaniciBilgileriniYukle);
      case 3:
        return SekmeProfil(
          kullanici: _kullanici,
          kredi: _kredi,
          onTopUpTap: () { setState(() { _seciliSayfaIndex = 2; }); },
          onLangTap: _diliSec,
          onProfileUpdated: _kullaniciBilgileriniYukle,
        );
      default: return SekmeAnaSayfa(kullanici: _kullanici, kredi: _kredi);
    }
  }

  // Madde 10: Bildirim badge ile çan ikonu
  Widget _bildirimButonuOlustur() {
    return ValueListenableBuilder<int>(
      valueListenable: okunmamisBildirimSayisi,
      builder: (context, sayi, child) {
        return Stack(
          clipBehavior: Clip.none,
          children: [
            Container(
              decoration: BoxDecoration(color: yaziRengi().withOpacity(0.05), shape: BoxShape.circle),
              child: IconButton(
                icon: Icon(Icons.notifications_none, color: yaziRengi()),
                onPressed: () async {
                  await Navigator.push(context, MaterialPageRoute(builder: (c) => const BildirimSayfasi()));
                  // Geri dönünce badge güncelle
                  BildirimServisi.okunmamisSayisiniGuncelle();
                },
              ),
            ),
            if (sayi > 0)
              Positioned(
                right: 2, top: 2,
                child: Container(
                  padding: const EdgeInsets.all(4),
                  decoration: BoxDecoration(color: Colors.red, shape: BoxShape.circle, border: Border.all(color: arkaplanRengi(), width: 2)),
                  constraints: const BoxConstraints(minWidth: 20, minHeight: 20),
                  child: Text('$sayi', style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold), textAlign: TextAlign.center),
                ),
              ),
          ],
        );
      },
    );
  }

  Widget _ustBilgiOlustur() {
    final profilUrl = ApiServisi.buildImageUrl(_kullanici?.profilImageUrl);
    return GlassHeader(
      child: SafeArea(
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(children: [
              Stack(children: [
                Container(width: 48, height: 48, decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: anaRenk.withOpacity(0.3), width: 2), image: profilUrl != null ? DecorationImage(image: NetworkImage(profilUrl), fit: BoxFit.cover) : null, color: profilUrl == null ? yuzeyRengi() : null), child: profilUrl == null ? const Icon(Icons.person, color: Colors.grey) : null),
                Positioned(bottom: 0, right: 0, child: Container(width: 12, height: 12, decoration: BoxDecoration(color: Colors.green, shape: BoxShape.circle, border: Border.all(color: arkaplanRengi(), width: 2)))),
              ]),
              const SizedBox(width: 16),
              // Madde 5: AI Auto Studio kaldırıldı
              Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                Text('${t('welcome_greeting')}, ${_kullanici?.name ?? '...'}! 👋', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: yaziRengi())),
              ]),
            ]),
            _bildirimButonuOlustur(),
          ],
        ),
      ),
    );
  }

  Widget _floatingAppBarOlustur() {
    if (_seciliSayfaIndex == 0) return Positioned(top: 0, left: 0, right: 0, child: _ustBilgiOlustur());
    if (_seciliSayfaIndex == 3) return Positioned(top: 0, left: 0, right: 0, child: GlassHeader(child: SafeArea(child: Text(_kullanici?.fullName ?? '', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: yaziRengi())))));
    return const SizedBox.shrink();
  }

  Widget _altMenusuButonuOlustur(IconData ikon, String etiket, int index) {
    bool aktifMi = _seciliSayfaIndex == index;
    return MaterialButton(minWidth: 40, onPressed: () { if (!aktifMi) HapticFeedback.lightImpact(); setState(() { _seciliSayfaIndex = index; }); }, child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [Icon(ikon, color: aktifMi ? anaRenk : Colors.grey, size: 24), Text(etiket, style: TextStyle(color: aktifMi ? anaRenk : Colors.grey, fontSize: 10))]));
  }

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<String>(
      valueListenable: appLanguage,
      builder: (context, lang, child) {
        return ValueListenableBuilder<bool>(
          valueListenable: isDarkMode,
          builder: (context, dark, child) {
            return PopScope(
              canPop: false,
              onPopInvokedWithResult: (didPop, result) async {
                if (didPop) return;
                HapticFeedback.lightImpact();
                await showDialog(context: context, builder: (context) => AlertDialog(backgroundColor: yuzeyRengi(), title: Text(t('exit_app'), style: TextStyle(color: yaziRengi())), content: Text(t('exit_sure'), style: TextStyle(color: ikinciYaziRengi())), actions: [TextButton(onPressed: () => Navigator.of(context).pop(false), child: Text(t('no'), style: const TextStyle(color: Colors.grey))), ElevatedButton(style: ElevatedButton.styleFrom(backgroundColor: anaRenk), onPressed: () { SystemNavigator.pop(); }, child: Text(t('yes'), style: const TextStyle(color: Colors.white)))]));
              },
              child: Scaffold(
                backgroundColor: arkaplanRengi(),
                extendBodyBehindAppBar: true,
                body: Stack(children: [_sayfaIceriginiGetir(), _floatingAppBarOlustur()]),
                floatingActionButton: FloatingActionButton(onPressed: () { HapticFeedback.lightImpact(); yumusakGecisYap(context, const ProjeTipiSecimSayfasi()); }, backgroundColor: anaRenk, shape: const CircleBorder(), elevation: 8, child: const Icon(Icons.auto_fix_high, color: Colors.white, size: 28)),
                floatingActionButtonLocation: FloatingActionButtonLocation.centerDocked,
                bottomNavigationBar: BottomAppBar(color: yuzeyRengi(), shape: const CircularNotchedRectangle(), notchMargin: 8.0, child: SizedBox(height: 60, child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: <Widget>[_altMenusuButonuOlustur(Icons.home, t('home_tab'), 0), _altMenusuButonuOlustur(Icons.photo_library_outlined, t('discover_tab'), 1), const SizedBox(width: 40), _altMenusuButonuOlustur(Icons.diamond_outlined, t('store_tab'), 2), _altMenusuButonuOlustur(Icons.person_outline, t('profile_tab'), 3)]))),
              ),
            );
          },
        );
      },
    );
  }
}