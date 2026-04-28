import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'sistem_ve_dil.dart';
import 'modeller/community_model.dart';
import 'modeller/scan_model.dart';
import 'servisler/api_servisi.dart';

class SekmeKesfet extends StatefulWidget {
  const SekmeKesfet({super.key});
  @override
  State<SekmeKesfet> createState() => _SekmeKesfetState();
}

class _SekmeKesfetState extends State<SekmeKesfet> {
  late Future<List<FeedItem>> _feedFuture;

  @override
  void initState() {
    super.initState();
    _feedFuture = ApiServisi().feedGetir();
  }

  void _alevTikla(FeedItem item) async {
    // Madde 8: Tek alev kısıtı — zaten beğendiyse geri almaz
    if (item.isLiked) {
      HapticFeedback.heavyImpact();
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Bu aracı zaten beğendiniz! 🔥'), backgroundColor: Colors.deepOrange, behavior: SnackBarBehavior.floating, duration: Duration(seconds: 1)));
      return;
    }
    HapticFeedback.selectionClick();
    setState(() { item.isLiked = true; item.likeCount++; });
    try {
      await ApiServisi().begeniToggle(item.scanId);
    } catch (e) {
      setState(() { item.isLiked = false; item.likeCount--; });
    }
  }

  void _yorumSayfasiAc(FeedItem item) {
    HapticFeedback.lightImpact();
    Navigator.push(context, MaterialPageRoute(builder: (c) => GonderiDetaySayfasi(feedItem: item)));
  }

  void _toplulugaPaylas() async {
    HapticFeedback.lightImpact();
    try {
      final garaj = await ApiServisi().garajiGetir();
      final tamamlananlar = garaj.where((s) => s.isCompleted).toList();
      if (tamamlananlar.isEmpty) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Paylaşılacak tamamlanmış araç yok.'), backgroundColor: Colors.orange, behavior: SnackBarBehavior.floating));
        return;
      }
      if (!mounted) return;
      _aracSecDialoguGoster(tamamlananlar);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceAll('Exception: ', '')), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
    }
  }

  void _aracSecDialoguGoster(List<Scan> araclar) {
    showModalBottomSheet(context: context, backgroundColor: yuzeyRengi(), shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))), builder: (ctx) {
      return SafeArea(child: Column(mainAxisSize: MainAxisSize.min, children: [
        Padding(padding: const EdgeInsets.all(16), child: Text(t('select_car_share'), style: TextStyle(color: yaziRengi(), fontSize: 18, fontWeight: FontWeight.bold))),
        ...araclar.map((scan) => ListTile(
          leading: Container(width: 48, height: 48, decoration: BoxDecoration(borderRadius: BorderRadius.circular(8), color: yuzeyRengi()), child: scan.thumbnailUrl != null ? ClipRRect(borderRadius: BorderRadius.circular(8), child: Image.network(ApiServisi.buildImageUrl(scan.thumbnailUrl)!, fit: BoxFit.cover)) : const Icon(Icons.directions_car, color: Colors.grey)),
          title: Text(scan.carName, style: TextStyle(color: yaziRengi(), fontWeight: FontWeight.bold)),
          subtitle: Text(scan.method == '3d' ? '3D' : '2D', style: TextStyle(color: ikinciYaziRengi())),
          onTap: () async {
            Navigator.pop(ctx);
            try {
              await ApiServisi().toplulugaPaylas(scan.scanId);
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('shared_success')), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating));
                setState(() { _feedFuture = ApiServisi().feedGetir(); });
              }
            } catch (e) {
              if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceAll('Exception: ', '')), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
            }
          },
        )),
        const SizedBox(height: 20),
      ]));
    });
  }

  @override
  Widget build(BuildContext context) {
    final Color anaRenk = const Color(0xFF257bf4);
    return SafeArea(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.only(left: 24, right: 24, top: 16, bottom: 8),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(t('discover_title'), style: TextStyle(color: yaziRengi(), fontSize: 28, fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              Text(t('discover_desc'), style: TextStyle(color: ikinciYaziRengi(), fontSize: 14)),
            ]),
          ),
          // Toplulukla paylaş butonu
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
            child: InkWell(
              onTap: _toplulugaPaylas,
              borderRadius: BorderRadius.circular(12),
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
                decoration: BoxDecoration(gradient: LinearGradient(colors: [anaRenk, Colors.blue.shade900]), borderRadius: BorderRadius.circular(12)),
                child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [const Icon(Icons.rocket_launch, color: Colors.white, size: 20), const SizedBox(width: 8), Text(t('share_your_legend'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14))]),
              ),
            ),
          ),
          // Feed
          Expanded(
            child: FutureBuilder<List<FeedItem>>(
              future: _feedFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) return Center(child: CircularProgressIndicator(color: anaRenk));
                if (snapshot.hasError) return Center(child: Text("Bağlantı hatası", style: TextStyle(color: yaziRengi())));
                final items = snapshot.data ?? [];
                if (items.isEmpty) return Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [const Icon(Icons.explore_off, color: Colors.grey, size: 48), const SizedBox(height: 12), Text('Henüz paylaşım yok', style: TextStyle(color: ikinciYaziRengi(), fontSize: 16))]));
                return GridView.builder(
                  padding: const EdgeInsets.all(16),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 2, crossAxisSpacing: 12, mainAxisSpacing: 12, childAspectRatio: 0.68),
                  itemCount: items.length,
                  itemBuilder: (context, index) {
                    final item = items[index];
                    final thumbUrl = ApiServisi.buildImageUrl(item.thumbnailUrl) ?? 'https://images.unsplash.com/photo-1603386329225-868f9b1ee6c9?q=80&w=500';
                    return GestureDetector(
                      onTap: () => _yorumSayfasiAc(item),
                      child: _kesfetKartiOlustur(item, thumbUrl),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _kesfetKartiOlustur(FeedItem item, String thumbUrl) {
    return Container(
      decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(16), border: Border.all(color: kartBorderRengi())),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: ClipRRect(borderRadius: const BorderRadius.vertical(top: Radius.circular(16)), child: Image.network(thumbUrl, width: double.infinity, fit: BoxFit.cover, errorBuilder: (c, e, s) => Container(color: Colors.black26, child: const Icon(Icons.image_not_supported, color: Colors.grey))))),
          Padding(
            padding: const EdgeInsets.all(10.0),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(item.carName, style: TextStyle(color: yaziRengi(), fontSize: 13, fontWeight: FontWeight.bold), maxLines: 1, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 2),
              Text('${t('by')}${item.ownerName}', style: TextStyle(color: ikinciYaziRengi(), fontSize: 10)),
              const SizedBox(height: 8),
              Row(children: [
                // Alev butonu
                InkWell(
                  onTap: () => _alevTikla(item),
                  borderRadius: BorderRadius.circular(12),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(color: item.isLiked ? Colors.deepOrange.withOpacity(0.2) : Colors.deepOrange.withOpacity(0.05), borderRadius: BorderRadius.circular(12), border: Border.all(color: item.isLiked ? Colors.deepOrangeAccent : Colors.deepOrange.withOpacity(0.5))),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [Text(item.isLiked ? '🔥' : '🔥', style: const TextStyle(fontSize: 12)), const SizedBox(width: 4), Text('${item.likeCount}', style: TextStyle(color: item.isLiked ? Colors.white : Colors.deepOrange, fontWeight: FontWeight.bold, fontSize: 11))]),
                  ),
                ),
                const SizedBox(width: 8),
                // Yorum sayısı
                Row(mainAxisSize: MainAxisSize.min, children: [Icon(Icons.comment_outlined, color: ikinciYaziRengi(), size: 14), const SizedBox(width: 4), Text('${item.commentCount}', style: TextStyle(color: ikinciYaziRengi(), fontSize: 11))]),
              ]),
            ]),
          ),
        ],
      ),
    );
  }
}

// ── GÖNDERİ DETAY SAYFASI (Madde 8 — Yorum sistemi) ──
class GonderiDetaySayfasi extends StatefulWidget {
  final FeedItem feedItem;
  const GonderiDetaySayfasi({super.key, required this.feedItem});
  @override
  State<GonderiDetaySayfasi> createState() => _GonderiDetaySayfasiState();
}

class _GonderiDetaySayfasiState extends State<GonderiDetaySayfasi> {
  late Future<List<Yorum>> _yorumFuture;
  final TextEditingController _yorumController = TextEditingController();
  bool _gonderiliyor = false;

  @override
  void initState() {
    super.initState();
    _yorumFuture = ApiServisi().yorumlariGetir(widget.feedItem.scanId);
  }

  Future<void> _yorumGonder() async {
    final icerik = _yorumController.text.trim();
    if (icerik.isEmpty) return;
    setState(() => _gonderiliyor = true);
    try {
      await ApiServisi().yorumEkle(widget.feedItem.scanId, icerik);
      _yorumController.clear();
      setState(() { _yorumFuture = ApiServisi().yorumlariGetir(widget.feedItem.scanId); });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceAll('Exception: ', '')), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
    } finally {
      if (mounted) setState(() => _gonderiliyor = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final Color anaRenk = const Color(0xFF257bf4);
    final thumbUrl = ApiServisi.buildImageUrl(widget.feedItem.thumbnailUrl) ?? 'https://images.unsplash.com/photo-1603386329225-868f9b1ee6c9?q=80&w=1000';

    return Scaffold(
      backgroundColor: arkaplanRengi(),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(icon: Icon(Icons.arrow_back, color: yaziRengi()), onPressed: () => Navigator.pop(context)),
        title: Text(widget.feedItem.carName, style: TextStyle(color: yaziRengi(), fontWeight: FontWeight.bold)),
        centerTitle: true,
      ),
      body: Column(
        children: [
          // Araç görseli + bilgiler
          ClipRRect(
            borderRadius: const BorderRadius.only(bottomLeft: Radius.circular(24), bottomRight: Radius.circular(24)),
            child: Image.network(thumbUrl, height: 250, width: double.infinity, fit: BoxFit.cover, errorBuilder: (c, e, s) => Container(height: 250, color: Colors.black26)),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(widget.feedItem.carName, style: TextStyle(color: yaziRengi(), fontSize: 20, fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                Text('${t('by')}${widget.feedItem.ownerName}', style: TextStyle(color: ikinciYaziRengi(), fontSize: 13)),
              ]),
              Row(children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(color: widget.feedItem.isLiked ? Colors.deepOrange.withOpacity(0.2) : Colors.deepOrange.withOpacity(0.05), borderRadius: BorderRadius.circular(16), border: Border.all(color: Colors.deepOrange.withOpacity(0.5))),
                  child: Row(children: [const Text('🔥', style: TextStyle(fontSize: 16)), const SizedBox(width: 4), Text('${widget.feedItem.likeCount}', style: TextStyle(color: yaziRengi(), fontWeight: FontWeight.bold))]),
                ),
              ]),
            ]),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Row(children: [Icon(Icons.comment, color: anaRenk, size: 18), const SizedBox(width: 8), Text(t('comments'), style: TextStyle(color: yaziRengi(), fontSize: 16, fontWeight: FontWeight.bold))]),
          ),
          const SizedBox(height: 8),
          // Yorum listesi
          Expanded(
            child: FutureBuilder<List<Yorum>>(
              future: _yorumFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) return Center(child: CircularProgressIndicator(color: anaRenk));
                final yorumlar = snapshot.data ?? [];
                if (yorumlar.isEmpty) return Center(child: Text(t('no_comments'), style: TextStyle(color: ikinciYaziRengi())));
                return ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  itemCount: yorumlar.length,
                  itemBuilder: (context, index) {
                    final yorum = yorumlar[index];
                    return Container(
                      margin: const EdgeInsets.only(bottom: 8),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(12), border: Border.all(color: kartBorderRengi())),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                          Text('Kullanıcı #${yorum.userId}', style: TextStyle(color: anaRenk, fontWeight: FontWeight.bold, fontSize: 12)),
                          Text(_zamanHesapla(yorum.createdAt), style: TextStyle(color: ikinciYaziRengi(), fontSize: 10)),
                        ]),
                        const SizedBox(height: 6),
                        Text(yorum.content, style: TextStyle(color: yaziRengi(), fontSize: 13, height: 1.4)),
                      ]),
                    );
                  },
                );
              },
            ),
          ),
          // Yorum yazma alanı
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(color: yuzeyRengi(), border: Border(top: BorderSide(color: kartBorderRengi()))),
            child: SafeArea(
              child: Row(children: [
                Expanded(
                  child: TextField(
                    controller: _yorumController,
                    style: TextStyle(color: yaziRengi(), fontSize: 14),
                    decoration: InputDecoration(
                      hintText: t('write_comment'),
                      hintStyle: TextStyle(color: ikinciYaziRengi()),
                      filled: true,
                      fillColor: arkaplanRengi(),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: BorderSide.none),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                InkWell(
                  onTap: _gonderiliyor ? null : _yorumGonder,
                  borderRadius: BorderRadius.circular(24),
                  child: Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(color: anaRenk, shape: BoxShape.circle),
                    child: _gonderiliyor ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2)) : const Icon(Icons.send, color: Colors.white, size: 20),
                  ),
                ),
              ]),
            ),
          ),
        ],
      ),
    );
  }

  String _zamanHesapla(DateTime dt) {
    final fark = DateTime.now().difference(dt);
    if (fark.inMinutes < 60) return '${fark.inMinutes} dk';
    if (fark.inHours < 24) return '${fark.inHours} saat';
    if (fark.inDays < 7) return '${fark.inDays} gün';
    return '${dt.day}.${dt.month}.${dt.year}';
  }
}