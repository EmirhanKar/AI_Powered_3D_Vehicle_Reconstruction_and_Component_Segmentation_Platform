import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';
import 'sistem_ve_dil.dart';
import 'ortak_widgetlar.dart';
import 'modeller/magaza_model.dart';
import 'servisler/api_servisi.dart';

class SekmeMagaza extends StatefulWidget {
  final VoidCallback? onCreditsChanged;
  final bool isGuest;
  const SekmeMagaza({super.key, this.onCreditsChanged, this.isGuest = false});
  @override
  State<SekmeMagaza> createState() => _SekmeMagazaState();
}

class _SekmeMagazaState extends State<SekmeMagaza> {
  Future<List<Paket>>? _paketFuture;
  bool _satinAlinyor = false;

  @override
  void initState() {
    super.initState();
    if (!widget.isGuest) {
      _paketFuture = ApiServisi().paketleriGetir();
    }
  }

  Future<void> _satinAl(Paket paket) async {
    if (_satinAlinyor) return;
    if (titresimAcik.value) HapticFeedback.mediumImpact();
    setState(() => _satinAlinyor = true);
    try {
      final sonuc = await ApiServisi().paketSatinAl(paket.packageId);
      if (mounted) {
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${sonuc.message} +${sonuc.creditsAdded} ${t('credits_total')} ${sonuc.currentCredits}'), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating));
        // Madde 1: Anlık kredi güncelleme
        widget.onCreditsChanged?.call();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).clearSnackBars();
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().replaceAll("Exception: ", "")), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
      }
    } finally {
      if (mounted) setState(() => _satinAlinyor = false);
    }
  }

  // Madde 2: Arkadaşını Davet Et — Paylaşım bottom sheet
  void _davetEtDialoguGoster() {
    if (titresimAcik.value) HapticFeedback.lightImpact();
    final String paylasilacakLink = t('invite_share_text');

    showModalBottomSheet(
      context: context,
      backgroundColor: yuzeyRengi(),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      builder: (ctx) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(width: 40, height: 4, decoration: BoxDecoration(color: Colors.grey.shade600, borderRadius: BorderRadius.circular(2))),
                const SizedBox(height: 20),
                Text(t('invite_title'), style: TextStyle(color: yaziRengi(), fontSize: 22, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                Text(t('invite_desc'), style: TextStyle(color: ikinciYaziRengi(), fontSize: 13), textAlign: TextAlign.center),
                const SizedBox(height: 24),
                // 4 + 4 grid
                GridView.count(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  crossAxisCount: 4,
                  mainAxisSpacing: 16,
                  crossAxisSpacing: 16,
                  children: [
                    _platformButonu(ctx, 'WhatsApp', Icons.chat, const Color(0xFF25D366), paylasilacakLink),
                    _platformButonu(ctx, 'Instagram', Icons.camera_alt, const Color(0xFFE1306C), paylasilacakLink),
                    _platformButonu(ctx, 'Telegram', Icons.send, const Color(0xFF0088CC), paylasilacakLink),
                    _platformButonu(ctx, 'Gmail', Icons.email, const Color(0xFFEA4335), paylasilacakLink),
                    _platformButonu(ctx, 'Mesajlar', Icons.sms, const Color(0xFF34B7F1), paylasilacakLink),
                    _platformButonu(ctx, 'Bluetooth', Icons.bluetooth, const Color(0xFF0082FC), paylasilacakLink),
                    _platformButonu(ctx, 'Drive', Icons.cloud_upload, const Color(0xFF4285F4), paylasilacakLink),
                    _platformButonu(ctx, 'Quick Share', Icons.share, const Color(0xFF00BCD4), paylasilacakLink),
                  ],
                ),
                const SizedBox(height: 16),
                // Link kopyala butonu
                OutlinedButton.icon(
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: 'https://modifai.app/download'));
                    if (mounted) {
                      ScaffoldMessenger.of(context).clearSnackBars();
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('invite_link_copied')), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating));
                    }
                  },
                  icon: const Icon(Icons.copy, size: 18),
                  label: Text(t('invite_link_copied'), style: const TextStyle(fontSize: 12)),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.grey,
                    side: const BorderSide(color: Colors.grey),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _platformButonu(BuildContext ctx, String isim, IconData ikon, Color renk, String metin) {
    return InkWell(
      onTap: () async {
        Navigator.pop(ctx);
        if (widget.isGuest) {
          ScaffoldMessenger.of(context).clearSnackBars();
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('registration_required'))));
          return;
        }
        if (titresimAcik.value) HapticFeedback.mediumImpact();
        // share_plus ile paylaş
        await Share.share(metin);
        // Backend'e referral bildir — 50 kredi ekle
        try {
          await ApiServisi().davetPaylas();
          if (mounted) {
            ScaffoldMessenger.of(context).clearSnackBars();
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(t('invite_success')), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating));
            widget.onCreditsChanged?.call();
          }
        } catch (_) {}
      },
      borderRadius: BorderRadius.circular(16),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 52, height: 52,
            decoration: BoxDecoration(color: renk.withValues(alpha: 0.15), shape: BoxShape.circle),
            child: Icon(ikon, color: renk, size: 26),
          ),
          const SizedBox(height: 6),
          Text(isim, style: TextStyle(color: ikinciYaziRengi(), fontSize: 10, fontWeight: FontWeight.w500), textAlign: TextAlign.center, maxLines: 1, overflow: TextOverflow.ellipsis),
        ],
      ),
    );
  }

  // Madde 3: SSS sayfasına git
  void _sssSayfasiAc() {
    if (titresimAcik.value) HapticFeedback.lightImpact();
    Navigator.push(context, MaterialPageRoute(builder: (c) => const SSSSayfasi()));
  }

  @override
  Widget build(BuildContext context) {
    final Color anaRenk = const Color(0xFF257bf4);
    final Color koyuArkaplan = arkaplanRengi();
    final Color koyuYuzey = yuzeyRengi();

    return SafeArea(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          GlassHeader(
            child: Row(
              children: [
                if (Navigator.maybeOf(context)?.canPop() ?? false) ...[
                  IconButton(
                    icon: Icon(Icons.arrow_back, color: yaziRengi()),
                    onPressed: () => Navigator.pop(context),
                  ),
                  const SizedBox(width: 8),
                ],
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(t('store_title'), style: TextStyle(color: yaziRengi(), fontSize: 28, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 8),
                      Text(t('store_desc'), style: TextStyle(color: ikinciYaziRengi(), fontSize: 14)),
                    ],
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: widget.isGuest
                ? _buildGuestView()
                : FutureBuilder<List<Paket>>(
                    future: _paketFuture,
                    builder: (context, snapshot) {
                      if (snapshot.connectionState == ConnectionState.waiting) return Center(child: CircularProgressIndicator(color: anaRenk));
                      if (snapshot.hasError) {
                        return Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              const Icon(Icons.error_outline, color: Colors.redAccent, size: 48),
                              const SizedBox(height: 16),
                              Text(
                                appLanguage.value == 'tr'
                                    ? 'Paketler yüklenirken hata oluştu.'
                                    : 'Failed to load packages.',
                                style: TextStyle(color: yaziRengi(), fontSize: 14),
                              ),
                              const SizedBox(height: 12),
                              ElevatedButton(
                                onPressed: () {
                                  setState(() {
                                    _paketFuture = ApiServisi().paketleriGetir();
                                  });
                                },
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: anaRenk,
                                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                                ),
                                child: Text(
                                  appLanguage.value == 'tr' ? 'Yeniden Dene' : 'Retry',
                                  style: const TextStyle(color: Colors.white),
                                ),
                              ),
                            ],
                          ),
                        );
                      }
                      final paketler = snapshot.data ?? [];
                      return SingleChildScrollView(
                        padding: const EdgeInsets.all(24.0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Text(t('packages'), style: TextStyle(color: yaziRengi(), fontSize: 20, fontWeight: FontWeight.bold)),
                            const SizedBox(height: 16),
                            ...paketler.map((paket) {
                              if (paket.isSubscription) return _abonelikKarti(paket, koyuArkaplan, koyuYuzey);
                              return Padding(padding: const EdgeInsets.only(bottom: 16), child: _paketKarti(paket, koyuYuzey, anaRenk));
                            }),
                            const SizedBox(height: 16),
                            // Arkadaşını davet et butonu
                            InkWell(
                              onTap: _davetEtDialoguGoster,
                              borderRadius: BorderRadius.circular(16),
                              child: Container(padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20), decoration: BoxDecoration(gradient: LinearGradient(colors: [Colors.purple.shade800, Colors.pink]), borderRadius: BorderRadius.circular(16), boxShadow: [BoxShadow(color: Colors.pink.withValues(alpha: 0.4), blurRadius: 10, spreadRadius: 1)]),
                                child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [const Icon(Icons.group_add, color: Colors.white, size: 28), const SizedBox(width: 12), Text(t('invite_friend'), textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14))]),
                              ),
                            ),
                            const SizedBox(height: 24),
                            Center(child: TextButton.icon(onPressed: _sssSayfasiAc, icon: const Icon(Icons.help_outline, color: Colors.grey, size: 18), label: Text(t('faq'), style: const TextStyle(color: Colors.grey)))),
                            const SizedBox(height: 100),
                          ],
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildGuestView() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(color: yuzeyRengi(), borderRadius: BorderRadius.circular(16)),
            child: Text(t('registration_required'), style: TextStyle(color: ikinciYaziRengi(), fontSize: 14), textAlign: TextAlign.center),
          ),
          const SizedBox(height: 32),
          // Arkadaşını davet et butonu
          InkWell(
            onTap: _davetEtDialoguGoster,
            borderRadius: BorderRadius.circular(16),
            child: Container(padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20), decoration: BoxDecoration(gradient: LinearGradient(colors: [Colors.purple.shade800, Colors.pink]), borderRadius: BorderRadius.circular(16), boxShadow: [BoxShadow(color: Colors.pink.withValues(alpha: 0.4), blurRadius: 10, spreadRadius: 1)]),
              child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [const Icon(Icons.group_add, color: Colors.white, size: 28), const SizedBox(width: 12), Text(t('invite_friend'), textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14))]),
            ),
          ),
        ],
      ),
    );
  }

  Widget _paketKarti(Paket paket, Color koyuYuzey, Color anaRenk) {
    final renk = paket.isFeatured ? Colors.purpleAccent : anaRenk;
    final ikon = paket.bonusCredits > 0 ? Icons.diamond : Icons.diamond_outlined;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        InkWell(
          onTap: _satinAlinyor ? null : () => _satinAl(paket),
          borderRadius: BorderRadius.circular(16),
          child: Container(
            padding: const EdgeInsets.all(20), decoration: BoxDecoration(color: koyuYuzey, borderRadius: BorderRadius.circular(16), border: Border.all(color: kartBorderRengi())),
            child: Row(children: [
              Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: renk.withValues(alpha: 0.1), shape: BoxShape.circle), child: Icon(ikon, color: renk, size: 28)),
              const SizedBox(width: 16),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Text(paket.name, style: TextStyle(color: yaziRengi(), fontSize: 18, fontWeight: FontWeight.bold)),
                  if (paket.bonusCredits > 0) ...[const SizedBox(width: 8), Container(padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2), decoration: BoxDecoration(color: Colors.green, borderRadius: BorderRadius.circular(4)), child: Text('+${paket.bonusCredits} Bonus', style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)))],
                ]),
                const SizedBox(height: 4),
                Text(paket.description, style: TextStyle(color: ikinciYaziRengi(), fontSize: 12)),
              ])),
              Text('${paket.price} ₺', style: premiumNumberStyle.copyWith(color: yaziRengi(), fontSize: 18)),
            ]),
          ),
        ),
        if (paket.isFeatured) Positioned(top: -10, right: 0, child: Transform.rotate(angle: 0.1, child: Container(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6), decoration: BoxDecoration(color: Colors.deepOrange, borderRadius: BorderRadius.circular(12), boxShadow: [BoxShadow(color: Colors.deepOrange.withValues(alpha: 0.5), blurRadius: 8)]), child: Text(t('best_deal'), style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold))))),
      ],
    );
  }

  Widget _abonelikKarti(Paket paket, Color koyuArkaplan, Color koyuYuzey) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: InkWell(
        onTap: _satinAlinyor ? null : () => _satinAl(paket),
        borderRadius: BorderRadius.circular(20),
        child: Container(
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(20), gradient: const LinearGradient(colors: [Color(0xFFFFD700), Color(0xFFFFA500)]), boxShadow: [BoxShadow(color: const Color(0xFFFFD700).withValues(alpha: 0.4), blurRadius: 20, spreadRadius: 3)]),
          padding: const EdgeInsets.all(2),
          child: Container(
            padding: const EdgeInsets.all(20), decoration: BoxDecoration(color: koyuArkaplan, borderRadius: BorderRadius.circular(18)),
            child: Column(children: [
              Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4), decoration: BoxDecoration(color: const Color(0xFFFFD700).withValues(alpha: 0.2), borderRadius: BorderRadius.circular(8)), child: Text(t('most_preferred'), style: const TextStyle(color: Color(0xFFFFD700), fontSize: 10, fontWeight: FontWeight.bold)))]),
              const SizedBox(height: 16),
              Row(children: [
                Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: const Color(0xFFFFD700).withValues(alpha: 0.1), shape: BoxShape.circle), child: const Icon(Icons.all_inclusive, color: Color(0xFFFFD700), size: 32)),
                const SizedBox(width: 16),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(paket.name, style: TextStyle(color: yaziRengi(), fontSize: 20, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  ...paket.description.split(',').map((d) => Text(d.trim(), style: TextStyle(color: ikinciYaziRengi(), fontSize: 12))),
                ])),
                Text('${paket.price} ₺', style: premiumNumberStyle.copyWith(color: const Color(0xFFFFD700), fontSize: 20)),
              ]),
            ]),
          ),
        ),
      ),
    );
  }
}

// ── SSS SAYFASI (Madde 3) ──
class SSSSayfasi extends StatelessWidget {
  const SSSSayfasi({super.key});

  @override
  Widget build(BuildContext context) {
    final Color anaRenk = const Color(0xFF257bf4);
    final Color koyuArkaplan = arkaplanRengi();
    final Color koyuYuzey = yuzeyRengi();

    final sssListesi = [
      {'q': t('faq_1_q'), 'a': t('faq_1_a'), 'icon': Icons.credit_card},
      {'q': t('faq_2_q'), 'a': t('faq_2_a'), 'icon': Icons.timer},
      {'q': t('faq_3_q'), 'a': t('faq_3_a'), 'icon': Icons.view_in_ar},
      {'q': t('faq_4_q'), 'a': t('faq_4_a'), 'icon': Icons.warning_amber},
      {'q': t('faq_5_q'), 'a': t('faq_5_a'), 'icon': Icons.high_quality},
      {'q': t('faq_6_q'), 'a': t('faq_6_a'), 'icon': Icons.delete_forever},
      {'q': t('faq_7_q'), 'a': t('faq_7_a'), 'icon': Icons.group},
      {'q': t('faq_8_q'), 'a': t('faq_8_a'), 'icon': Icons.contact_mail},
    ];

    return Scaffold(
      backgroundColor: koyuArkaplan,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(icon: Icon(Icons.arrow_back, color: yaziRengi()), onPressed: () => Navigator.pop(context)),
        title: Text(t('faq_title'), style: TextStyle(color: yaziRengi(), fontSize: 18, fontWeight: FontWeight.bold)),
        centerTitle: true,
      ),
      body: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: sssListesi.length,
        itemBuilder: (context, index) {
          final item = sssListesi[index];
          return Container(
            margin: const EdgeInsets.only(bottom: 12),
            decoration: BoxDecoration(
              color: koyuYuzey,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: kartBorderRengi()),
            ),
            child: Theme(
              data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
              child: ExpansionTile(
                leading: Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(color: anaRenk.withValues(alpha: 0.1), shape: BoxShape.circle),
                  child: Icon(item['icon'] as IconData, color: anaRenk, size: 22),
                ),
                title: Text(item['q'] as String, style: TextStyle(color: yaziRengi(), fontSize: 14, fontWeight: FontWeight.w600)),
                iconColor: Colors.grey,
                collapsedIconColor: Colors.grey,
                childrenPadding: const EdgeInsets.only(left: 16, right: 16, bottom: 16),
                children: [
                  Text(item['a'] as String, style: TextStyle(color: ikinciYaziRengi(), fontSize: 13, height: 1.6)),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}