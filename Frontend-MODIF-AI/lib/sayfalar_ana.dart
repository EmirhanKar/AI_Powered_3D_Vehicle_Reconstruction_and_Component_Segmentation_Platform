import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
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
import 'sayfalar/onboarding_sayfasi.dart';

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

    // İlk açılış kontrolü: Onboarding gösterilmemişse yönlendir
    final prefs = await SharedPreferences.getInstance();
    final onboardingGoruldu = prefs.getBool('onboarding_seen') ?? false;

    if (!onboardingGoruldu) {
      await prefs.setBool('onboarding_seen', true);
      // İlk açılışta tutorial flag'ini de sıfırla
      await prefs.setBool('first_time_tutorial', true);
      if (!mounted) return;
      yumusakGecisYap(context, const OnboardingSayfasi(), eskiSayfayiKapat: true);
      return;
    }

    // Token kontrolü: giriş yapılmışsa doğrudan ana sayfaya, yoksa yine ana sayfaya (misafir)
    final isLoggedIn = await AuthServisi().isLoggedIn();
    if (isLoggedIn) {
      // Token varsa doğrulamayı dene
      try {
        await ApiServisi().beniBilgileriniGetir();
      } catch (_) {
        // Token geçersizse temizle (misafir olarak devam)
        await AuthServisi().logout();
      }
    }
    if (!mounted) return;
    yumusakGecisYap(context, const AnaSayfa(), eskiSayfayiKapat: true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: arkaplanRengi(),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 200,
              height: 200,
              decoration: const BoxDecoration(
                image: DecorationImage(
                  image: AssetImage('assets/LOGO101.png'),
                  fit: BoxFit.contain,
                ),
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Modif AI',
              style: TextStyle(
                color: yaziRengi(),
                fontSize: 40,
                fontWeight: FontWeight.bold,
                letterSpacing: 3.0,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'AI CAR TUNING STUDIO',
              style: TextStyle(
                color: Colors.blueAccent,
                fontSize: 12,
                letterSpacing: 2.0,
              ),
            ),
            const SizedBox(height: 60),
            const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(
                color: Color(0xFF257bf4),
                strokeWidth: 2,
              ),
            ),
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


  Future<void> _girisYap(BuildContext context) async {
    if (titresimAcik.value) HapticFeedback.mediumImpact();
    String email = kullaniciAdiGirdisi.text.trim();
    String sifre = sifreGirdisi.text.trim();
    if (email.isEmpty || sifre.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(t('Lütfen tüm alanları doldurun!')),
          backgroundColor: Colors.orange,
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }
    setState(() {
      _isYukleniyor = true;
    });
    try {
      await ApiServisi().girisYap(email, sifre);
      if (mounted)
        yumusakGecisYap(context, const AnaSayfa(), eskiSayfayiKapat: true);
    } catch (hata) {
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(hata.toString().replaceAll("Exception: ", "")),
            backgroundColor: Colors.redAccent,
            behavior: SnackBarBehavior.floating,
          ),
        );
    } finally {
      if (mounted)
        setState(() {
          _isYukleniyor = false;
        });
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
              Positioned.fill(
                child: Image.network(
                  'https://images.unsplash.com/photo-1542282088-fe8426682b8f?q=80&w=1000&auto=format&fit=crop',
                  fit: BoxFit.cover,
                  errorBuilder: (c, e, s) => Container(color: koyuArkaplan),
                ),
              ),
              Positioned.fill(
                child: Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        Colors.transparent,
                        koyuArkaplan.withValues(alpha: 0.8),
                        koyuArkaplan,
                      ],
                      stops: const [0.0, 0.6, 1.0],
                    ),
                  ),
                ),
              ),
              SafeArea(
                child: Align(
                  alignment: Alignment.bottomCenter,
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 24.0,
                      vertical: 20.0,
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Center(
                          child: Image.asset(
                            'assets/LOGO101.png',
                            width: 120,
                            height: 120,
                            fit: BoxFit.contain,
                          ),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          t('app_title'),
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 32,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 1.5,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          t('welcome_title'),
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            color: Colors.grey,
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 48),
                        TextField(
                          controller: kullaniciAdiGirdisi,
                          style: const TextStyle(color: Colors.white),
                          decoration: InputDecoration(
                            filled: true,
                            fillColor: koyuYuzey.withValues(alpha: 0.8),
                            hintText: 'E-posta',
                            hintStyle: const TextStyle(color: Colors.grey),
                            prefixIcon: const Icon(
                              Icons.email,
                              color: Colors.grey,
                            ),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                              borderSide: BorderSide.none,
                            ),
                            focusedBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                              borderSide: BorderSide(color: anaRenk, width: 2),
                            ),
                          ),
                        ),
                        const SizedBox(height: 16),
                        TextField(
                          controller: sifreGirdisi,
                          obscureText: true,
                          style: const TextStyle(color: Colors.white),
                          decoration: InputDecoration(
                            filled: true,
                            fillColor: koyuYuzey.withValues(alpha: 0.8),
                            hintText: t('password'),
                            hintStyle: const TextStyle(color: Colors.grey),
                            prefixIcon: const Icon(
                              Icons.lock,
                              color: Colors.grey,
                            ),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                              borderSide: BorderSide.none,
                            ),
                            focusedBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                              borderSide: BorderSide(color: anaRenk, width: 2),
                            ),
                          ),
                        ),
                        const SizedBox(height: 24),
                        ElevatedButton(
                          onPressed: _isYukleniyor
                              ? null
                              : () => _girisYap(context),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: anaRenk,
                            padding: const EdgeInsets.symmetric(vertical: 16),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                            elevation: 8,
                          ),
                          child: _isYukleniyor
                              ? const SizedBox(
                                  width: 24,
                                  height: 24,
                                  child: CircularProgressIndicator(
                                    color: Colors.white,
                                    strokeWidth: 3,
                                  ),
                                )
                              : Text(
                                  t('login'),
                                  style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.bold,
                                    color: Colors.white,
                                  ),
                                ),
                        ),
                        const SizedBox(height: 16),
                        TextButton(
                          onPressed: () =>
                              yumusakGecisYap(context, const KayitSayfasi()),
                          child: RichText(
                            text: TextSpan(
                              text: t('no_account'),
                              style: const TextStyle(
                                color: Colors.grey,
                                fontSize: 14,
                              ),
                              children: [
                                TextSpan(
                                  text: t('signup'),
                                  style: TextStyle(
                                    color: anaRenk,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(height: 32),
                      ],
                    ),
                  ),
                ),
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
    if (_adCtrl.text.trim().isEmpty ||
        _soyadCtrl.text.trim().isEmpty ||
        _emailCtrl.text.trim().isEmpty ||
        _sifreCtrl.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Lütfen tüm alanları doldurun!'),
          backgroundColor: Colors.orange,
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }
    if (_sifreCtrl.text.trim().length < 8) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Şifre en az 8 karakter olmalı!'),
          backgroundColor: Colors.orange,
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }
    setState(() => _isYukleniyor = true);
    try {
      await ApiServisi().kayitOl(
        name: _adCtrl.text.trim(),
        surname: _soyadCtrl.text.trim(),
        email: _emailCtrl.text.trim(),
        password: _sifreCtrl.text.trim(),
      );
      await ApiServisi().girisYap(
        _emailCtrl.text.trim(),
        _sifreCtrl.text.trim(),
      );
      if (mounted)
        yumusakGecisYap(context, const AnaSayfa(), eskiSayfayiKapat: true);
    } catch (e) {
      if (mounted)
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(e.toString().replaceAll("Exception: ", "")),
            backgroundColor: Colors.redAccent,
            behavior: SnackBarBehavior.floating,
          ),
        );
    } finally {
      if (mounted) setState(() => _isYukleniyor = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final Color anaRenk = const Color(0xFF257bf4);
    final Color koyuArkaplan = arkaplanRengi();
    final Color koyuYuzey = yuzeyRengi();
    InputDecoration _dec(String hint, IconData icon) => InputDecoration(
      filled: true,
      fillColor: koyuYuzey.withValues(alpha: 0.8),
      hintText: hint,
      hintStyle: const TextStyle(color: Colors.grey),
      prefixIcon: Icon(icon, color: Colors.grey),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide.none,
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: anaRenk, width: 2),
      ),
    );

    return Scaffold(
      backgroundColor: koyuArkaplan,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: yaziRengi()),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(t('signup'), style: TextStyle(color: yaziRengi())),
        centerTitle: true,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Icon(Icons.person_add, size: 64, color: yaziRengi()),
              const SizedBox(height: 32),
              TextField(
                controller: _adCtrl,
                style: TextStyle(color: yaziRengi()),
                decoration: _dec('Ad', Icons.person),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _soyadCtrl,
                style: TextStyle(color: yaziRengi()),
                decoration: _dec('Soyad', Icons.person_outline),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _emailCtrl,
                style: TextStyle(color: yaziRengi()),
                keyboardType: TextInputType.emailAddress,
                decoration: _dec('E-posta', Icons.email),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _sifreCtrl,
                obscureText: true,
                style: TextStyle(color: yaziRengi()),
                decoration: _dec('Şifre (min 8 karakter)', Icons.lock),
              ),
              const SizedBox(height: 32),
              ElevatedButton(
                onPressed: _isYukleniyor ? null : _kayitOl,
                style: ElevatedButton.styleFrom(
                  backgroundColor: anaRenk,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                child: _isYukleniyor
                    ? const SizedBox(
                        width: 24,
                        height: 24,
                        child: CircularProgressIndicator(
                          color: Colors.white,
                          strokeWidth: 3,
                        ),
                      )
                    : Text(
                        t('signup'),
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
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

  // Tutorial Keys
  final GlobalKey kesfetKey = GlobalKey();
  final GlobalKey magazaKey = GlobalKey();
  final GlobalKey profilKey = GlobalKey();
  final GlobalKey fabKey = GlobalKey();

  int _tutorialStep = -1; // -1: Kapalı, 0-6: Adımlar
  bool _isTutorialAnimating = false;

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

    // Madde 6: Tanıtım kontrolü
    _tanitimiBaslat();
  }

  Future<void> _tanitimiBaslat() async {
    final prefs = await SharedPreferences.getInstance();
    
    // YENİ: Kullanıcı giriş yapmışsa (misafir değilse) tanıtım gösterme.
    // Tanıtım sadece misafir (guest) akışı için tasarlandı.
    if (await AuthServisi().isLoggedIn()) {
      await prefs.setBool('first_time_tutorial', false);
      return;
    }

    final firstTime = prefs.getBool('first_time_tutorial') ?? true;
    if (firstTime) {
      await Future.delayed(const Duration(milliseconds: 1500));
      if (mounted) setState(() => _tutorialStep = 0);
      await prefs.setBool('first_time_tutorial', false);
    }
  }

  Future<void> _nextTutorial() async {
    if (_tutorialStep == -1 || _isTutorialAnimating) return;
    _isTutorialAnimating = true;

    int nextStep = _tutorialStep + 1;
    if (nextStep > 8) {
      setState(() => _tutorialStep = -1);
      return;
    }

    // Hide overlay during transition to prevent red screens due to missing contexts
    if (mounted) setState(() => _tutorialStep = -2);

    // Tab geçişleri
    if (nextStep == 4 || nextStep == 5) {
      if (_seciliSayfaIndex != 1) {
        setState(() => _seciliSayfaIndex = 1); // Keşfet
        await Future.delayed(const Duration(milliseconds: 300));
      }
    } else if (nextStep == 6) {
      if (_seciliSayfaIndex != 2) {
        setState(() => _seciliSayfaIndex = 2); // Mağaza
        await Future.delayed(const Duration(milliseconds: 300));
      }
    } else if (nextStep == 7) {
      if (_seciliSayfaIndex != 3) {
        setState(() => _seciliSayfaIndex = 3); // Profil
        await Future.delayed(const Duration(milliseconds: 300));
      }
    } else if (nextStep <= 3) {
      if (_seciliSayfaIndex != 0) {
        setState(() => _seciliSayfaIndex = 0);
        await Future.delayed(const Duration(milliseconds: 300));
      }

      // Kaydırma işlemi
      GlobalKey? key;
      if (nextStep == 0)
        key = SekmeAnaSayfa.newProjectKey;
      else if (nextStep == 1)
        key = SekmeAnaSayfa.statsKey;
      else if (nextStep == 2)
        key = SekmeAnaSayfa.garageKey;
      else if (nextStep == 3)
        key = SekmeAnaSayfa.draftsKey;

      if (key?.currentContext != null) {
        Scrollable.ensureVisible(
          key!.currentContext!,
          duration: const Duration(milliseconds: 500),
          curve: Curves.easeInOut,
        );
        await Future.delayed(const Duration(milliseconds: 500));
      }
    }

    if (mounted) setState(() => _tutorialStep = nextStep);
    _isTutorialAnimating = false;
  }

  Future<void> _kullaniciBilgileriniYukle() async {
    // BUG-04 FIX: Token yoksa API çağrısı yapma
    final isLoggedIn = await AuthServisi().isLoggedIn();
    if (!isLoggedIn) {
      if (mounted) setState(() => _yukleniyor = false);
      return;
    }
    try {
      final kullanici = await ApiServisi().beniBilgileriniGetir();
      final krediInfo = await ApiServisi().krediBilgisiGetir();
      if (mounted)
        setState(() {
          _kullanici = kullanici;
          _kredi = krediInfo.credits;
          _yukleniyor = false;
        });
    } catch (e) {
      if (mounted) setState(() => _yukleniyor = false);
    }
  }

  void _diliSec() {
    showModalBottomSheet(
      context: context,
      backgroundColor: yuzeyRengi(),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        return SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Padding(
                padding: const EdgeInsets.all(16.0),
                child: Text(
                  t('select_lang_title'),
                  style: TextStyle(
                    color: yaziRengi(),
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              ListTile(
                leading: const Text('🇹🇷', style: TextStyle(fontSize: 24)),
                title: Text('Türkçe', style: TextStyle(color: yaziRengi())),
                onTap: () {
                  appLanguage.value = 'tr';
                  Navigator.pop(context);
                },
              ),
              ListTile(
                leading: const Text('🇬🇧', style: TextStyle(fontSize: 24)),
                title: Text('English', style: TextStyle(color: yaziRengi())),
                onTap: () {
                  appLanguage.value = 'en';
                  Navigator.pop(context);
                },
              ),
              const SizedBox(height: 20),
            ],
          ),
        );
      },
    );
  }

  Widget _sayfaIceriginiGetir() {
    bool isGuest = !_yukleniyor && _kullanici == null;
    switch (_seciliSayfaIndex) {
      case 0:
        return SekmeAnaSayfa(kullanici: _kullanici, kredi: _kredi, isGuest: isGuest, headerWidget: _ustBilgiOlustur());
      case 1:
        return SekmeKesfet(isGuest: isGuest);
      case 2:
        return SekmeMagaza(onCreditsChanged: _kullaniciBilgileriniYukle, isGuest: isGuest);
      case 3:
        return SekmeProfil(
          kullanici: _kullanici,
          kredi: _kredi,
          isGuest: isGuest,
          onTopUpTap: () {
            setState(() {
              _seciliSayfaIndex = 2;
            });
          },
          onLangTap: _diliSec,
          onProfileUpdated: _kullaniciBilgileriniYukle,
        );
      default:
        return SekmeAnaSayfa(kullanici: _kullanici, kredi: _kredi, isGuest: isGuest);
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
              decoration: BoxDecoration(
                color: yaziRengi().withValues(alpha: 0.05),
                shape: BoxShape.circle,
              ),
              child: IconButton(
                icon: Icon(Icons.notifications_none, color: yaziRengi()),
                onPressed: () async {
                  await Navigator.push(
                    context,
                    MaterialPageRoute(builder: (c) => const BildirimSayfasi()),
                  );
                  // Geri dönünce badge güncelle
                  BildirimServisi.okunmamisSayisiniGuncelle();
                },
              ),
            ),
            if (sayi > 0)
              Positioned(
                right: 2,
                top: 2,
                child: Container(
                  padding: const EdgeInsets.all(4),
                  decoration: BoxDecoration(
                    color: Colors.red,
                    shape: BoxShape.circle,
                    border: Border.all(color: arkaplanRengi(), width: 2),
                  ),
                  constraints: const BoxConstraints(
                    minWidth: 20,
                    minHeight: 20,
                  ),
                  child: Text(
                    '$sayi',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                    ),
                    textAlign: TextAlign.center,
                  ),
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
            Row(
              children: [
                Stack(
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: anaRenk.withValues(alpha: 0.3),
                          width: 2,
                        ),
                        image: profilUrl != null
                            ? DecorationImage(
                                image: NetworkImage(profilUrl),
                                fit: BoxFit.cover,
                              )
                            : null,
                        color: profilUrl == null ? yuzeyRengi() : null,
                      ),
                      child: profilUrl == null
                          ? const Icon(Icons.person, color: Colors.grey)
                          : null,
                    ),
                    Positioned(
                      bottom: 0,
                      right: 0,
                      child: Container(
                        width: 12,
                        height: 12,
                        decoration: BoxDecoration(
                          color: Colors.green,
                          shape: BoxShape.circle,
                          border: Border.all(color: arkaplanRengi(), width: 2),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(width: 16),
                // Madde 5: AI Auto Studio kaldırıldı
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      '${t('welcome_greeting')}, ${_kullanici?.name ?? 'Misafir'}! 👋',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: yaziRengi(),
                      ),
                    ),
                  ],
                ),
              ],
            ),
            _bildirimButonuOlustur(),
          ],
        ),
      ),
    );
  }

  // _floatingAppBarOlustur() was removed to allow the header to scroll with the page.

  Widget _altMenusuButonuOlustur(
    IconData ikon,
    String etiket,
    int index, {
    GlobalKey? key,
  }) {
    bool aktifMi = _seciliSayfaIndex == index;
    return MaterialButton(
      key: key,
      minWidth: 40,
      onPressed: () {
        if (!aktifMi) if (titresimAcik.value) HapticFeedback.lightImpact();
        setState(() {
          _seciliSayfaIndex = index;
        });
      },
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(ikon, color: aktifMi ? anaRenk : Colors.grey, size: 24),
          Text(
            etiket,
            style: TextStyle(
              color: aktifMi ? anaRenk : Colors.grey,
              fontSize: 10,
            ),
          ),
        ],
      ),
    );
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
                if (titresimAcik.value) HapticFeedback.lightImpact();
                await showDialog(
                  context: context,
                  builder: (context) => AlertDialog(
                    backgroundColor: yuzeyRengi(),
                    title: Text(
                      t('exit_app'),
                      style: TextStyle(color: yaziRengi()),
                    ),
                    content: Text(
                      t('exit_sure'),
                      style: TextStyle(color: ikinciYaziRengi()),
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.of(context).pop(false),
                        child: Text(
                          t('no'),
                          style: const TextStyle(color: Colors.grey),
                        ),
                      ),
                      ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: anaRenk,
                        ),
                        onPressed: () {
                          SystemNavigator.pop();
                        },
                        child: Text(
                          t('yes'),
                          style: const TextStyle(color: Colors.white),
                        ),
                      ),
                    ],
                  ),
                );
              },
              child: Scaffold(
                backgroundColor: arkaplanRengi(),
                extendBodyBehindAppBar: true,
                body: Stack(
                  children: [
                    _sayfaIceriginiGetir(),
                    if (_tutorialStep != -1) _tutorialOverlayOlustur(),
                  ],
                ),
                floatingActionButton: FloatingActionButton(
                  key: fabKey,
                  onPressed: () {
                    if (titresimAcik.value) HapticFeedback.lightImpact();
                    bool wasInTutorial = false;
                    if (_tutorialStep == 8) {
                      setState(() => _tutorialStep = -1);
                      wasInTutorial = true;
                    }
                    bool isGuest = !_yukleniyor && _kullanici == null;
                    yumusakGecisYap(context, ProjeTipiSecimSayfasi(isGuest: isGuest, startTutorial: wasInTutorial));
                  },
                  backgroundColor: anaRenk,
                  shape: const CircleBorder(),
                  elevation: 8,
                  child: const Icon(
                    Icons.auto_fix_high,
                    color: Colors.white,
                    size: 28,
                  ),
                ),
                floatingActionButtonLocation:
                    FloatingActionButtonLocation.centerDocked,
                bottomNavigationBar: BottomAppBar(
                  color: yuzeyRengi(),
                  shape: const CircularNotchedRectangle(),
                  notchMargin: 8.0,
                  child: SizedBox(
                    height: 60,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: <Widget>[
                        _altMenusuButonuOlustur(Icons.home, t('home_tab'), 0),
                        _altMenusuButonuOlustur(
                          Icons.photo_library_outlined,
                          t('discover_tab'),
                          1,
                          key: kesfetKey,
                        ),
                        const SizedBox(width: 40),
                        _altMenusuButonuOlustur(
                          Icons.diamond_outlined,
                          t('store_tab'),
                          2,
                          key: magazaKey,
                        ),
                        _altMenusuButonuOlustur(
                          Icons.person_outline,
                          t('profile_tab'),
                          3,
                          key: profilKey,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _tutorialOverlayOlustur() {
    GlobalKey targetKey;
    String title, desc;

    switch (_tutorialStep) {
      case 0:
        targetKey = SekmeAnaSayfa.newProjectKey;
        title = "Yeni Proje";
        desc = "Buradan AI ile yeni bir modifiye projesi başlatabilirsin.";
        break;
      case 1:
        targetKey = SekmeAnaSayfa.statsKey;
        title = "İstatistiklerin";
        desc = "Render sayını ve mevcut kredilerini buradan takip edebilirsin.";
        break;
      case 2:
        targetKey = SekmeAnaSayfa.garageKey;
        title = "Garajın";
        desc = "Daha önce yaptığın tüm çalışmaları burada görebilirsin.";
        break;
      case 3:
        targetKey = SekmeAnaSayfa.draftsKey;
        title = "Taslaklar";
        desc = "Yarım kalan projelerine buradan devam edebilirsin.";
        break;
      case 4:
        targetKey = SekmeKesfet.likeKey;
        title = "Beğen";
        desc = "Topluluğun en alevli tasarımlarına '🔥' bırakabilirsin.";
        break;
      case 5:
        targetKey = SekmeKesfet.commentKey;
        title = "Yorum Yap";
        desc = "Tasarımlar hakkında fikirlerini paylaş ve diğer kullanıcılarla etkileşime geç.";
        break;
      case 6:
        targetKey = magazaKey;
        title = "Mağaza";
        desc = "Arkadaşlarını davet ederek kredi kazanabilir veya yeni kredi paketleri alabilirsin.";
        break;
      case 7:
        targetKey = profilKey;
        title = "Profil";
        desc = "Hesap bilgilerini, yasal metinleri ve iletişim detaylarını buradan yönet.";
        break;
      case 8:
        targetKey = fabKey;
        title = "Başla!";
        desc = "Tüm bu özellikleri kullanmak için sihirbaz değneğine tıkla ve projeni oluştur!";
        break;
      default:
        return const SizedBox.shrink();
    }

    return GestureDetector(
      onTap: _tutorialStep == 8 ? null : _nextTutorial,
      child: Material(
        color: Colors.transparent,
        child: SpotlightWidget(
          targetKey: targetKey,
          title: title,
          desc: desc,
          currentStep: _tutorialStep,
          onNext: _nextTutorial,
          onFabTap: _tutorialStep == 8 ? () {
            setState(() => _tutorialStep = -1);
            bool isGuest = !_yukleniyor && _kullanici == null;
            yumusakGecisYap(context, ProjeTipiSecimSayfasi(isGuest: isGuest, startTutorial: true));
          } : null,
        ),
      ),
    );
  }
}

class SpotlightWidget extends StatefulWidget {
  final GlobalKey targetKey;
  final String title;
  final String desc;
  final int currentStep;
  final VoidCallback onNext;
  final VoidCallback? onFabTap;

  const SpotlightWidget({
    super.key,
    required this.targetKey,
    required this.title,
    required this.desc,
    required this.currentStep,
    required this.onNext,
    this.onFabTap,
  });

  @override
  State<SpotlightWidget> createState() => _SpotlightWidgetState();
}

class _SpotlightWidgetState extends State<SpotlightWidget>
    with SingleTickerProviderStateMixin {
  late AnimationController _arrowController;

  @override
  void initState() {
    super.initState();
    // BUG-08 FIX: Sonsuz döngü ok animasyonu
    _arrowController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _arrowController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final RenderBox? renderBox =
        widget.targetKey.currentContext?.findRenderObject() as RenderBox?;
    if (renderBox == null) return const SizedBox.shrink();

    final size = renderBox.size;
    final offset = renderBox.localToGlobal(Offset.zero);

    return Stack(
      children: [
        // Spotlight Hole with Glow
        Positioned.fill(
          child: ColorFiltered(
            colorFilter: ColorFilter.mode(
              Colors.black.withValues(alpha: 0.92),
              BlendMode.srcOut,
            ),
            child: Stack(
              children: [
                Positioned.fill(
                  child: Container(color: Colors.transparent),
                ),
                Positioned(
                  left: offset.dx - 4,
                  top: offset.dy - 4,
                  child: Container(
                    width: size.width + 8,
                    height: size.height + 8,
                    decoration: BoxDecoration(
                      color: Colors.black,
                      borderRadius: BorderRadius.circular(widget.currentStep == 8 ? 50 : (widget.currentStep >= 9 ? 24 : 12)),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),

        // Arrow pointing to FAB for step 8
        if (widget.currentStep == 8)
          Positioned(
            left: offset.dx + size.width / 2 - 24,
            top: offset.dy - 60,
            child: AnimatedBuilder(
              animation: _arrowController,
              builder: (context, child) {
                return Transform.translate(
                  offset: Offset(0, _arrowController.value * 15),
                  child: const Icon(
                    Icons.keyboard_double_arrow_down,
                    color: Colors.white,
                    size: 48,
                  ),
                );
              },
            ),
          ),
        // Information Box
        Positioned(
          left: 24,
          right: 24,
          // Box position logic: dynamically calculate to avoid screen cutoff
          top: (offset.dy + size.height + 230 > MediaQuery.of(context).size.height)
              ? (offset.dy - 200 < 50 ? 50 : offset.dy - 200)
              : offset.dy + size.height + 20,
          child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0.0, end: 1.0),
            duration: const Duration(milliseconds: 400),
            builder: (context, val, child) => Opacity(
              opacity: val,
              child: Transform.translate(
                offset: Offset(0, (1 - val) * 20),
                child: child,
              ),
            ),
            child: Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(20),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.4),
                    blurRadius: 30,
                    spreadRadius: 5,
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: Colors.blueAccent.withValues(alpha: 0.1),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.tips_and_updates,
                          color: Colors.blueAccent,
                          size: 20,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          widget.title,
                          style: const TextStyle(
                            color: Colors.black87,
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Text(
                    widget.desc,
                    style: const TextStyle(
                      color: Colors.black54,
                      fontSize: 14,
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 20),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        "${widget.currentStep + 1} / 9",
                        style: const TextStyle(
                          color: Colors.black38,
                          fontSize: 12,
                        ),
                      ),
                      if (widget.currentStep != 8)
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 8,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.blueAccent,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            widget.currentStep == 7 ? "Son Adım" : "Devam Et",
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
        // Fake hit area for step 8
        if (widget.currentStep == 8 && widget.onFabTap != null)
          Positioned(
            left: offset.dx,
            top: offset.dy,
            child: GestureDetector(
              onTap: widget.onFabTap,
              child: Container(
                width: size.width,
                height: size.height,
                color: Colors.transparent,
              ),
            ),
          ),
      ],
    );
  }
}
