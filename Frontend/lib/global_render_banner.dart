import 'package:flutter/material.dart';
import 'render_state.dart';
import 'sayfalar_islem.dart';
import 'main.dart';

/// Uygulama genelinde gösterilen render ilerleme banner'ı.
/// Kullanıcı render sayfasından çıksa bile, arka planda devam eden
/// render işleminin durumunu küçük bir yüzen kart ile gösterir.
class GlobalRenderBanner extends StatefulWidget {
  const GlobalRenderBanner({super.key});

  @override
  State<GlobalRenderBanner> createState() => _GlobalRenderBannerState();
}

class _GlobalRenderBannerState extends State<GlobalRenderBanner>
    with SingleTickerProviderStateMixin {
  final _yonetici = RenderDurumYonetici();
  late AnimationController _animController;
  late Animation<Offset> _slideAnim;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 350),
    );
    _slideAnim = Tween<Offset>(
      begin: const Offset(0, -1),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _animController,
      curve: Curves.easeOutCubic,
    ));
    _yonetici.addListener(_durumDegisti);
  }

  void _durumDegisti() {
    if (!mounted) return;
    if (_yonetici.bannerGoster) {
      _animController.forward();
    } else {
      _animController.reverse();
    }
    setState(() {});
  }

  @override
  void dispose() {
    _yonetici.removeListener(_durumDegisti);
    _animController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!_yonetici.aktifMi || _yonetici.renderSayfasiAcik) {
      return const SizedBox.shrink();
    }

    final ilerlemeYuzde = (_yonetici.ilerleme * 100).toInt();
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Positioned(
      top: MediaQuery.of(context).padding.top + 8,
      left: 16,
      right: 16,
      child: SlideTransition(
        position: _slideAnim,
        child: Material(
          elevation: 8,
          borderRadius: BorderRadius.circular(16),
          color: isDark ? const Color(0xFF1A2636) : Colors.white,
          shadowColor: Colors.black26,
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: () {
              // Banner'a tıklanınca render sayfasına geri dön
              if (_yonetici.scanId != null) {
                navigatorKey.currentState?.push(
                  MaterialPageRoute(
                    builder: (context) => ModifiyeSecimSayfasi(
                      scanId: _yonetici.scanId,
                      carName: _yonetici.arabaAdi,
                      method: _yonetici.method,
                    ),
                  ),
                );
              }
            },
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                children: [
                  // Dönen animasyon ikonu
                  SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                      value: _yonetici.ilerleme,
                      strokeWidth: 3,
                      backgroundColor: isDark
                          ? Colors.white12
                          : Colors.grey.shade200,
                      valueColor: const AlwaysStoppedAnimation<Color>(
                        Color(0xFF257bf4),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  // Metin bilgisi
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          _yonetici.arabaAdi.isNotEmpty
                              ? '${_yonetici.arabaAdi} işleniyor…'
                              : 'Render işleniyor…',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: isDark ? Colors.white : Colors.black87,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${_yonetici.method.toUpperCase()} • %$ilerlemeYuzde',
                          style: TextStyle(
                            fontSize: 11,
                            color: isDark
                                ? Colors.white54
                                : Colors.grey.shade600,
                          ),
                        ),
                      ],
                    ),
                  ),
                  // İlerleme yüzde rozeti
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: const Color(0xFF257bf4).withOpacity(0.15),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      '%$ilerlemeYuzde',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF257bf4),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
