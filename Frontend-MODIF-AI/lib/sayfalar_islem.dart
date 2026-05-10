import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:io';
import 'sistem_ve_dil.dart';
import 'ortak_widgetlar.dart';
import 'sayfalar_ana.dart';
import 'oyun_sayfasi.dart';
import 'modeller/plugin_model.dart';
import 'servisler/api_servisi.dart';
import 'sayfalar/sablonlu_kamera.dart';

// ── PROJE TİPİ SEÇİMİ ──
class ProjeTipiSecimSayfasi extends StatefulWidget {
  final bool isGuest;
  final bool startTutorial;
  const ProjeTipiSecimSayfasi({
    super.key,
    this.isGuest = false,
    this.startTutorial = false,
  });

  @override
  State<ProjeTipiSecimSayfasi> createState() => _ProjeTipiSecimSayfasiState();
}

class _ProjeTipiSecimSayfasiState extends State<ProjeTipiSecimSayfasi> {
  bool _showInfoBox = false;

  @override
  void initState() {
    super.initState();
    if (widget.startTutorial) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        setState(() => _showInfoBox = true);
      });
    }
  }

  void _handleSelect(String method) {
    HapticFeedback.mediumImpact();
    if (widget.isGuest) {
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: const Color(0xFF182434),
          title: Text(
            "Giriş Yap",
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.bold,
            ),
          ),
          content: const Text(
            "Projelerini oluşturmak ve düzenlemek için giriş yapmalısın. Hadi seni kayıt ekranına alalım!",
            style: TextStyle(color: Colors.grey),
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text("Kapat", style: TextStyle(color: Colors.grey)),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF257bf4),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              onPressed: () {
                Navigator.pop(ctx);
                Navigator.pop(context); // Go back to Home
                // We assume user can switch to profile tab later.
              },
              child: const Text(
                "Anladım",
                style: TextStyle(color: Colors.white),
              ),
            ),
          ],
        ),
      );
    } else {
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (c) => FotografYuklemeSayfasi(method: method),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<String>(
      valueListenable: appLanguage,
      builder: (context, lang, child) {
        final Color koyuArkaplan = const Color(0xFF0A1017);
        return Scaffold(
          backgroundColor: koyuArkaplan,
          appBar: AppBar(
            backgroundColor: Colors.transparent,
            elevation: 0,
            leading: IconButton(
              icon: const Icon(Icons.arrow_back, color: Colors.white),
              onPressed: () => Navigator.pop(context),
            ),
            title: Text(
              t('select_project_type'),
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
            ),
            centerTitle: true,
            actions: [
              IconButton(
                icon: const Icon(Icons.info_outline, color: Colors.white),
                onPressed: () => setState(() => _showInfoBox = !_showInfoBox),
              ),
            ],
          ),
          body: Stack(
            children: [
              Column(
                children: [
                  Expanded(
                    child: GestureDetector(
                      onTap: () => _handleSelect('2d'),
                      child: Container(
                        margin: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(20),
                          image: DecorationImage(
                            image: const NetworkImage(
                              'https://images.unsplash.com/photo-1552519507-da3b142c6e3d?q=80&w=1000',
                            ),
                            fit: BoxFit.cover,
                            onError: (exception, stackTrace) {},
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.5),
                              blurRadius: 10,
                              spreadRadius: 2,
                            ),
                          ],
                        ),
                        child: Container(
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(20),
                            gradient: LinearGradient(
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                              colors: [
                                Colors.transparent,
                                Colors.black.withValues(alpha: 0.8),
                              ],
                            ),
                          ),
                          child: Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.end,
                              children: [
                                const Icon(
                                  Icons.image,
                                  color: Colors.white,
                                  size: 48,
                                ),
                                const SizedBox(height: 12),
                                Text(
                                  t('2d_mod'),
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 24,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  t('2d_desc'),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                    color: Colors.grey,
                                    fontSize: 14,
                                  ),
                                ),
                                const SizedBox(height: 12),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 16,
                                    vertical: 6,
                                  ),
                                  decoration: BoxDecoration(
                                    color: Colors.green.withValues(alpha: 0.2),
                                    borderRadius: BorderRadius.circular(12),
                                    border: Border.all(
                                      color: Colors.greenAccent.withValues(
                                        alpha: 0.5,
                                      ),
                                    ),
                                  ),
                                  child: Text(
                                    "30 ${t('credit_cost')}",
                                    style: const TextStyle(
                                      color: Colors.greenAccent,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 14,
                                    ),
                                  ),
                                ),
                                const SizedBox(height: 32),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  Expanded(
                    child: GestureDetector(
                      onTap: () => _handleSelect('3d'),
                      child: Container(
                        margin: const EdgeInsets.only(
                          left: 16,
                          right: 16,
                          bottom: 16,
                        ),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(20),
                          image: DecorationImage(
                            image: const NetworkImage(
                              'https://images.unsplash.com/photo-1617788138017-80ad40651399?q=80&w=1000',
                            ),
                            fit: BoxFit.cover,
                            onError: (exception, stackTrace) {},
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.blueAccent.withValues(alpha: 0.3),
                              blurRadius: 10,
                              spreadRadius: 2,
                            ),
                          ],
                        ),
                        child: Container(
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(20),
                            gradient: LinearGradient(
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                              colors: [
                                Colors.transparent,
                                Colors.blue.shade900.withValues(alpha: 0.9),
                              ],
                            ),
                          ),
                          child: Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.end,
                              children: [
                                const Icon(
                                  Icons.threed_rotation,
                                  color: Colors.white,
                                  size: 48,
                                ),
                                const SizedBox(height: 12),
                                Text(
                                  t('3d_mod'),
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 24,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  t('3d_desc'),
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                    color: Colors.grey,
                                    fontSize: 14,
                                  ),
                                ),
                                const SizedBox(height: 12),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 16,
                                    vertical: 6,
                                  ),
                                  decoration: BoxDecoration(
                                    color: Colors.green.withValues(alpha: 0.2),
                                    borderRadius: BorderRadius.circular(12),
                                    border: Border.all(
                                      color: Colors.greenAccent.withValues(
                                        alpha: 0.5,
                                      ),
                                    ),
                                  ),
                                  child: Text(
                                    "50 ${t('credit_cost')}",
                                    style: const TextStyle(
                                      color: Colors.greenAccent,
                                      fontWeight: FontWeight.bold,
                                      fontSize: 14,
                                    ),
                                  ),
                                ),
                                const SizedBox(height: 32),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              if (_showInfoBox)
                Positioned(
                  left: 24,
                  right: 24,
                  bottom: 24,
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
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Row(
                                children: [
                                  Container(
                                    padding: const EdgeInsets.all(8),
                                    decoration: BoxDecoration(
                                      color: Colors.blueAccent.withValues(
                                        alpha: 0.1,
                                      ),
                                      shape: BoxShape.circle,
                                    ),
                                    child: const Icon(
                                      Icons.tips_and_updates,
                                      color: Colors.blueAccent,
                                      size: 20,
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                  const Text(
                                    "Modül Bilgisi",
                                    style: TextStyle(
                                      color: Colors.black87,
                                      fontSize: 18,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ],
                              ),
                              IconButton(
                                icon: const Icon(
                                  Icons.close,
                                  color: Colors.black54,
                                ),
                                onPressed: () =>
                                    setState(() => _showInfoBox = false),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          const Text(
                            "🚗 2D Modifiye",
                            style: TextStyle(
                              color: Colors.black87,
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 4),
                          const Text(
                            "Aracının sadece dış görünümünü değiştirmek istiyorsan 2D modülü tam sana göre!",
                            style: TextStyle(
                              color: Colors.black54,
                              fontSize: 14,
                            ),
                          ),
                          const SizedBox(height: 16),
                          const Text(
                            "🏎️ 3D Modifiye",
                            style: TextStyle(
                              color: Colors.black87,
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 4),
                          const Text(
                            "Aracını baştan aşağı detaylıca şekillendirmek ve 3 boyutlu ortamda incelemek istersen bu modülü seç!",
                            style: TextStyle(
                              color: Colors.black54,
                              fontSize: 14,
                            ),
                          ),
                          const SizedBox(height: 20),
                          Align(
                            alignment: Alignment.centerRight,
                            child: InkWell(
                              onTap: () => setState(() => _showInfoBox = false),
                              borderRadius: BorderRadius.circular(8),
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 16,
                                  vertical: 8,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.blueAccent,
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: const Text(
                                  "Anladım",
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 12,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                            ),
                          ),
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

// ── FOTOĞRAF YÜKLEME (Hem 2D hem 3D) ──
class FotografYuklemeSayfasi extends StatefulWidget {
  final String method;
  const FotografYuklemeSayfasi({super.key, required this.method});
  @override
  State<FotografYuklemeSayfasi> createState() => _FotografYuklemeSayfasiState();
}

class _FotografYuklemeSayfasiState extends State<FotografYuklemeSayfasi> {
  final ImagePicker _picker = ImagePicker();
  final List<XFile> _seciliResimler = [];
  final _carNameCtrl = TextEditingController();
  ImageSource? _secilenKaynak;
  String _aracTipi = 'sedan'; // sedan, hatchback, suv

  List<String> get _acilar => widget.method == '2d'
      ? ['Ön', 'Arka', 'Sağ Yan', 'Sol Yan']
      : [
          'Ön',
          'Sağ Yan',
          'Sol Yan',
          'Arka',
          'Ön Sağ',
          'Ön Sol',
          'Arka Sağ',
          'Arka Sol',
        ];

  int get _gerekliSayi => widget.method == '2d' ? 4 : 8;

  Widget _buildAracTipiChip(String label, String tip, Color anaRenk, Color koyuYuzey) {
    final secili = _aracTipi == tip;
    return GestureDetector(
      onTap: () { HapticFeedback.selectionClick(); setState(() => _aracTipi = tip); },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: secili ? anaRenk.withValues(alpha: 0.15) : koyuYuzey,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: secili ? anaRenk : Colors.white.withValues(alpha: 0.1), width: secili ? 1.5 : 1),
        ),
        child: Text(label, style: TextStyle(color: secili ? anaRenk : Colors.grey, fontSize: 12, fontWeight: secili ? FontWeight.bold : FontWeight.normal)),
      ),
    );
  }

  Future<void> _fotografSec(int index) async {
    HapticFeedback.selectionClick();
    ImageSource? source = _secilenKaynak;

    // Sadece ilk fotoğrafta kaynak sorulur
    if (source == null) {
      source = await showDialog<ImageSource>(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: const Color(0xFF182434),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
          ),
          title: Text(
            t('photo_source'),
            style: const TextStyle(color: Colors.white),
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              ListTile(
                leading: const Icon(Icons.camera_alt, color: Colors.white),
                title: Text(
                  t('take_photo'),
                  style: const TextStyle(color: Colors.white),
                ),
                onTap: () => Navigator.pop(ctx, ImageSource.camera),
              ),
              const Divider(color: Colors.white10),
              ListTile(
                leading: const Icon(Icons.photo_library, color: Colors.white),
                title: Text(
                  t('choose_gallery'),
                  style: const TextStyle(color: Colors.white),
                ),
                onTap: () => Navigator.pop(ctx, ImageSource.gallery),
              ),
            ],
          ),
        ),
      );
      if (source == null) return;
      setState(() => _secilenKaynak = source);
    }

    XFile? photo;
    if (source == ImageSource.camera) {
      photo = await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (c) => SablonluKameraSayfasi(
            aci: _acilar[index],
            currentIndex: index,
            totalCount: _gerekliSayi,
            aracTipi: _aracTipi,
          ),
        ),
      );
    } else {
      photo = await _picker.pickImage(
        source: source,
        maxWidth: 1920,
        maxHeight: 1920,
        imageQuality: 85,
      );
    }

    if (photo == null) return;
    setState(() {
      if (index < _seciliResimler.length) {
        _seciliResimler[index] = photo!;
      } else {
        _seciliResimler.add(photo!);
      }
    });
  }

  Future<void> _devamEt() async {
    if (_seciliResimler.length < _gerekliSayi) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Lütfen $_gerekliSayi fotoğraf yükleyin! (${_seciliResimler.length}/$_gerekliSayi)',
          ),
          backgroundColor: Colors.orange,
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }
    if (_carNameCtrl.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Araç adını girin!'),
          backgroundColor: Colors.orange,
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (c) => ModifiyeSecimSayfasi(
          photos: _seciliResimler,
          carName: _carNameCtrl.text.trim(),
          method: widget.method,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final Color anaRenk = const Color(0xFF257bf4);
    final Color koyuArkaplan = const Color(0xFF0A1017);
    final Color koyuYuzey = const Color(0xFF182434);
    final bool is3d = widget.method == '3d';
    final int krediMaliyet = is3d ? 50 : 30;

    return Scaffold(
      backgroundColor: koyuArkaplan,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          t('upload_photo'),
          style: const TextStyle(
            color: Colors.white,
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
        centerTitle: true,
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: koyuYuzey,
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  is3d ? Icons.threed_rotation : Icons.image,
                  color: anaRenk,
                  size: 32,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                is3d ? t('turn_3d') : t('turn_2d'),
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  height: 1.2,
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _carNameCtrl,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  filled: true,
                  fillColor: koyuYuzey,
                  hintText: 'Araç Adı (ör: BMW M3 2024)',
                  hintStyle: const TextStyle(color: Colors.grey, fontSize: 14),
                  prefixIcon: const Icon(
                    Icons.directions_car,
                    color: Colors.grey,
                  ),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              const SizedBox(height: 12),
              // Araç tipi seçimi
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _buildAracTipiChip('🚗 Sedan', 'sedan', anaRenk, koyuYuzey),
                  const SizedBox(width: 8),
                  _buildAracTipiChip('🚙 Hatchback', 'hatchback', anaRenk, koyuYuzey),
                  const SizedBox(width: 8),
                  _buildAracTipiChip('🚘 SUV', 'suv', anaRenk, koyuYuzey),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    '${_seciliResimler.length}/$_gerekliSayi fotoğraf seçildi',
                    style: TextStyle(
                      color: _seciliResimler.length == _gerekliSayi
                          ? Colors.greenAccent
                          : Colors.grey,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      color: anaRenk.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      "$krediMaliyet ${t('credit_cost')}",
                      style: TextStyle(
                        color: anaRenk,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Expanded(
                child: GridView.builder(
                  gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    crossAxisSpacing: 16,
                    mainAxisSpacing: 16,
                    childAspectRatio: is3d ? 0.9 : 1.0,
                  ),
                  itemCount: _gerekliSayi,
                  itemBuilder: (context, index) {
                    final yuklendiMi = index < _seciliResimler.length;
                    return InkWell(
                      onTap: () => _fotografSec(index),
                      borderRadius: BorderRadius.circular(16),
                      child: Container(
                        decoration: BoxDecoration(
                          color: koyuYuzey,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: yuklendiMi
                                ? anaRenk
                                : Colors.white.withValues(alpha: 0.05),
                            width: 1.5,
                          ),
                        ),
                        child: Stack(
                          children: [
                            if (yuklendiMi)
                              ClipRRect(
                                borderRadius: BorderRadius.circular(14),
                                child: Image.file(
                                  File(_seciliResimler[index].path),
                                  width: double.infinity,
                                  height: double.infinity,
                                  fit: BoxFit.cover,
                                  errorBuilder: (c, e, s) => Container(
                                    color: anaRenk.withValues(alpha: 0.1),
                                    child: const Center(
                                      child: Icon(
                                        Icons.image,
                                        color: Colors.grey,
                                        size: 32,
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            if (yuklendiMi)
                              Positioned(
                                top: 8,
                                right: 8,
                                child: Container(
                                  padding: const EdgeInsets.all(4),
                                  decoration: BoxDecoration(
                                    color: anaRenk,
                                    shape: BoxShape.circle,
                                    boxShadow: [
                                      BoxShadow(
                                        color: anaRenk.withValues(alpha: 0.4),
                                        blurRadius: 6,
                                      ),
                                    ],
                                  ),
                                  child: const Icon(
                                    Icons.check,
                                    color: Colors.white,
                                    size: 14,
                                  ),
                                ),
                              ),
                            if (!yuklendiMi)
                              Center(
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Icon(
                                      Icons.add_a_photo,
                                      color: Colors.grey.withValues(alpha: 0.4),
                                      size: 36,
                                    ),
                                    const SizedBox(height: 4),
                                  ],
                                ),
                              ),
                            Positioned(
                              bottom: 8,
                              left: 0,
                              right: 0,
                              child: Container(
                                margin: const EdgeInsets.symmetric(
                                  horizontal: 8,
                                ),
                                padding: const EdgeInsets.symmetric(
                                  vertical: 4,
                                ),
                                decoration: BoxDecoration(
                                  color: Colors.black.withValues(alpha: 0.6),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Text(
                                  index < _acilar.length
                                      ? _acilar[index]
                                      : 'Açı ${index + 1}',
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 11,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(vertical: 20),
                child: ElevatedButton.icon(
                  onPressed: _devamEt,
                  icon: const Icon(Icons.arrow_forward, color: Colors.white),
                  label: Text(
                    t('continue_btn'),
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: anaRenk,
                    minimumSize: const Size(double.infinity, 56),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
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

// ── MODİFİYE SEÇİM SAYFASI ──
class ModifiyeSecimSayfasi extends StatefulWidget {
  final List<XFile>? photos;
  final String? carName;
  final String? method;
  final int? scanId; // Taslaktan devam ediyorsa
  const ModifiyeSecimSayfasi({
    super.key,
    this.photos,
    this.carName,
    this.method,
    this.scanId,
  });
  @override
  State<ModifiyeSecimSayfasi> createState() => _ModifiyeSecimSayfasiState();
}

class _ModifiyeSecimSayfasiState extends State<ModifiyeSecimSayfasi> {
  int _seciliRenkIndex = -1;
  int _seciliJantIndex = -1;
  bool _isYukleniyor = false;
  List<JantModel> _jantlar = [];
  List<RenkModel> _renkler = [];
  bool _pluginsYukleniyor = true;
  String? _seciliKategori; // null = Tümü

  @override
  void initState() {
    super.initState();
    _pluginlariYukle();
  }

  // Lokal fallback jant listesi (backend boşsa bunlar gösterilir)
  static final List<JantModel> _lokalJantlar = [
    JantModel(jantId: -1, modelName: 'BBS RS', category: 'sport', imageUrl: null, lokalAsset: 'assets/jantlar/bbs_rs.png'),
    JantModel(jantId: -2, modelName: 'Vossen VFS-1', category: 'sport', imageUrl: null, lokalAsset: 'assets/jantlar/vossen_vfs1.png'),
    JantModel(jantId: -3, modelName: 'Rotiform BLQ', category: 'sport', imageUrl: null, lokalAsset: 'assets/jantlar/rotiform_blq.png'),
    JantModel(jantId: -4, modelName: 'Work Meister', category: 'classic', imageUrl: null, lokalAsset: 'assets/jantlar/work_meister.png'),
    JantModel(jantId: -5, modelName: 'TE37 Saga', category: 'classic', imageUrl: null, lokalAsset: 'assets/jantlar/te37_saga.png'),
    JantModel(jantId: -6, modelName: 'Fuel Rebel', category: 'suv', imageUrl: null, lokalAsset: 'assets/jantlar/fuel_rebel.png'),
  ];

  Future<void> _pluginlariYukle() async {
    try {
      final jantlar = await ApiServisi().jantlariGetir();
      final renkler = await ApiServisi().renkleriGetir();
      if (mounted) {
        setState(() {
          _jantlar = jantlar.isNotEmpty ? jantlar : _lokalJantlar;
          _renkler = renkler;
          _pluginsYukleniyor = false;
        });
      }
    } catch (e) {
      // API erişilemezse lokal jantları göster
      if (mounted) {
        setState(() {
          _jantlar = _lokalJantlar;
          _pluginsYukleniyor = false;
        });
      }
    }
  }

  // Filtrelenmiş jant listesi
  List<JantModel> get _filtrelenmisJantlar {
    if (_seciliKategori == null) return _jantlar;
    return _jantlar.where((j) => j.category == _seciliKategori).toList();
  }

  String _kategoriEtiketi(String category) {
    switch (category) {
      case 'sport': return 'Spor';
      case 'classic': return 'Klasik';
      case 'suv': return 'SUV';
      default: return category;
    }
  }

  Widget _buildKategoriChip(String label, String? kategori, Color anaRenk) {
    final secili = _seciliKategori == kategori;
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick();
        setState(() => _seciliKategori = kategori);
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        margin: const EdgeInsets.only(right: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: secili ? anaRenk : const Color(0xFF182434),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: secili ? anaRenk : Colors.white.withValues(alpha: 0.1),
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: secili ? Colors.white : Colors.grey,
            fontSize: 12,
            fontWeight: secili ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ),
    );
  }

  Widget _buildPlaceholderPreview() {
    return Container(
      color: const Color(0xFF182434),
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.directions_car, size: 60, color: Colors.grey.withValues(alpha: 0.3)),
            const SizedBox(height: 8),
            Text(
              t('preview_area'),
              style: TextStyle(color: Colors.grey.withValues(alpha: 0.5), fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildJantPlaceholder() {
    return Container(
      color: Colors.transparent,
      child: Center(
        child: Icon(
          Icons.tire_repair,
          color: Colors.grey.withValues(alpha: 0.3),
          size: 32,
        ),
      ),
    );
  }

  // Fotoğrafları backend'e yükle → modifikasyon oluştur → RenderSayfası'na geç
  Future<void> _uretimiBaslat(BuildContext context) async {
    HapticFeedback.mediumImpact();
    setState(() => _isYukleniyor = true);

    try {
      if (widget.photos != null &&
          widget.carName != null &&
          widget.method != null) {
        debugPrint(
          '📤 Fotoğraf yükleniyor: ${widget.photos!.length} adet, araç: ${widget.carName}, method: ${widget.method}',
        );

        // 1) Backend'e fotoğrafları yükle
        final scan = await ApiServisi().fotografYukle(
          files: widget.photos!,
          carName: widget.carName!,
          method: widget.method!,
        );

        debugPrint('✅ Yükleme başarılı! Scan ID: ${scan.scanId}');

        // 2) Jant/renk seçildiyse modifikasyon oluştur
        int? jantId =
            _seciliJantIndex >= 0 && _seciliJantIndex < _jantlar.length
            ? _jantlar[_seciliJantIndex].jantId
            : null;
        int? colorId =
            _seciliRenkIndex >= 0 && _seciliRenkIndex < _renkler.length
            ? _renkler[_seciliRenkIndex].colorId
            : null;

        if (jantId != null || colorId != null) {
          await ApiServisi().modifikasyonOlustur(
            scanId: scan.scanId,
            jantId: jantId,
            colorId: colorId,
          );
          debugPrint('✅ Modifikasyon oluşturuldu');
        }

        // 3) Render sayfasına yönlendir
        if (mounted) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (c) => RenderSayfasi(
                carName: widget.carName!,
                method: widget.method!,
              ),
            ),
          );
        }
      } else {
        throw Exception('Fotoğraf veya araç bilgisi eksik!');
      }
    } catch (e) {
      debugPrint('❌ Yükleme hatası: $e');
      if (mounted) {
        setState(() => _isYukleniyor = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Yükleme başarısız: ${e.toString().replaceAll("Exception: ", "")}',
            ),
            backgroundColor: Colors.red,
            behavior: SnackBarBehavior.floating,
            duration: const Duration(seconds: 4),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final Color anaRenk = const Color(0xFF257bf4);
    final Color koyuArkaplan = const Color(0xFF0A1017);
    final Color koyuYuzey = const Color(0xFF182434);

    return Scaffold(
      backgroundColor: koyuArkaplan,
      extendBodyBehindAppBar: true,
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(70),
        child: GlassHeader(
          child: SafeArea(
            bottom: false,
            child: Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.arrow_back, color: Colors.white),
                  onPressed: () => Navigator.pop(context),
                ),
                Expanded(
                  child: Text(
                    t('mod_selection'),
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(width: 48),
              ],
            ),
          ),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: _pluginsYukleniyor
                  ? Center(child: CircularProgressIndicator(color: anaRenk))
                  : SingleChildScrollView(
                      padding: const EdgeInsets.only(
                        left: 24,
                        right: 24,
                        top: 10,
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // ── ÖNİZLEME ALANI (Anlık Güncelleme) ──
                          Container(
                            height: 240,
                            width: double.infinity,
                            decoration: BoxDecoration(
                              color: koyuYuzey,
                              borderRadius: BorderRadius.circular(24),
                              border: Border.all(
                                color: Colors.white.withValues(alpha: 0.08),
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.black.withValues(alpha: 0.3),
                                  blurRadius: 20,
                                  spreadRadius: 2,
                                ),
                              ],
                            ),
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(24),
                              child: Stack(
                                children: [
                                  // Araba fotoğrafı (ilk yüklenen foto)
                                  if (widget.photos != null && widget.photos!.isNotEmpty)
                                    Positioned.fill(
                                      child: Image.file(
                                        File(widget.photos!.first.path),
                                        fit: BoxFit.cover,
                                        errorBuilder: (c, e, s) => _buildPlaceholderPreview(),
                                      ),
                                    )
                                  else
                                    _buildPlaceholderPreview(),
                                  // Gradient overlay
                                  Positioned.fill(
                                    child: Container(
                                      decoration: BoxDecoration(
                                        gradient: LinearGradient(
                                          begin: Alignment.topCenter,
                                          end: Alignment.bottomCenter,
                                          colors: [
                                            Colors.transparent,
                                            Colors.black.withValues(alpha: 0.7),
                                          ],
                                          stops: const [0.4, 1.0],
                                        ),
                                      ),
                                    ),
                                  ),
                                  // Seçim badge'leri
                                  Positioned(
                                    bottom: 12,
                                    left: 12,
                                    right: 12,
                                    child: Row(
                                      children: [
                                        const Spacer(),
                                        // Jant badge
                                        if (_seciliJantIndex >= 0 && _seciliJantIndex < _jantlar.length)
                                          Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                            decoration: BoxDecoration(
                                              color: Colors.black.withValues(alpha: 0.6),
                                              borderRadius: BorderRadius.circular(20),
                                              border: Border.all(color: anaRenk.withValues(alpha: 0.5)),
                                            ),
                                            child: Row(
                                              mainAxisSize: MainAxisSize.min,
                                              children: [
                                                Icon(Icons.tire_repair, color: anaRenk, size: 14),
                                                const SizedBox(width: 6),
                                                Text(
                                                  _jantlar[_seciliJantIndex].modelName,
                                                  style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold),
                                                ),
                                              ],
                                            ),
                                          ),
                                      ],
                                    ),
                                  ),
                                  // Önizleme etiketi
                                  Positioned(
                                    top: 12,
                                    right: 12,
                                    child: Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                                      decoration: BoxDecoration(
                                        color: Colors.black.withValues(alpha: 0.5),
                                        borderRadius: BorderRadius.circular(12),
                                      ),
                                      child: Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          Icon(Icons.visibility, color: anaRenk, size: 14),
                                          const SizedBox(width: 4),
                                          Text(
                                            t('preview_area'),
                                            style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w500),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                          const SizedBox(height: 28),
                          // ── BOYA SEÇENEKLERİ (Geliştirme Aşamasında) ──
                          Row(
                            children: [
                              Icon(Icons.palette, color: anaRenk, size: 20),
                              const SizedBox(width: 8),
                              Text(
                                t('color_palette'),
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
                            decoration: BoxDecoration(
                              color: koyuYuzey,
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(color: Colors.amber.withValues(alpha: 0.15)),
                              gradient: LinearGradient(
                                begin: Alignment.topLeft,
                                end: Alignment.bottomRight,
                                colors: [
                                  Colors.amber.withValues(alpha: 0.05),
                                  koyuYuzey,
                                ],
                              ),
                            ),
                            child: Row(
                              children: [
                                Container(
                                  padding: const EdgeInsets.all(10),
                                  decoration: BoxDecoration(
                                    color: Colors.amber.withValues(alpha: 0.1),
                                    shape: BoxShape.circle,
                                  ),
                                  child: Icon(Icons.construction, color: Colors.amber.withValues(alpha: 0.8), size: 22),
                                ),
                                const SizedBox(width: 14),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      const Text(
                                        '🎨 Geliştirme Aşamasında',
                                        style: TextStyle(
                                          color: Colors.amber,
                                          fontSize: 14,
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        'Boya renk seçenekleri yakında eklenecektir.',
                                        style: TextStyle(
                                          color: Colors.white.withValues(alpha: 0.5),
                                          fontSize: 12,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 28),
                          // ── JANT SEÇENEKLERİ (Kategori Sekmeli) ──
                          Row(
                            children: [
                              Icon(Icons.tire_repair, color: anaRenk, size: 20),
                              const SizedBox(width: 8),
                              Text(
                                t('wheel_options'),
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              if (_seciliJantIndex >= 0 && _seciliJantIndex < _jantlar.length) ...[
                                const Spacer(),
                                GestureDetector(
                                  onTap: () {
                                    HapticFeedback.selectionClick();
                                    setState(() => _seciliJantIndex = -1);
                                  },
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: Colors.redAccent.withValues(alpha: 0.1),
                                      borderRadius: BorderRadius.circular(8),
                                    ),
                                    child: const Text(
                                      '✕ Temizle',
                                      style: TextStyle(color: Colors.redAccent, fontSize: 11),
                                    ),
                                  ),
                                ),
                              ],
                            ],
                          ),
                          const SizedBox(height: 12),
                          // Kategori filtreleri
                          if (_jantlar.isNotEmpty) ...[
                            SizedBox(
                              height: 36,
                              child: ListView(
                                scrollDirection: Axis.horizontal,
                                children: [
                                  _buildKategoriChip('Tümü', null, anaRenk),
                                  _buildKategoriChip('🏎️ Spor', 'sport', anaRenk),
                                  _buildKategoriChip('🏛️ Klasik', 'classic', anaRenk),
                                  _buildKategoriChip('🚙 SUV', 'suv', anaRenk),
                                ],
                              ),
                            ),
                            const SizedBox(height: 16),
                          ],
                          _jantlar.isEmpty
                              ? Container(
                                  padding: const EdgeInsets.all(20),
                                  decoration: BoxDecoration(
                                    color: koyuYuzey,
                                    borderRadius: BorderRadius.circular(16),
                                    border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
                                  ),
                                  child: Row(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      Icon(Icons.tire_repair, color: Colors.grey.withValues(alpha: 0.5), size: 20),
                                      const SizedBox(width: 8),
                                      const Text(
                                        'Henüz jant eklenmemiş',
                                        style: TextStyle(color: Colors.grey),
                                      ),
                                    ],
                                  ),
                                )
                              : GridView.builder(
                                  shrinkWrap: true,
                                  physics: const NeverScrollableScrollPhysics(),
                                  itemCount: _filtrelenmisJantlar.length,
                                  gridDelegate:
                                      const SliverGridDelegateWithFixedCrossAxisCount(
                                        crossAxisCount: 3,
                                        crossAxisSpacing: 12,
                                        mainAxisSpacing: 12,
                                        childAspectRatio: 0.85,
                                      ),
                                  itemBuilder: (context, index) {
                                    final jant = _filtrelenmisJantlar[index];
                                    final gercekIndex = _jantlar.indexOf(jant);
                                    final seciliMi = _seciliJantIndex == gercekIndex;
                                    final jantImgUrl =
                                        ApiServisi.buildImageUrl(jant.imageUrl);
                                    return GestureDetector(
                                      onTap: () {
                                        HapticFeedback.selectionClick();
                                        setState(
                                          () => _seciliJantIndex = gercekIndex,
                                        );
                                      },
                                      child: AnimatedContainer(
                                        duration: const Duration(milliseconds: 200),
                                        decoration: BoxDecoration(
                                          color: seciliMi
                                              ? anaRenk.withValues(alpha: 0.08)
                                              : koyuYuzey,
                                          borderRadius: BorderRadius.circular(16),
                                          border: Border.all(
                                            color: seciliMi
                                                ? anaRenk
                                                : Colors.white.withValues(alpha: 0.05),
                                            width: seciliMi ? 2.5 : 1,
                                          ),
                                          boxShadow: seciliMi
                                              ? [
                                                  BoxShadow(
                                                    color: anaRenk.withValues(alpha: 0.25),
                                                    blurRadius: 15,
                                                    spreadRadius: 1,
                                                  ),
                                                ]
                                              : [],
                                        ),
                                        child: ClipRRect(
                                          borderRadius: BorderRadius.circular(14),
                                          child: Stack(
                                            children: [
                                              // Jant görseli (lokal veya network)
                                              if (jant.isLokal)
                                                Positioned.fill(
                                                  child: Padding(
                                                    padding: const EdgeInsets.all(8),
                                                    child: Image.asset(
                                                      jant.lokalAsset!,
                                                      fit: BoxFit.contain,
                                                      errorBuilder: (c, e, s) =>
                                                          _buildJantPlaceholder(),
                                                    ),
                                                  ),
                                                )
                                              else if (jantImgUrl != null)
                                                Positioned.fill(
                                                  child: Padding(
                                                    padding: const EdgeInsets.all(8),
                                                    child: Image.network(
                                                      jantImgUrl,
                                                      fit: BoxFit.contain,
                                                      errorBuilder: (c, e, s) =>
                                                          _buildJantPlaceholder(),
                                                    ),
                                                  ),
                                                )
                                              else
                                                Positioned.fill(
                                                  child: _buildJantPlaceholder(),
                                                ),
                                              // Seçili badge
                                              if (seciliMi)
                                                Positioned(
                                                  top: 6,
                                                  right: 6,
                                                  child: Container(
                                                    padding: const EdgeInsets.all(4),
                                                    decoration: BoxDecoration(
                                                      color: anaRenk,
                                                      shape: BoxShape.circle,
                                                      boxShadow: [
                                                        BoxShadow(
                                                          color: anaRenk.withValues(alpha: 0.4),
                                                          blurRadius: 6,
                                                        ),
                                                      ],
                                                    ),
                                                    child: const Icon(
                                                      Icons.check,
                                                      color: Colors.white,
                                                      size: 12,
                                                    ),
                                                  ),
                                                ),
                                              // İsim ve kategori etiketi
                                              Positioned(
                                                bottom: 0,
                                                left: 0,
                                                right: 0,
                                                child: Container(
                                                  padding: const EdgeInsets.symmetric(
                                                    horizontal: 6,
                                                    vertical: 6,
                                                  ),
                                                  decoration: BoxDecoration(
                                                    gradient: LinearGradient(
                                                      begin: Alignment.topCenter,
                                                      end: Alignment.bottomCenter,
                                                      colors: [
                                                        Colors.transparent,
                                                        Colors.black.withValues(alpha: 0.8),
                                                      ],
                                                    ),
                                                    borderRadius: const BorderRadius.vertical(
                                                      bottom: Radius.circular(14),
                                                    ),
                                                  ),
                                                  child: Column(
                                                    children: [
                                                      Text(
                                                        jant.modelName,
                                                        style: const TextStyle(
                                                          color: Colors.white,
                                                          fontSize: 10,
                                                          fontWeight: FontWeight.bold,
                                                        ),
                                                        maxLines: 1,
                                                        overflow: TextOverflow.ellipsis,
                                                        textAlign: TextAlign.center,
                                                      ),
                                                      const SizedBox(height: 2),
                                                      Text(
                                                        _kategoriEtiketi(jant.category),
                                                        style: TextStyle(
                                                          color: Colors.white.withValues(alpha: 0.5),
                                                          fontSize: 8,
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
                                  },
                                ),
                          const SizedBox(height: 30),
                        ],
                      ),
                    ),
            ),
            // Alt buton
            Container(
              padding: const EdgeInsets.all(24.0),
              decoration: BoxDecoration(
                color: koyuYuzey,
                borderRadius: const BorderRadius.vertical(
                  top: Radius.circular(28),
                ),
                border: const Border(
                  top: BorderSide(color: Colors.white10, width: 0.5),
                ),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  InkWell(
                    onTap: _isYukleniyor ? null : () => _uretimiBaslat(context),
                    borderRadius: BorderRadius.circular(16),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        vertical: 18,
                        horizontal: 24,
                      ),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          colors: [Color(0xFF257bf4), Color(0xFF8A2387)],
                        ),
                        borderRadius: BorderRadius.circular(16),
                        boxShadow: [
                          BoxShadow(
                            color: const Color(
                              0xFF257bf4,
                            ).withValues(alpha: 0.5),
                            blurRadius: 15,
                            spreadRadius: 2,
                          ),
                        ],
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: _isYukleniyor
                            ? [
                                const SizedBox(
                                  width: 24,
                                  height: 24,
                                  child: CircularProgressIndicator(
                                    color: Colors.white,
                                    strokeWidth: 3,
                                  ),
                                ),
                              ]
                            : [
                                const Icon(
                                  Icons.auto_fix_high,
                                  color: Colors.white,
                                  size: 24,
                                ),
                                const SizedBox(width: 12),
                                Text(
                                  t('start_prod'),
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 18,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: () {
                      HapticFeedback.lightImpact();
                      Navigator.pushAndRemoveUntil(
                        context,
                        MaterialPageRoute(
                          builder: (c) => const AnaSayfa(initialIndex: 2),
                        ),
                        (r) => false,
                      );
                    },
                    child: Text(
                      t('not_enough_credit'),
                      style: const TextStyle(
                        color: Colors.grey,
                        fontSize: 12,
                        decoration: TextDecoration.underline,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// Izgara çizicisi
class GridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    var paint = Paint()
      ..color = Colors.white
      ..strokeWidth = 0.5;
    double step = 20.0;
    for (double i = 0; i < size.width; i += step)
      canvas.drawLine(Offset(i, 0), Offset(i, size.height), paint);
    for (double i = 0; i < size.height; i += step)
      canvas.drawLine(Offset(0, i), Offset(size.width, i), paint);
  }

  @override
  bool shouldRepaint(CustomPainter oldDelegate) => false;
}
