import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'sistem_ve_dil.dart';
import 'ortak_widgetlar.dart';
import 'sayfalar_islem.dart';
import 'modeller/kullanici_model.dart';
import 'modeller/scan_model.dart';
import 'modeller/draft_model.dart';
import 'servisler/api_servisi.dart';

class SekmeAnaSayfa extends StatefulWidget {
  final Kullanici? kullanici;
  final int kredi;
  const SekmeAnaSayfa({super.key, this.kullanici, this.kredi = 0});
  @override
  State<SekmeAnaSayfa> createState() => _SekmeAnaSayfaState();
}

class _SekmeAnaSayfaState extends State<SekmeAnaSayfa> {
  final Color anaRenk = const Color(0xFF257bf4);
  late Future<List<Scan>> _garajFuture;
  late Future<List<Taslak>> _taslakFuture;
  int _garajSayisi = 0;

  @override
  void initState() {
    super.initState();
    _garajFuture = ApiServisi().garajiGetir().then((list) {
      if (mounted) setState(() => _garajSayisi = list.length);
      return list;
    });
    _taslakFuture = ApiServisi().taslaklariGetir();
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.only(top: 110),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _yeniProjeKartiOlustur(context),
          _istatistikleriOlustur(),
          _garajKismiOlustur(context),
          _taslaklarKismiOlustur(),
          const SizedBox(height: 100),
        ],
      ),
    );
  }

  Widget _yeniProjeKartiOlustur(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 8.0),
      child: Container(
        height: 280,
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(20), gradient: LinearGradient(colors: [anaRenk.withOpacity(0.9), Colors.blue.shade900], begin: Alignment.topLeft, end: Alignment.bottomRight), boxShadow: [BoxShadow(color: anaRenk.withOpacity(0.3), blurRadius: 20, spreadRadius: 2)]),
        child: Stack(children: [
          Opacity(opacity: 0.3, child: ClipRRect(borderRadius: BorderRadius.circular(20), child: Image.network('https://images.unsplash.com/photo-1617788138017-80ad40651399?q=80&w=1000&auto=format&fit=crop', width: double.infinity, height: double.infinity, fit: BoxFit.cover))),
          Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(mainAxisAlignment: MainAxisAlignment.end, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), decoration: BoxDecoration(color: Colors.white.withOpacity(0.2), borderRadius: BorderRadius.circular(12)), child: const Row(mainAxisSize: MainAxisSize.min, children: [Icon(Icons.auto_awesome, color: Colors.white, size: 14), SizedBox(width: 4), Text('AI Studio', style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold))])),
              const SizedBox(height: 8),
              Text(t('design_dream'), style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold, height: 1.1)),
              const SizedBox(height: 8),
              Text(t('ai_step'), style: const TextStyle(color: Colors.blueAccent, fontSize: 12)),
              const SizedBox(height: 16),
              ElevatedButton.icon(onPressed: () { HapticFeedback.lightImpact(); Navigator.push(context, MaterialPageRoute(builder: (context) => const ProjeTipiSecimSayfasi())); }, icon: Icon(Icons.add_circle, color: anaRenk), label: Text(t('new_project'), style: TextStyle(color: anaRenk, fontWeight: FontWeight.bold)), style: ElevatedButton.styleFrom(backgroundColor: Colors.white, minimumSize: const Size(double.infinity, 48), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)))),
            ]),
          ),
        ]),
      ),
    );
  }

  Widget _istatistikleriOlustur() {
    final u = widget.kullanici;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16.0),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 24.0),
        child: Row(children: [
          _istatistikKartiOlustur(Icons.garage, t('total'), '$_garajSayisi', t('cars_in_garage'), anaRenk),
          const SizedBox(width: 12),
          _istatistikKartiOlustur(Icons.view_in_ar, 'Render', '${u?.renderImage ?? 0}', t('created'), Colors.purpleAccent),
          const SizedBox(width: 12),
          _istatistikKartiOlustur(Icons.savings, t('credit'), '${widget.kredi}', t('available'), Colors.greenAccent),
        ]),
      ),
    );
  }

  Widget _istatistikKartiOlustur(IconData ikon, String baslik, String deger, String altBaslik, Color renk) {
    return Container(width: 130, padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(16), border: Border.all(color: kartBorderRengi())), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Row(children: [Icon(ikon, color: renk, size: 18), const SizedBox(width: 4), Text(baslik, style: TextStyle(color: renk, fontSize: 12, fontWeight: FontWeight.bold))]), const SizedBox(height: 8), Text(deger, style: premiumNumberStyle.copyWith(color: yaziRengi(), fontSize: 24)), Text(altBaslik, style: TextStyle(color: ikinciYaziRengi(), fontSize: 10))]));
  }

  // Madde 7: Garaj kartlarına işlevsel butonlar
  Widget _garajKismiOlustur(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24.0),
      child: Column(children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Row(children: [Container(width: 4, height: 20, color: anaRenk), const SizedBox(width: 8), Text(t('my_garage'), style: TextStyle(color: yaziRengi(), fontSize: 20, fontWeight: FontWeight.bold))]),
          TextButton(onPressed: () { HapticFeedback.lightImpact(); Navigator.push(context, MaterialPageRoute(builder: (context) => const TumGarajSayfasi())); }, child: Row(children: [Text(t('see_all'), style: TextStyle(color: anaRenk, fontSize: 12)), Icon(Icons.arrow_forward_ios, color: anaRenk, size: 12)])),
        ]),
        const SizedBox(height: 8),
        FutureBuilder<List<Scan>>(
          future: _garajFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) return const Center(child: Padding(padding: EdgeInsets.all(20), child: CircularProgressIndicator()));
            if (snapshot.hasError || !snapshot.hasData || snapshot.data!.isEmpty) return Container(width: double.infinity, padding: const EdgeInsets.all(20), decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(16)), child: Text(snapshot.hasError ? "Bağlantı hatası" : "Garajın şu an boş.", style: const TextStyle(color: Colors.grey), textAlign: TextAlign.center));
            final scan = snapshot.data!.first;
            final thumbUrl = ApiServisi.buildImageUrl(scan.thumbnailUrl) ?? 'https://images.unsplash.com/photo-1603386329225-868f9b1ee6c9?q=80&w=1000';
            return ArabaKartiOlusturucu.olustur(
              scan.carName,
              scan.method == '3d' ? '3D Model' : '2D Modifiye',
              thumbUrl,
              _zamanHesapla(scan.createdAt),
              anaRenk,
              yuzeyRengi(),
              scanId: scan.scanId,
              onDuzenle: () {
                HapticFeedback.lightImpact();
                Navigator.push(context, MaterialPageRoute(builder: (c) => ModifiyeSecimSayfasi(scanId: scan.scanId, carName: scan.carName, method: scan.method)));
              },
              onPaylas: () async {
                HapticFeedback.mediumImpact();
                try {
                  await ApiServisi().toplulugaPaylas(scan.scanId);
                  if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('car_shared')), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating));
                } catch (e) {
                  if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceAll('Exception: ', '')), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
                }
              },
              onSil: () async {
                final onay = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(
                  backgroundColor: yuzeyRengi(),
                  title: Text(t('delete_btn'), style: TextStyle(color: yaziRengi())),
                  content: Text(t('delete_car_confirm'), style: TextStyle(color: ikinciYaziRengi())),
                  actions: [
                    TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(t('cancel'), style: const TextStyle(color: Colors.grey))),
                    ElevatedButton(onPressed: () => Navigator.pop(ctx, true), style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent), child: Text(t('delete_btn'), style: const TextStyle(color: Colors.white))),
                  ],
                ));
                if (onay == true) {
                  try {
                    await ApiServisi().scanSil(scan.scanId);
                    if (mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('car_deleted')), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating));
                      setState(() { _garajFuture = ApiServisi().garajiGetir(); });
                    }
                  } catch (_) {}
                }
              },
              onDetay: () {
                HapticFeedback.lightImpact();
                // Detay sayfası — scan bilgileri gösterilir
                showModalBottomSheet(context: context, backgroundColor: yuzeyRengi(), shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))), builder: (ctx) {
                  return SafeArea(child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(scan.carName, style: TextStyle(color: yaziRengi(), fontSize: 22, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 12),
                      _detaySatiri('Metod', scan.method == '3d' ? '3D Model' : '2D Modifiye'),
                      _detaySatiri('Durum', scan.status == 'completed' ? 'Tamamlandı ✅' : scan.status),
                      _detaySatiri('Oluşturulma', _zamanHesapla(scan.createdAt)),
                      _detaySatiri('Scan ID', '#${scan.scanId}'),
                      const SizedBox(height: 16),
                    ]),
                  ));
                });
              },
            );
          },
        ),
      ]),
    );
  }

  Widget _detaySatiri(String etiket, String deger) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(etiket, style: TextStyle(color: ikinciYaziRengi(), fontSize: 14)),
        Text(deger, style: TextStyle(color: yaziRengi(), fontSize: 14, fontWeight: FontWeight.w600)),
      ]),
    );
  }

  String _zamanHesapla(DateTime dt) {
    final fark = DateTime.now().difference(dt);
    if (fark.inMinutes < 60) return '${fark.inMinutes} dk önce';
    if (fark.inHours < 24) return '${fark.inHours} saat önce';
    if (fark.inDays < 7) return '${fark.inDays} gün önce';
    return '${dt.day}.${dt.month}.${dt.year}';
  }

  Widget _taslaklarKismiOlustur() {
    return FutureBuilder<List<Taslak>>(
      future: _taslakFuture,
      builder: (context, snapshot) {
        if (!snapshot.hasData || snapshot.data!.isEmpty) return const SizedBox.shrink();
        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 16.0),
          child: Column(children: [
            Row(children: [Container(width: 4, height: 20, color: Colors.orange), const SizedBox(width: 8), Text(t('drafts'), style: TextStyle(color: yaziRengi(), fontSize: 20, fontWeight: FontWeight.bold))]),
            const SizedBox(height: 12),
            ...snapshot.data!.map((taslak) => _taslakKarti(taslak)).toList(),
          ]),
        );
      },
    );
  }

  Widget _taslakKarti(Taslak taslak) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(16), border: Border.all(color: Colors.orange.withOpacity(0.5))),
      child: Column(children: [
        Row(children: [
          Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: Colors.orange.withOpacity(0.1), shape: BoxShape.circle), child: const Icon(Icons.design_services, color: Colors.orange)),
          const SizedBox(width: 16),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(taslak.carName, style: TextStyle(color: yaziRengi(), fontWeight: FontWeight.bold, fontSize: 14)), const SizedBox(height: 4), Text(taslak.stepLabel, style: TextStyle(color: ikinciYaziRengi(), fontSize: 12))])),
        ]),
        const SizedBox(height: 16),
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          TextButton.icon(onPressed: () async { try { await ApiServisi().scanSil(taslak.scanId); setState(() { _taslakFuture = ApiServisi().taslaklariGetir(); }); } catch (_) {} }, icon: const Icon(Icons.delete_outline, color: Colors.redAccent, size: 18), label: Text(t('delete_draft'), style: const TextStyle(color: Colors.redAccent, fontWeight: FontWeight.bold))),
          ElevatedButton(onPressed: () { Navigator.push(context, MaterialPageRoute(builder: (context) => ModifiyeSecimSayfasi(scanId: taslak.scanId, carName: taslak.carName, method: taslak.method))); }, style: ElevatedButton.styleFrom(backgroundColor: Colors.orange, padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))), child: Text(t('continue_btn'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 12))),
        ]),
      ]),
    );
  }
}

// ── TÜM GARAJ SAYFASI ──
class TumGarajSayfasi extends StatefulWidget {
  const TumGarajSayfasi({super.key});
  @override
  State<TumGarajSayfasi> createState() => _TumGarajSayfasiState();
}

class _TumGarajSayfasiState extends State<TumGarajSayfasi> {
  late Future<List<Scan>> _garajFuture;

  @override
  void initState() {
    super.initState();
    _garajFuture = ApiServisi().garajiGetir();
  }

  @override
  Widget build(BuildContext context) {
    final Color anaRenk = const Color(0xFF257bf4);
    return Scaffold(
      backgroundColor: arkaplanRengi(),
      body: Stack(children: [
        Positioned.fill(child: Image.network('https://images.unsplash.com/photo-1553440569-bcc63803a83d?q=80&w=1000&auto=format&fit=crop', fit: BoxFit.cover, errorBuilder: (c, e, s) => Container(color: arkaplanRengi()))),
        Positioned.fill(child: Container(decoration: BoxDecoration(gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [arkaplanRengi().withOpacity(0.6), arkaplanRengi().withOpacity(0.95), arkaplanRengi()])))),
        SafeArea(child: Column(children: [
          AppBar(backgroundColor: Colors.transparent, elevation: 0, leading: IconButton(icon: Icon(Icons.arrow_back, color: yaziRengi()), onPressed: () => Navigator.pop(context)), title: Text(t('all_my_cars'), style: TextStyle(color: yaziRengi(), fontSize: 18, fontWeight: FontWeight.bold)), centerTitle: true),
          Expanded(
            child: FutureBuilder<List<Scan>>(
              future: _garajFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) return Center(child: CircularProgressIndicator(color: anaRenk));
                if (snapshot.hasError) return Center(child: Text("Hata: ${snapshot.error}", style: const TextStyle(color: Colors.redAccent)));
                if (!snapshot.hasData || snapshot.data!.isEmpty) return Center(child: Text("Garajın şu an tamamen boş.", style: TextStyle(color: yaziRengi(), fontSize: 18)));
                return ListView.builder(
                  padding: const EdgeInsets.all(24.0),
                  itemCount: snapshot.data!.length,
                  itemBuilder: (context, index) {
                    final scan = snapshot.data![index];
                    final thumbUrl = ApiServisi.buildImageUrl(scan.thumbnailUrl) ?? 'https://images.unsplash.com/photo-1603386329225-868f9b1ee6c9?q=80&w=1000';
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 20),
                      child: ArabaKartiOlusturucu.olustur(
                        scan.carName,
                        scan.method == '3d' ? '3D Model' : '2D Modifiye',
                        thumbUrl,
                        'Tamamlandı',
                        anaRenk,
                        yuzeyRengi(),
                        scanId: scan.scanId,
                        onDuzenle: () { Navigator.push(context, MaterialPageRoute(builder: (c) => ModifiyeSecimSayfasi(scanId: scan.scanId, carName: scan.carName, method: scan.method))); },
                        onPaylas: () async {
                          try {
                            await ApiServisi().toplulugaPaylas(scan.scanId);
                            if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('car_shared')), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating));
                          } catch (e) {
                            if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceAll('Exception: ', '')), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
                          }
                        },
                        onSil: () async {
                          try {
                            await ApiServisi().scanSil(scan.scanId);
                            if (mounted) { setState(() { _garajFuture = ApiServisi().garajiGetir(); }); ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('car_deleted')), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating)); }
                          } catch (_) {}
                        },
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ])),
      ]),
    );
  }
}
