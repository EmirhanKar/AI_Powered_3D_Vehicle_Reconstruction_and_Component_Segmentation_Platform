import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';
import 'sistem_ve_dil.dart';
import 'ortak_widgetlar.dart';
import 'modeller/kullanici_model.dart';
import 'modeller/scan_model.dart';
import 'servisler/api_servisi.dart';
import 'sayfalar/model_3d_viewer.dart';
import 'sayfalar_islem.dart';

class SekmeGaraj extends StatefulWidget {
  final Kullanici? kullanici;
  final bool isGuest;
  final bool showBackButton;
  
  const SekmeGaraj({
    super.key,
    this.kullanici,
    this.isGuest = false,
    this.showBackButton = false,
  });

  @override
  State<SekmeGaraj> createState() => _SekmeGarajState();
}

class _SekmeGarajState extends State<SekmeGaraj> with SingleTickerProviderStateMixin {
  final Color anaRenk = const Color(0xFF257bf4);
  Future<List<Scan>>? _garajFuture;
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    if (!widget.isGuest) {
      _garajFuture = ApiServisi().garajiGetir();
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  String _zamanHesapla(DateTime dt) {
    final fark = DateTime.now().difference(dt);
    if (fark.inMinutes < 60) return '${fark.inMinutes} dk önce';
    if (fark.inHours < 24) return '${fark.inHours} saat önce';
    if (fark.inDays < 7) return '${fark.inDays} gün önce';
    return '${dt.day}.${dt.month}.${dt.year}';
  }

  void _scanSil(Scan scan) async {
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
  }

  Widget _buildDetay(Scan scan) {
    return SafeArea(child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(scan.carName, style: TextStyle(color: yaziRengi(), fontSize: 22, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),

        Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Text('Oluşturulma', style: TextStyle(color: ikinciYaziRengi(), fontSize: 14)),
            Text(_zamanHesapla(scan.createdAt), style: TextStyle(color: yaziRengi(), fontSize: 14, fontWeight: FontWeight.w600)),
          ]),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Modifiyeler:', style: TextStyle(color: ikinciYaziRengi(), fontSize: 14)),
              const SizedBox(height: 8),
              if (scan.modifications.isEmpty)
                Text('Modifiye yok', style: TextStyle(color: yaziRengi(), fontSize: 14, fontWeight: FontWeight.w600))
              else
                ...scan.modifications.map((m) {
                  List<String> details = [];
                  if (m.jantName != null) details.add('Jant: ${m.jantName}');
                  if (m.colorCode != null) details.add('Renk: ${m.colorCode}');
                  if (details.isEmpty) return const SizedBox.shrink();
                  
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 4.0),
                    child: Text('• ${details.join(", ")}', style: TextStyle(color: yaziRengi(), fontSize: 14, fontWeight: FontWeight.w600)),
                  );
                }),
            ],
          ),
        ),
        const SizedBox(height: 16),
      ]),
    ));
  }


  Future<void> _yenile() async {
    if (!mounted || widget.isGuest) return;
    setState(() {
      _garajFuture = ApiServisi().garajiGetir();
    });
    try {
      await _garajFuture;
    } catch (_) {}
  }

  Widget _buildList(List<Scan> scans, String method) {
    final filtered = scans.where((s) {
      if (method == '3d') {
        return s.method == '3d' || s.method == '3d_single';
      }
      return s.method == method;
    }).toList();

    return RefreshIndicator(
      onRefresh: _yenile,
      color: anaRenk,
      child: filtered.isEmpty
          ? ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                SizedBox(height: MediaQuery.of(context).size.height * 0.25),
                Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.garage, size: 64, color: yaziRengi().withOpacity(0.2)),
                      const SizedBox(height: 16),
                      Text(
                        'Garajınızda henüz ${method == '3d' ? '3D' : '2D'} araba bulunmuyor.\n(Yenilemek için aşağı çekin)',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: ikinciYaziRengi(), fontSize: 15),
                      ),
                    ],
                  ),
                ),
              ],
            )
          : ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              itemCount: filtered.length,
              itemBuilder: (context, index) {
        final scan = filtered[index];
        final thumbUrl = ApiServisi.buildImageUrl(scan.thumbnailUrl) ?? 'https://images.unsplash.com/photo-1603386329225-868f9b1ee6c9?q=80&w=1000';
        
        return Padding(
          padding: const EdgeInsets.only(bottom: 16.0),
          child: ArabaKartiOlusturucu.olustur(
            scan.carName,
            (scan.method == '3d' || scan.method == '3d_single') ? '3D Model' : '2D Modifiye',
            thumbUrl,
            _zamanHesapla(scan.createdAt),
            anaRenk,
            yuzeyRengi(),
            scanId: scan.scanId,
            showEditButton: scan.canModify,
            onDuzenle: () {
              if (titresimAcik.value) HapticFeedback.mediumImpact();
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (c) => ModifiyeSecimSayfasi(
                    scanId: scan.scanId,
                    carName: scan.carName,
                    method: scan.method,
                    scan: scan,
                  ),
                ),
              ).then((_) {
                if (mounted) {
                  setState(() {
                    _garajFuture = ApiServisi().garajiGetir();
                  });
                }
              });
            },
            isShared: scan.isShared,
            onGoster: () {
              if (titresimAcik.value) HapticFeedback.mediumImpact();
              if ((scan.method == '3d' || scan.method == '3d_single') && scan.has3DModel) {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => Model3DViewer(
                      modelUrl: scan.modelUrl!,
                      carName: scan.carName,
                      thumbnailUrl: scan.thumbnailUrl,
                    ),
                  ),
                );
              } else if ((scan.method == '3d' || scan.method == '3d_single') && !scan.has3DModel) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Row(
                      children: [
                        const SizedBox(
                          width: 18, height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        ),
                        const SizedBox(width: 12),
                        const Text('3D model henüz hazırlanıyor...', style: TextStyle(color: Colors.white)),
                      ],
                    ),
                    backgroundColor: Colors.deepOrange,
                    behavior: SnackBarBehavior.floating,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    margin: const EdgeInsets.all(20),
                  ),
                );
              } else {
                // 2D: Yüksek çözünürlüklü işlenmiş görseli (yoksa thumbnail) göster
                final imgUrl = ApiServisi.buildImageUrl(scan.imageUrl ?? scan.thumbnailUrl);
                if (imgUrl != null) {
                  _goster2DResimDialog(context, scan, imgUrl);
                }
              }
            },
            onPaylas: () async {
              if (titresimAcik.value) HapticFeedback.mediumImpact();
              Share.share('${scan.carName} modifiyem nasıl olmuş? \n\n$thumbUrl', subject: 'Modif AI');
            },
            onSil: () => _scanSil(scan),
            onDetay: () {
              if (titresimAcik.value) HapticFeedback.lightImpact();
              showModalBottomSheet(context: context, backgroundColor: yuzeyRengi(), shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))), builder: (ctx) {
                return _buildDetay(scan);
              });
            },
          ),
        );
      },
    ),
  );
}

  @override
  Widget build(BuildContext context) {
    if (widget.isGuest) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.lock_outline, size: 64, color: yaziRengi().withOpacity(0.5)),
            const SizedBox(height: 16),
            Text('Garajı görmek için giriş yapmalısınız.', style: TextStyle(color: yaziRengi(), fontSize: 16)),
          ],
        ),
      );
    }

    return Scaffold(
      backgroundColor: arkaplanRengi(),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        automaticallyImplyLeading: false,
        leading: widget.showBackButton && Navigator.of(context).canPop()
            ? IconButton(
                icon: Icon(Icons.arrow_back, color: yaziRengi()),
                onPressed: () => Navigator.pop(context),
              )
            : null,
        title: Text('Garajım', style: TextStyle(color: yaziRengi(), fontSize: 18, fontWeight: FontWeight.bold)),
        centerTitle: true,
        actions: [
          IconButton(
            icon: Icon(Icons.refresh, color: yaziRengi()),
            tooltip: 'Yenile',
            onPressed: () {
              if (titresimAcik.value) HapticFeedback.lightImpact();
              _yenile();
            },
          ),
        ],
      ),
      body: Column(
        children: [
          TabBar(
            controller: _tabController,
            indicatorColor: anaRenk,
            labelColor: anaRenk,
            unselectedLabelColor: ikinciYaziRengi(),
            tabs: const [
              Tab(text: '2D Projeler'),
              Tab(text: '3D Projeler'),
            ],
          ),
          Expanded(
            child: FutureBuilder<List<Scan>>(
              future: _garajFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return Center(child: CircularProgressIndicator(color: anaRenk));
                }
                if (snapshot.hasError || !snapshot.hasData) {
                  return Center(child: Text('Garaj yüklenemedi.', style: TextStyle(color: yaziRengi())));
                }

                final scans = snapshot.data!;
                return TabBarView(
                  controller: _tabController,
                  children: [
                    _buildList(scans, '2d'),
                    _buildList(scans, '3d'),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  void _goster2DResimDialog(BuildContext context, Scan scan, String imgUrl) {
    showDialog(
      context: context,
      barrierDismissible: true,
      builder: (context) {
        bool isDownloading = false;
        bool isSharing = false;

        return StatefulBuilder(
          builder: (context, setState) {
            return Dialog(
              backgroundColor: Colors.transparent,
              insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 24),
              child: Container(
                decoration: BoxDecoration(
                  color: arkaplanRengi(),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(
                    color: anaRenk.withOpacity(0.3),
                    width: 2,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: anaRenk.withOpacity(0.15),
                      blurRadius: 20,
                      spreadRadius: 5,
                    ),
                  ],
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Header
                    Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  scan.carName,
                                  style: TextStyle(
                                    color: yaziRengi(),
                                    fontSize: 18,
                                    fontWeight: FontWeight.bold,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  'Yakınlaştırmak için kaydırın/çimdikleyin',
                                  style: TextStyle(
                                    color: ikinciYaziRengi(),
                                    fontSize: 11,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            icon: Icon(Icons.close, color: yaziRengi()),
                            onPressed: () => Navigator.pop(context),
                          ),
                        ],
                      ),
                    ),

                    // Image Frame
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16.0),
                      child: Container(
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(
                            color: anaRenk.withOpacity(0.5),
                            width: 3,
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.5),
                              blurRadius: 10,
                            ),
                          ],
                        ),
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(13),
                          child: AspectRatio(
                            aspectRatio: 16 / 9,
                            child: InteractiveViewer(
                              panEnabled: true,
                              boundaryMargin: const EdgeInsets.all(20),
                              minScale: 0.5,
                              maxScale: 4.0,
                              child: Image.network(
                                imgUrl,
                                fit: BoxFit.cover,
                                loadingBuilder: (context, child, loadingProgress) {
                                  if (loadingProgress == null) return child;
                                  return Center(
                                    child: CircularProgressIndicator(
                                      color: anaRenk,
                                      value: loadingProgress.expectedTotalBytes != null
                                          ? loadingProgress.cumulativeBytesLoaded /
                                              loadingProgress.expectedTotalBytes!
                                          : null,
                                    ),
                                  );
                                },
                                errorBuilder: (context, error, stackTrace) {
                                  return Center(
                                    child: Icon(Icons.broken_image, size: 64, color: ikinciYaziRengi()),
                                  );
                                },
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),

                    // Action Buttons
                    Padding(
                      padding: const EdgeInsets.all(20.0),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        children: [
                          // Download Button
                          Expanded(
                            child: Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 8.0),
                              child: ElevatedButton.icon(
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: const Color(0xFF1E293B),
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(vertical: 14),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                    side: BorderSide(color: Colors.grey.shade800),
                                  ),
                                ),
                                onPressed: isDownloading || isSharing
                                    ? null
                                    : () async {
                                        setState(() {
                                          isDownloading = true;
                                        });
                                        try {
                                          final response = await http.get(Uri.parse(imgUrl));
                                          if (response.statusCode == 200) {
                                            bool saved = false;
                                            try {
                                              const channel = MethodChannel('com.example.araba_app101/gallery');
                                              final fileName = 'modifai_${scan.carName.replaceAll(" ", "_")}_${DateTime.now().millisecondsSinceEpoch}.jpg';
                                              final result = await channel.invokeMethod('saveImageToGallery', {
                                                'imageBytes': response.bodyBytes,
                                                'fileName': fileName,
                                              });
                                              if (result != null) {
                                                saved = true;
                                              }
                                            } catch (e) {
                                              debugPrint('MethodChannel save error: $e');
                                            }

                                            if (saved) {
                                              if (context.mounted) {
                                                ScaffoldMessenger.of(context).showSnackBar(
                                                  const SnackBar(
                                                    content: Text('Fotoğraf başarıyla galeriye kaydedildi!'),
                                                    backgroundColor: Colors.green,
                                                    behavior: SnackBarBehavior.floating,
                                                  ),
                                                );
                                              }
                                            } else {
                                              // Fallback to launch in browser
                                              if (await canLaunchUrl(Uri.parse(imgUrl))) {
                                                await launchUrl(Uri.parse(imgUrl),
                                                    mode: LaunchMode.externalApplication);
                                                if (context.mounted) {
                                                  ScaffoldMessenger.of(context).showSnackBar(
                                                    const SnackBar(
                                                      content: Text('Tarayıcıda açıldı. Kaydetmek için üzerine basılı tutun.'),
                                                      backgroundColor: Colors.blue,
                                                      behavior: SnackBarBehavior.floating,
                                                    ),
                                                  );
                                                }
                                              }
                                            }
                                          }
                                        } catch (e) {
                                          if (context.mounted) {
                                            ScaffoldMessenger.of(context).showSnackBar(
                                              SnackBar(
                                                content: Text('İndirme hatası: $e'),
                                                backgroundColor: Colors.redAccent,
                                                behavior: SnackBarBehavior.floating,
                                              ),
                                            );
                                          }
                                        } finally {
                                          if (context.mounted) {
                                            setState(() {
                                              isDownloading = false;
                                            });
                                          }
                                        }
                                      },
                                icon: isDownloading
                                    ? const SizedBox(
                                        width: 18,
                                        height: 18,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: Colors.white,
                                        ),
                                      )
                                    : const Icon(Icons.download, size: 20),
                                label: const Text(
                                  'İndir',
                                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                                ),
                              ),
                            ),
                          ),

                          // Share Button
                          Expanded(
                            child: Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 8.0),
                              child: ElevatedButton.icon(
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: anaRenk,
                                  foregroundColor: Colors.white,
                                  padding: const EdgeInsets.symmetric(vertical: 14),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  elevation: 4,
                                ),
                                onPressed: isDownloading || isSharing
                                    ? null
                                    : () async {
                                        setState(() {
                                          isSharing = true;
                                        });
                                        try {
                                          final response = await http.get(Uri.parse(imgUrl));
                                          if (response.statusCode == 200) {
                                            final tempDir = Directory.systemTemp;
                                            final tempPath =
                                                '${tempDir.path}/share_${scan.carName.replaceAll(" ", "_")}_${DateTime.now().millisecondsSinceEpoch}.jpg';
                                            final file = File(tempPath);
                                            await file.writeAsBytes(response.bodyBytes);

                                            await Share.shareXFiles(
                                              [XFile(tempPath)],
                                              text: '${scan.carName} modifiyem nasıl olmuş? #ModifAI',
                                            );
                                          }
                                        } catch (e) {
                                          if (context.mounted) {
                                            ScaffoldMessenger.of(context).showSnackBar(
                                              SnackBar(
                                                content: Text('Paylaşım hatası: $e'),
                                                backgroundColor: Colors.redAccent,
                                                behavior: SnackBarBehavior.floating,
                                              ),
                                            );
                                          }
                                        } finally {
                                          if (context.mounted) {
                                            setState(() {
                                              isSharing = false;
                                            });
                                          }
                                        }
                                      },
                                icon: isSharing
                                    ? const SizedBox(
                                        width: 18,
                                        height: 18,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: Colors.white,
                                        ),
                                      )
                                    : const Icon(Icons.share, size: 20),
                                label: const Text(
                                  'Paylaş',
                                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                                ),
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
          },
        );
      },
    );
  }
}
