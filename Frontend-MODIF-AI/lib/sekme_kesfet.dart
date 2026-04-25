import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'sistem_ve_dil.dart';
import 'ortak_widgetlar.dart';
import 'modeller/community_model.dart';
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

  @override
  Widget build(BuildContext context) {
    final Color anaRenk = const Color(0xFF257bf4);
    return SafeArea(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          GlassHeader(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(t('discover_title'), style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text(t('discover_desc'), style: const TextStyle(color: Colors.grey, fontSize: 14)),
          ])),
          Expanded(
            child: FutureBuilder<List<FeedItem>>(
              future: _feedFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) return Center(child: CircularProgressIndicator(color: anaRenk));
                if (snapshot.hasError) {
                  // API hatası durumunda statik demo kartlar göster
                  return _statikFeed();
                }
                if (!snapshot.hasData || snapshot.data!.isEmpty) return _statikFeed();
                final feed = snapshot.data!;
                return GridView.builder(
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 2, mainAxisSpacing: 16, crossAxisSpacing: 16, childAspectRatio: 0.8),
                  padding: const EdgeInsets.all(24.0),
                  itemCount: feed.length,
                  itemBuilder: (context, index) {
                    final item = feed[index];
                    final thumbUrl = ApiServisi.buildImageUrl(item.thumbnailUrl);
                    return _DynamicFeedCard(item: item, thumbUrl: thumbUrl);
                  },
                );
              },
            ),
          ),
          const SizedBox(height: 80),
        ],
      ),
    );
  }

  Widget _statikFeed() {
    return GridView.count(
      crossAxisCount: 2, mainAxisSpacing: 16, crossAxisSpacing: 16,
      padding: const EdgeInsets.all(24.0), childAspectRatio: 0.8,
      children: const [
        _StaticFeedCard(resimUrl: 'https://images.unsplash.com/photo-1614200179396-2bdb77ebf81b?q=80&w=1000', kullaniciAdi: '@Viper_Garage', baslik: 'Skyline GTR R34', alevSayisi: 5430),
        _StaticFeedCard(resimUrl: 'https://images.unsplash.com/photo-1544829099-b9a0c07fad1a?q=80&w=1000', kullaniciAdi: '@Kaan_Drift', baslik: 'Neon Supra MK4', alevSayisi: 3125),
        _StaticFeedCard(resimUrl: 'https://images.unsplash.com/photo-1503376713222-25ec13d8cbb8?q=80&w=1000', kullaniciAdi: '@Ahmet3D', baslik: 'Porsche 911 GT3', alevSayisi: 820),
        _StaticFeedCard(resimUrl: 'https://images.unsplash.com/photo-1511919884226-fd3cad34687c?q=80&w=1000', kullaniciAdi: '@RacerMat', baslik: 'Aventador Spez.', alevSayisi: 1540),
      ],
    );
  }
}

// ── Dinamik Feed Kartı (Backend'den) ──
class _DynamicFeedCard extends StatefulWidget {
  final FeedItem item;
  final String? thumbUrl;
  const _DynamicFeedCard({required this.item, this.thumbUrl});
  @override
  State<_DynamicFeedCard> createState() => _DynamicFeedCardState();
}

class _DynamicFeedCardState extends State<_DynamicFeedCard> {
  late bool begenildi;
  late int alevSayisi;

  @override
  void initState() {
    super.initState();
    begenildi = widget.item.isLiked;
    alevSayisi = widget.item.likeCount;
  }

  void _alevTikla() async {
    HapticFeedback.selectionClick();
    setState(() { if (begenildi) { alevSayisi--; begenildi = false; } else { alevSayisi++; begenildi = true; } });
    try { await ApiServisi().begeniToggle(widget.item.scanId); } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final Color koyuYuzey = const Color(0xFF182434);
    final imageUrl = widget.thumbUrl ?? 'https://images.unsplash.com/photo-1614200179396-2bdb77ebf81b?q=80&w=1000';
    return Container(
      decoration: BoxDecoration(color: koyuYuzey, borderRadius: BorderRadius.circular(16), border: Border.all(color: Colors.white.withOpacity(0.05))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(child: ClipRRect(borderRadius: const BorderRadius.vertical(top: Radius.circular(16)), child: Image.network(imageUrl, width: double.infinity, fit: BoxFit.cover, errorBuilder: (c, e, s) => Container(color: Colors.black26, child: const Icon(Icons.image_not_supported, color: Colors.grey))))),
        Padding(padding: const EdgeInsets.all(12.0), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(widget.item.carName, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold), maxLines: 1, overflow: TextOverflow.ellipsis),
          const SizedBox(height: 2),
          Text('${t('by')}${widget.item.ownerName}', style: const TextStyle(color: Colors.grey, fontSize: 10), maxLines: 1, overflow: TextOverflow.ellipsis),
          const SizedBox(height: 8),
          InkWell(
            onTap: _alevTikla, borderRadius: BorderRadius.circular(12),
            child: AnimatedContainer(duration: const Duration(milliseconds: 300), padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), decoration: BoxDecoration(color: begenildi ? Colors.deepOrange.withOpacity(0.2) : Colors.deepOrange.withOpacity(0.05), borderRadius: BorderRadius.circular(12), border: Border.all(color: begenildi ? Colors.deepOrangeAccent : Colors.deepOrange.withOpacity(0.5))),
              child: Row(mainAxisSize: MainAxisSize.min, children: [const Text('🔥', style: TextStyle(fontSize: 14)), const SizedBox(width: 4), Text(alevSayisi.toString(), style: premiumNumberStyle.copyWith(color: begenildi ? Colors.white : Colors.deepOrange, fontWeight: FontWeight.bold, fontSize: 12))]),
            ),
          ),
        ])),
      ]),
    );
  }
}

// ── Statik Feed Kartı (Fallback) ──
class _StaticFeedCard extends StatefulWidget {
  final String resimUrl, kullaniciAdi, baslik;
  final int alevSayisi;
  const _StaticFeedCard({required this.resimUrl, required this.kullaniciAdi, required this.baslik, required this.alevSayisi});
  @override
  State<_StaticFeedCard> createState() => _StaticFeedCardState();
}

class _StaticFeedCardState extends State<_StaticFeedCard> {
  late int alevSayisi;
  bool begenildi = false;

  @override
  void initState() { super.initState(); alevSayisi = widget.alevSayisi; }

  @override
  Widget build(BuildContext context) {
    final Color koyuYuzey = const Color(0xFF182434);
    return Container(
      decoration: BoxDecoration(color: koyuYuzey, borderRadius: BorderRadius.circular(16), border: Border.all(color: Colors.white.withOpacity(0.05))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Expanded(child: ClipRRect(borderRadius: const BorderRadius.vertical(top: Radius.circular(16)), child: Image.network(widget.resimUrl, width: double.infinity, fit: BoxFit.cover, errorBuilder: (c, e, s) => Container(color: Colors.black26, child: const Icon(Icons.image_not_supported, color: Colors.grey))))),
        Padding(padding: const EdgeInsets.all(12.0), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(widget.baslik, style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold), maxLines: 1, overflow: TextOverflow.ellipsis),
          const SizedBox(height: 2),
          Text('${t('by')}${widget.kullaniciAdi}', style: const TextStyle(color: Colors.grey, fontSize: 10)),
          const SizedBox(height: 8),
          InkWell(onTap: () { HapticFeedback.selectionClick(); setState(() { if (begenildi) { alevSayisi--; begenildi = false; } else { alevSayisi++; begenildi = true; } }); }, borderRadius: BorderRadius.circular(12),
            child: AnimatedContainer(duration: const Duration(milliseconds: 300), padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), decoration: BoxDecoration(color: begenildi ? Colors.deepOrange.withOpacity(0.2) : Colors.deepOrange.withOpacity(0.05), borderRadius: BorderRadius.circular(12), border: Border.all(color: begenildi ? Colors.deepOrangeAccent : Colors.deepOrange.withOpacity(0.5))),
              child: Row(mainAxisSize: MainAxisSize.min, children: [const Text('🔥', style: TextStyle(fontSize: 14)), const SizedBox(width: 4), Text(alevSayisi.toString(), style: premiumNumberStyle.copyWith(color: begenildi ? Colors.white : Colors.deepOrange, fontWeight: FontWeight.bold, fontSize: 12))]),
            ),
          ),
        ])),
      ]),
    );
  }
}