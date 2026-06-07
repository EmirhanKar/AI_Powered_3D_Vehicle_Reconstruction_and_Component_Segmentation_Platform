import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:model_viewer_plus/model_viewer_plus.dart';
import '../sistem_ve_dil.dart';
import '../config.dart';

class Model3DViewer extends StatefulWidget {
  final String modelUrl;   // Backend'den gelen model_url
  final String carName;
  final String? thumbnailUrl;

  const Model3DViewer({
    super.key,
    required this.modelUrl,
    required this.carName,
    this.thumbnailUrl,
  });

  @override
  State<Model3DViewer> createState() => _Model3DViewerState();
}

class _Model3DViewerState extends State<Model3DViewer>
    with SingleTickerProviderStateMixin {
  bool _isLoading = true;
  bool _autoRotate = true;
  late AnimationController _fadeController;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    _fadeAnimation = CurvedAnimation(
      parent: _fadeController,
      curve: Curves.easeOut,
    );

    // Model yüklendikten sonra fade-in
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) {
        setState(() => _isLoading = false);
        _fadeController.forward();
      }
    });
  }

  @override
  void dispose() {
    SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
    _fadeController.dispose();
    super.dispose();
  }

  String get _fullModelUrl {
    final url = widget.modelUrl.replaceAll('\\', '/');
    if (url.startsWith('http')) return url;
    final clean = url.startsWith('/') ? url.substring(1) : url;
    return '${AppConfig.baseUrl}/$clean';
  }

  @override
  Widget build(BuildContext context) {
    final anaRenk = const Color(0xFF257bf4);

    return Scaffold(
      backgroundColor: const Color(0xFF0A0A0F),
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.black.withOpacity(0.4),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.white12),
            ),
            child: const Icon(Icons.arrow_back_ios_new, color: Colors.white, size: 18),
          ),
          onPressed: () => Navigator.pop(context),
        ),
        title: Column(
          children: [
            Text(
              widget.carName,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.bold,
                letterSpacing: 0.5,
              ),
            ),
            const Text(
              '3D Model',
              style: TextStyle(
                color: Colors.white54,
                fontSize: 11,
                fontWeight: FontWeight.w400,
              ),
            ),
          ],
        ),
        centerTitle: true,
        actions: [
          IconButton(
            icon: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.black.withOpacity(0.4),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white12),
              ),
              child: const Icon(Icons.fullscreen, color: Colors.white, size: 18),
            ),
            onPressed: () {
              SystemChrome.setPreferredOrientations([
                DeviceOrientation.landscapeLeft,
                DeviceOrientation.landscapeRight,
              ]);
              // Geri dönüşte dikey moda al
              Future.delayed(const Duration(seconds: 1), () {
                if (mounted) {
                  // Kullanıcı geri dönene kadar landscape kalır
                }
              });
            },
          ),
        ],
      ),
      body: Stack(
        children: [
          // ── Arka Plan Gradient ──
          Container(
            decoration: const BoxDecoration(
              gradient: RadialGradient(
                center: Alignment(0, -0.3),
                radius: 1.2,
                colors: [
                  Color(0xFF1A1A2E),
                  Color(0xFF0A0A0F),
                ],
              ),
            ),
          ),

          // ── Grid Zemin Efekti ──
          Positioned.fill(
            child: CustomPaint(
              painter: _GridPainter(color: anaRenk.withOpacity(0.04)),
            ),
          ),

          // ── 3D Model Viewer ──
          Positioned.fill(
            child: ModelViewer(
              src: _fullModelUrl,
              alt: '${widget.carName} 3D Model',
              autoRotate: _autoRotate,
              autoRotateDelay: 0,
              rotationPerSecond: '18deg',
              cameraControls: true,
              disableZoom: false,
              backgroundColor: Colors.transparent,
              fieldOfView: '30deg',
              minFieldOfView: '20deg',
              maxFieldOfView: '50deg',
              shadowIntensity: 1,
              shadowSoftness: 0.8,
              exposure: 1.0,
              environmentImage: 'neutral',
              interactionPrompt: InteractionPrompt.auto,
              interactionPromptThreshold: 500,
            ),
          ),

          // ── Yükleniyor Overlay ──
          if (_isLoading)
            Container(
              color: const Color(0xFF0A0A0F),
              child: Stack(
                children: [
                  Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Pulsing logo / ring
                        SizedBox(
                          width: 80,
                          height: 80,
                          child: Stack(
                            alignment: Alignment.center,
                            children: [
                              SizedBox(
                                width: 80,
                                height: 80,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: anaRenk.withOpacity(0.6),
                                ),
                              ),
                              Icon(Icons.view_in_ar, color: anaRenk, size: 32),
                            ],
                          ),
                        ),
                        const SizedBox(height: 24),
                        Text(
                          '3D Model Yükleniyor...',
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.8),
                            fontSize: 16,
                            fontWeight: FontWeight.w500,
                            letterSpacing: 0.5,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Modeli döndürmek için sürükleyin',
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.3),
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Positioned(
                    left: 20,
                    right: 20,
                    bottom: 40,
                    child: Center(
                      child: SelectableText(
                        'URL: $_fullModelUrl',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.4),
                          fontSize: 10,
                          fontFamily: 'monospace',
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),

          // ── Alt Kontrol Barı ──
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: Container(
              padding: EdgeInsets.only(
                left: 20,
                right: 20,
                bottom: MediaQuery.of(context).padding.bottom + 16,
                top: 16,
              ),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    Colors.transparent,
                    Colors.black.withOpacity(0.8),
                    Colors.black.withOpacity(0.95),
                  ],
                ),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  _buildControlButton(
                    icon: _autoRotate ? Icons.pause : Icons.play_arrow,
                    label: _autoRotate ? 'Durdur' : 'Döndür',
                    color: anaRenk,
                    onTap: () {
                      if (titresimAcik.value) HapticFeedback.lightImpact();
                      setState(() => _autoRotate = !_autoRotate);
                    },
                  ),
                  _buildControlButton(
                    icon: Icons.share,
                    label: 'Paylaş',
                    color: Colors.green,
                    onTap: () {
                      if (titresimAcik.value) HapticFeedback.lightImpact();
                      // Paylaşma
                    },
                  ),
                  _buildControlButton(
                    icon: Icons.screen_rotation,
                    label: 'Tam Ekran',
                    color: Colors.orange,
                    onTap: () {
                      if (titresimAcik.value) HapticFeedback.mediumImpact();
                      final isLandscape = MediaQuery.of(context).orientation == Orientation.landscape;
                      if (isLandscape) {
                        SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
                      } else {
                        SystemChrome.setPreferredOrientations([
                          DeviceOrientation.landscapeLeft,
                          DeviceOrientation.landscapeRight,
                        ]);
                      }
                    },
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildControlButton({
    required IconData icon,
    required String label,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: color.withOpacity(0.25), width: 1),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color, size: 22),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                color: color.withOpacity(0.9),
                fontSize: 10,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Grid Zemin Çizici ──
class _GridPainter extends CustomPainter {
  final Color color;

  _GridPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 0.5;

    const spacing = 40.0;
    // Yatay çizgiler (alt yarı)
    for (double y = size.height * 0.6; y < size.height; y += spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
    // Dikey çizgiler (alt yarı)
    for (double x = 0; x < size.width; x += spacing) {
      canvas.drawLine(
        Offset(x, size.height * 0.6),
        Offset(x, size.height),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
