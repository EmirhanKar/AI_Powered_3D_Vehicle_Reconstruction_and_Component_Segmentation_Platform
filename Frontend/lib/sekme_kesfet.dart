import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'sistem_ve_dil.dart';
import 'modeller/community_model.dart';
import 'modeller/scan_model.dart';
import 'servisler/api_servisi.dart';

class SekmeKesfet extends StatefulWidget {
  final bool isGuest;
  final int? currentUserId;
  final GlobalKey likeKey;
  final GlobalKey commentKey;
  const SekmeKesfet({
    super.key,
    this.isGuest = false,
    this.currentUserId,
    required this.likeKey,
    required this.commentKey,
  });
  @override
  State<SekmeKesfet> createState() => _SekmeKesfetState();
}

class _SekmeKesfetState extends State<SekmeKesfet> {
  Future<List<FeedItem>>? _feedFuture;

  @override
  void initState() {
    super.initState();
    if (!widget.isGuest) {
      _feedFuture = ApiServisi().feedGetir();
    }
  }

  void _alevTikla(FeedItem item) async {
    if (widget.isGuest) {
      ScaffoldMessenger.of(context).clearSnackBars();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('registration_required'))));
      return;
    }
    if (titresimAcik.value) HapticFeedback.selectionClick();
    final wasLiked = item.isLiked;
    setState(() {
      item.isLiked = !wasLiked;
      item.likeCount += wasLiked ? -1 : 1;
    });
    try {
      await ApiServisi().begeniToggle(item.scanId);
    } catch (e) {
      // Hata durumunda geri al
      setState(() {
        item.isLiked = wasLiked;
        item.likeCount += wasLiked ? 1 : -1;
      });
    }
  }

  void _yorumSayfasiAc(FeedItem item) {
    if (widget.isGuest) {
      ScaffoldMessenger.of(context).clearSnackBars();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('registration_required'))));
      return;
    }
    if (titresimAcik.value) HapticFeedback.lightImpact();
    Navigator.push(context, MaterialPageRoute(builder: (c) => GonderiDetaySayfasi(
      feedItem: item,
      currentUserId: widget.currentUserId,
    ))).then((_) {
      // Detaydan dönünce feed kartlarını güncelle (yorum/beğeni sayısı değişmiş olabilir)
      if (mounted) setState(() {});
    });
  }

  void _toplulugaPaylas() async {
    if (widget.isGuest) {
      ScaffoldMessenger.of(context).clearSnackBars();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('registration_required'))));
      return;
    }
    if (titresimAcik.value) HapticFeedback.lightImpact();
    try {
      final garaj = await ApiServisi().garajiGetir();
      final tamamlananlar = garaj.where((s) => s.isCompleted).toList();
      if (tamamlananlar.isEmpty) {
        if (mounted) {
          ScaffoldMessenger.of(context).clearSnackBars();
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Paylaşılacak tamamlanmış araç yok.'), backgroundColor: Colors.orange, behavior: SnackBarBehavior.floating));
        }
        return;
      }
      if (!mounted) return;
      _aracSecDialoguGoster(tamamlananlar);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceAll('Exception: ', '')), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
      }
    }
  }

  void _aracSecDialoguGoster(List<Scan> araclar) {
    showModalBottomSheet(context: context, backgroundColor: yuzeyRengi(), shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))), isScrollControlled: true, builder: (ctx) {
      return SafeArea(child: ConstrainedBox(
        constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.7),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Padding(padding: const EdgeInsets.all(16), child: Text(t('select_car_share'), style: TextStyle(color: yaziRengi(), fontSize: 18, fontWeight: FontWeight.bold))),
          Flexible(
            child: ListView(
              shrinkWrap: true,
              children: araclar.map((scan) => ListTile(
                leading: Container(width: 48, height: 48, decoration: BoxDecoration(borderRadius: BorderRadius.circular(8), color: yuzeyRengi()), child: scan.thumbnailUrl != null ? ClipRRect(borderRadius: BorderRadius.circular(8), child: Image.network(ApiServisi.buildImageUrl(scan.thumbnailUrl)!, fit: BoxFit.cover)) : const Icon(Icons.directions_car, color: Colors.grey)),
                title: Text(scan.carName, style: TextStyle(color: yaziRengi(), fontWeight: FontWeight.bold)),
                subtitle: Text((scan.method == '3d' || scan.method == '3d_single') ? '3D' : '2D', style: TextStyle(color: ikinciYaziRengi())),
                onTap: () async {
                  Navigator.pop(ctx);
                  try {
                    await ApiServisi().toplulugaPaylas(scan.scanId);
                    if (mounted) {
                      ScaffoldMessenger.of(context).clearSnackBars();
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('shared_success')), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating));
                      setState(() { _feedFuture = ApiServisi().feedGetir(); });
                    }
                  } catch (e) {
                    if (mounted) {
                      ScaffoldMessenger.of(context).clearSnackBars();
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceAll('Exception: ', '')), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
                    }
                  }
                },
              )).toList(),
            ),
          ),
          const SizedBox(height: 20),
        ]),
      ));
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
            child: RefreshIndicator(
              color: anaRenk,
              onRefresh: () async {
                if (!widget.isGuest) {
                  setState(() {
                    _feedFuture = ApiServisi().feedGetir();
                  });
                }
                await Future.delayed(const Duration(milliseconds: 800));
              },
              child: widget.isGuest
                  ? _buildDummyGrid()
                  : FutureBuilder<List<FeedItem>>(
                      future: _feedFuture,
                      builder: (context, snapshot) {
                        if (snapshot.connectionState == ConnectionState.waiting) return Center(child: CircularProgressIndicator(color: anaRenk));
                        if (snapshot.hasError) return Center(child: Text(t('connection_error'), style: TextStyle(color: yaziRengi())));
                        final items = snapshot.data ?? [];
                        if (items.isEmpty) return Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [const Icon(Icons.explore_off, color: Colors.grey, size: 48), const SizedBox(height: 12), Text(t('no_legends_yet'), style: TextStyle(color: ikinciYaziRengi(), fontSize: 16))]));
                        return GridView.builder(
                          padding: const EdgeInsets.all(16),
                          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 2, crossAxisSpacing: 12, mainAxisSpacing: 12, childAspectRatio: 0.68),
                          itemCount: items.length,
                          itemBuilder: (context, index) {
                            final item = items[index];
                            final thumbUrl = ApiServisi.buildImageUrl(item.thumbnailUrl);
                            debugPrint('[Keşfet] scan=${item.scanId} thumbUrl=$thumbUrl raw=${item.thumbnailUrl}');
                            final displayUrl = thumbUrl ?? 'https://images.unsplash.com/photo-1603386329225-868f9b1ee6c9?q=80&w=500';
                            return GestureDetector(
                              onTap: () => _yorumSayfasiAc(item),
                              child: _kesfetKartiOlustur(item, displayUrl, index),
                            );
                          },
                        );
                      },
                    ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDummyGrid() {
    final List<FeedItem> dummyItems = [
      FeedItem(scanId: 1, carName: 'Örnek Araç 1', ownerName: 'ModifAI', thumbnailUrl: 'https://images.unsplash.com/photo-1552519507-da3b142c6e3d?q=80&w=500', likeCount: 124, commentCount: 12, isLiked: false),
      FeedItem(scanId: 2, carName: 'Örnek Araç 2', ownerName: 'Misafir', thumbnailUrl: 'https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?q=80&w=500', likeCount: 89, commentCount: 5, isLiked: false),
      FeedItem(scanId: 3, carName: 'Örnek Araç 3', ownerName: 'Test', thumbnailUrl: 'https://images.unsplash.com/photo-1583121274602-3e2820c69888?q=80&w=500', likeCount: 245, commentCount: 30, isLiked: true),
      FeedItem(scanId: 4, carName: 'Örnek Araç 4', ownerName: 'Admin', thumbnailUrl: 'https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?q=80&w=500', likeCount: 56, commentCount: 2, isLiked: false),
    ];

    return GridView.builder(
      padding: const EdgeInsets.all(16),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 2, crossAxisSpacing: 12, mainAxisSpacing: 12, childAspectRatio: 0.68),
      itemCount: dummyItems.length,
      itemBuilder: (context, index) {
        final item = dummyItems[index];
        return GestureDetector(
          onTap: () => _yorumSayfasiAc(item),
          child: _kesfetKartiOlustur(item, item.thumbnailUrl!, index),
        );
      },
    );
  }


  Widget _kesfetKartiOlustur(FeedItem item, String thumbUrl, int index) {
    return Container(
      decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(16), border: Border.all(color: kartBorderRengi())),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: ClipRRect(borderRadius: const BorderRadius.vertical(top: Radius.circular(16)), child: Image.network(thumbUrl, width: double.infinity, fit: BoxFit.cover, loadingBuilder: (c, child, progress) { if (progress == null) return child; return Container(color: yuzeyRengi(), child: Center(child: CircularProgressIndicator(strokeWidth: 2, color: Colors.deepOrange.withValues(alpha: 0.5)))); }, errorBuilder: (c, e, s) => Container(color: yuzeyRengi(), child: Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [Icon(Icons.broken_image_outlined, color: ikinciYaziRengi(), size: 32), const SizedBox(height: 4), Text('Görsel yüklenemedi', style: TextStyle(color: ikinciYaziRengi(), fontSize: 9))])))))),
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
                  key: index == 0 ? widget.likeKey : null,
                  onTap: () => _alevTikla(item),
                  borderRadius: BorderRadius.circular(12),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(color: item.isLiked ? Colors.deepOrange.withValues(alpha: 0.2) : Colors.deepOrange.withValues(alpha: 0.05), borderRadius: BorderRadius.circular(12), border: Border.all(color: item.isLiked ? Colors.deepOrangeAccent : Colors.deepOrange.withValues(alpha: 0.5))),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [Text(item.isLiked ? '🔥' : '🔥', style: const TextStyle(fontSize: 12)), const SizedBox(width: 4), Text('${item.likeCount}', style: TextStyle(color: item.isLiked ? Colors.white : Colors.deepOrange, fontWeight: FontWeight.bold, fontSize: 11))]),
                  ),
                ),
                const SizedBox(width: 8),
                // Yorum sayısı
                Container(
                  key: index == 0 ? widget.commentKey : null,
                  child: Row(mainAxisSize: MainAxisSize.min, children: [Icon(Icons.comment_outlined, color: ikinciYaziRengi(), size: 14), const SizedBox(width: 4), Text('${item.commentCount}', style: TextStyle(color: ikinciYaziRengi(), fontSize: 11))]),
                ),
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
  final int? currentUserId;
  const GonderiDetaySayfasi({super.key, required this.feedItem, this.currentUserId});
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

  Future<void> _begeniTiklaDetay() async {
    if (titresimAcik.value) HapticFeedback.selectionClick();
    final wasLiked = widget.feedItem.isLiked;
    setState(() {
      widget.feedItem.isLiked = !wasLiked;
      widget.feedItem.likeCount += wasLiked ? -1 : 1;
    });
    try {
      await ApiServisi().begeniToggle(widget.feedItem.scanId);
    } catch (e) {
      setState(() {
        widget.feedItem.isLiked = wasLiked;
        widget.feedItem.likeCount += wasLiked ? 1 : -1;
      });
    }
  }

  Future<void> _yorumGonder() async {
    final icerik = _yorumController.text.trim();
    if (icerik.isEmpty) return;
    setState(() => _gonderiliyor = true);
    try {
      await ApiServisi().yorumEkle(widget.feedItem.scanId, icerik);
      _yorumController.clear();
      // Madde 4: Anlık sayı artışı
      setState(() {
        widget.feedItem.commentCount++;
        _yorumFuture = ApiServisi().yorumlariGetir(widget.feedItem.scanId);
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceAll('Exception: ', '')), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
      }
    } finally {
      if (mounted) setState(() => _gonderiliyor = false);
    }
  }

  void _yorumBegeniTikla(Yorum yorum) async {
    if (titresimAcik.value) HapticFeedback.selectionClick();
    final wasLiked = yorum.isLiked;
    setState(() {
      yorum.isLiked = !wasLiked;
      yorum.likeCount += wasLiked ? -1 : 1;
    });
    try {
      await ApiServisi().yorumBegeniToggle(yorum.commentId);
    } catch (e) {
      setState(() {
        yorum.isLiked = wasLiked;
        yorum.likeCount += wasLiked ? 1 : -1;
      });
    }
  }

  Future<void> _yorumSil(Yorum yorum) async {
    if (titresimAcik.value) HapticFeedback.mediumImpact();
    try {
      await ApiServisi().yorumSil(yorum.commentId);
      setState(() {
        widget.feedItem.commentCount = (widget.feedItem.commentCount - 1).clamp(0, 999999);
        _yorumFuture = ApiServisi().yorumlariGetir(widget.feedItem.scanId);
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceAll('Exception: ', '')), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final Color anaRenk = const Color(0xFF257bf4);
    final thumbUrl = ApiServisi.buildImageUrl(widget.feedItem.thumbnailUrl) ?? 'https://images.unsplash.com/photo-1603386329225-868f9b1ee6c9?q=80&w=1000';

    return Scaffold(
      backgroundColor: arkaplanRengi(),
      resizeToAvoidBottomInset: true, // Klavye için önemli
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(icon: Icon(Icons.arrow_back, color: yaziRengi()), onPressed: () => Navigator.pop(context)),
        title: Text(widget.feedItem.carName, style: TextStyle(color: yaziRengi(), fontWeight: FontWeight.bold)),
        centerTitle: true,
      ),
      body: GestureDetector(
        onTap: () => FocusScope.of(context).unfocus(),
        child: Column(
          children: [
            Expanded(
              child: CustomScrollView(
                slivers: [
                  SliverToBoxAdapter(
                    child: Column(
                      children: [
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
                            InkWell(
                              onTap: () => _begeniTiklaDetay(),
                              borderRadius: BorderRadius.circular(16),
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                                decoration: BoxDecoration(color: widget.feedItem.isLiked ? Colors.deepOrange.withValues(alpha: 0.2) : Colors.deepOrange.withValues(alpha: 0.05), borderRadius: BorderRadius.circular(16), border: Border.all(color: widget.feedItem.isLiked ? Colors.deepOrangeAccent : Colors.deepOrange.withValues(alpha: 0.5))),
                                child: Row(children: [const Text('🔥', style: TextStyle(fontSize: 16)), const SizedBox(width: 4), Text('${widget.feedItem.likeCount}', style: TextStyle(color: widget.feedItem.isLiked ? Colors.white : yaziRengi(), fontWeight: FontWeight.bold))]),
                              ),
                            ),
                          ]),
                        ),
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          child: Row(children: [Icon(Icons.comment, color: anaRenk, size: 18), const SizedBox(width: 8), Text(t('comments'), style: TextStyle(color: yaziRengi(), fontSize: 16, fontWeight: FontWeight.bold))]),
                        ),
                        const SizedBox(height: 8),
                      ],
                    ),
                  ),
                  FutureBuilder<List<Yorum>>(
                    future: _yorumFuture,
                    builder: (context, snapshot) {
                      if (snapshot.connectionState == ConnectionState.waiting) return const SliverFillRemaining(child: Center(child: CircularProgressIndicator()));
                      final yorumlar = snapshot.data ?? [];
                      if (yorumlar.isEmpty) return SliverFillRemaining(child: Center(child: Text(t('no_comments'), style: TextStyle(color: ikinciYaziRengi()))));
                      
                      return SliverPadding(
                        padding: const EdgeInsets.symmetric(horizontal: 16),
                        sliver: SliverList(
                          delegate: SliverChildBuilderDelegate(
                            (context, index) {
                              final yorum = yorumlar[index];
                              return Container(
                                margin: const EdgeInsets.only(bottom: 12),
                                padding: const EdgeInsets.all(12),
                                decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(12), border: Border.all(color: kartBorderRengi())),
                                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                  Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                                    // Madde 3: İsim veritabanından
                                    Text(yorum.userName, style: TextStyle(color: anaRenk, fontWeight: FontWeight.bold, fontSize: 13)),
                                    Text(_zamanHesapla(yorum.createdAt), style: TextStyle(color: ikinciYaziRengi(), fontSize: 10)),
                                  ]),
                                  const SizedBox(height: 8),
                                  Text(yorum.content, style: TextStyle(color: yaziRengi(), fontSize: 14, height: 1.4)),
                                  const SizedBox(height: 10),
                                  // Madde 2: Yorum beğenisi
                                  Row(
                                    children: [
                                      InkWell(
                                        onTap: () => _yorumBegeniTikla(yorum),
                                        child: Row(
                                          children: [
                                            Icon(yorum.isLiked ? Icons.favorite : Icons.favorite_border, color: yorum.isLiked ? Colors.redAccent : ikinciYaziRengi(), size: 16),
                                            const SizedBox(width: 4),
                                            Text('${yorum.likeCount}', style: TextStyle(color: ikinciYaziRengi(), fontSize: 12)),
                                          ],
                                        ),
                                      ),
                                      const Spacer(),
                                      // Yorum silme butonu (sadece kendi yorumu)
                                      if (widget.currentUserId != null && yorum.userId == widget.currentUserId)
                                        InkWell(
                                          onTap: () => _yorumSil(yorum),
                                          borderRadius: BorderRadius.circular(8),
                                          child: Padding(
                                            padding: const EdgeInsets.all(4),
                                            child: Icon(Icons.delete_outline, color: Colors.redAccent.withValues(alpha: 0.7), size: 16),
                                          ),
                                        ),
                                    ],
                                  ),
                                ]),
                              );
                            },
                            childCount: yorumlar.length,
                          ),
                        ),
                      );
                    },
                  ),
                ],
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
      ),
    );
  }


  String _zamanHesapla(DateTime dt) {
    final fark = DateTime.now().difference(dt);
    if (fark.inSeconds < 60) return 'şimdi';
    if (fark.inMinutes < 60) return '${fark.inMinutes} dk';
    if (fark.inHours < 24) return '${fark.inHours} sa';
    if (fark.inDays < 7) return '${fark.inDays} g';
    return '${dt.day}.${dt.month}.${dt.year}';
  }
}