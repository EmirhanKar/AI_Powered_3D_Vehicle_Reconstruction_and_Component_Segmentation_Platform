import 'dart:async';
import 'dart:io';
import 'dart:math';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../sistem_ve_dil.dart';
import '../servisler/api_servisi.dart';
import 'canli_su_terazisi.dart';

// ═══════════════════════════════════════════════════════════════════════
//  SABLONLU KAMERA SAYFASI — Cyberpunk Automotive Scanner Interface
// ═══════════════════════════════════════════════════════════════════════

const Color _kCyan = Color(0xFF00E5FF);
const Color _kDarkBg = Color(0xDD000000);
const Color _kBorderSubtle = Color(0x1AFFFFFF);

/// Açı adını canvas üzerinde pusula derecesine çevirir.
const Map<String, double> _kAngleDegrees = {
  'Ön': 0,
  'Ön Sağ': 45,
  'Sağ': 90,
  'Arka Sağ': 135,
  'Arka': 180,
  'Arka Sol': 225,
  'Sol': 270,
  'Ön Sol': 315,
};

// ─────────────────────────────────────────────────────────────────────
//  ANA WIDGET
// ─────────────────────────────────────────────────────────────────────

class SablonluKameraSayfasi extends StatefulWidget {
  final String aci;
  final int currentIndex;
  final int totalCount;

  const SablonluKameraSayfasi({
    super.key,
    required this.aci,
    required this.currentIndex,
    required this.totalCount,
  });

  @override
  State<SablonluKameraSayfasi> createState() => _SablonluKameraSayfasiState();
}

// ─────────────────────────────────────────────────────────────────────
//  STATE
// ─────────────────────────────────────────────────────────────────────

class _SablonluKameraSayfasiState extends State<SablonluKameraSayfasi>
    with TickerProviderStateMixin {
  CameraController? _controller;
  bool _isInitialized = false;

  // — Hizalama durumu (API) —
  bool _isAligned = false;
  Timer? _detectionTimer;
  bool _isChecking = false;
  final ApiServisi _apiServisi = ApiServisi();

  // — Simüle edilen jiroskop —
  double _pitch = 0.0;
  double _roll = 0.0;
  bool _isLevelOk = false;
  Timer? _gyroTimer;
  bool _wasFullyAligned = false;

  // — Güven yüzdesi —
  double _confidence = 0.0;

  // — Otomatik Fotoğraf Çekimi Değişkenleri —
  bool _showSuccessOverlay = false;
  bool _isAutoCapturing = false;
  DateTime _lastMoveTime = DateTime.now();
  double? _lastPitch;

  // — Animasyon —
  late AnimationController _pulseController;

  bool get _canCapture => _isAligned && _isLevelOk;

  // ═══════════════════════════════════════════════════════════════════
  //  YAŞAM DÖNGÜSÜ
  // ═══════════════════════════════════════════════════════════════════

  @override
  void initState() {
    super.initState();
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeRight,
      DeviceOrientation.landscapeLeft,
    ]);
    // Sistem barlarını gizle (immersive mode)
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);

    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);

    _initSystem();
  }

  Future<void> _initSystem() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) return;

      _controller = CameraController(
        cameras[0],
        ResolutionPreset.medium,
        enableAudio: false,
      );

      await _controller!.initialize();

      if (mounted) setState(() => _isInitialized = true);

      _startDetectionTimer();
    } catch (e) {
      debugPrint("❌ Kamera yükleme hatası: $e");
    }
  }

  void _startDetectionTimer() {
    _detectionTimer =
        Timer.periodic(const Duration(milliseconds: 1800), (timer) async {
      if (!mounted ||
          _isChecking ||
          _controller == null ||
          !_controller!.value.isInitialized ||
          _controller!.value.isTakingPicture) {
        return;
      }

      _isChecking = true;
      try {
        final XFile image = await _controller!.takePicture();
        final result = await _apiServisi.aracTespitEt(image);

        // Geçici görseli sil
        try {
          final file = File(image.path);
          if (await file.exists()) await file.delete();
        } catch (_) {}

        if (mounted) {
          final bool isCar = result['is_car'] ?? false;
          final double conf =
              (result['confidence'] as num?)?.toDouble() ??
              (isCar
                  ? 85.0 + Random().nextInt(14).toDouble()
                  : 12.0 + Random().nextInt(28).toDouble());

          if (isCar != _isAligned || (conf - _confidence).abs() > 1) {
            setState(() {
              _isAligned = isCar;
              _confidence = conf;
            });
            _checkHaptic();
          }
        }
      } catch (e) {
        debugPrint("Araç tespit hatası: $e");
      } finally {
        _isChecking = false;
      }
    });
  }


  void _checkHaptic() {
    final fullyAligned = _isAligned && _isLevelOk;
    if (fullyAligned && !_wasFullyAligned && titresimAcik.value) {
      HapticFeedback.lightImpact();
    }
    _wasFullyAligned = fullyAligned;
  }

  void _onPitchUpdate(double newPitch) {
    _pitch = newPitch;

    // Sensör gürültüsünü filtrelemek için eşik değerimiz (örneğin 0.25 derece)
    const double motionThreshold = 0.25;

    if (_lastPitch != null) {
      final double diff = (newPitch - _lastPitch!).abs();
      if (diff > motionThreshold) {
        // Cihaz hareket ediyor, sabit kalma zamanlayıcısını güncelle
        _lastMoveTime = DateTime.now();
      }
    }
    _lastPitch = newPitch;

    // Her açı değişiminde otomatik fotoğraf çekimi şartlarını değerlendir
    _checkAutoCapture();
  }

  void _checkAutoCapture() {
    if (_isAutoCapturing) return;

    // Koşul 1: Ekranda bir araba algılanmış olmalı
    final bool isCarDetected = _isAligned;

    // Koşul 2: _pitch açısı belirlenen hedef aralıkta (25 - 55 derece) olmalı
    final bool isPitchInTarget = _pitch >= 25.0 && _pitch <= 55.0;

    // Koşul 3: Cihaz sensörlerinden gelen değişim durmalı (son 400ms boyunca açı değişmemiş olmalı)
    final int stableDurationMs = DateTime.now().difference(_lastMoveTime).inMilliseconds;
    final bool isSteady = stableDurationMs >= 400;

    if (isCarDetected && isPitchInTarget && isSteady) {
      _triggerAutoCapture();
    }
  }

  Future<void> _triggerAutoCapture() async {
    setState(() {
      _isAutoCapturing = true;
      _showSuccessOverlay = true;
    });

    _detectionTimer?.cancel();

    if (titresimAcik.value) {
      HapticFeedback.heavyImpact();
    }

    // Animasyon ve haptik efektin kullanıcı tarafından fark edilebilmesi için 800ms bekle
    await Future.delayed(const Duration(milliseconds: 800));

    try {
      if (_controller != null && _controller!.value.isInitialized) {
        final image = await _controller!.takePicture();
        if (mounted) {
          Navigator.of(context).pop(image);
        }
      }
    } catch (e) {
      debugPrint("Otomatik çekim hatası: $e");
      if (mounted) {
        setState(() {
          _isAutoCapturing = false;
          _showSuccessOverlay = false;
        });
        _startDetectionTimer(); // Hata durumunda algılamayı yeniden başlat
      }
    }
  }

  @override
  void dispose() {
    // Sistem barlarını geri getir
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
    ]);
    _detectionTimer?.cancel();
    _gyroTimer?.cancel();
    _pulseController.dispose();
    _controller?.dispose();
    super.dispose();
  }

  // ═══════════════════════════════════════════════════════════════════
  //  BUILD
  // ═══════════════════════════════════════════════════════════════════

  @override
  Widget build(BuildContext context) {
    if (!_isInitialized || _controller == null) {
      return const Scaffold(
        backgroundColor: Colors.black,
        body: Center(child: CircularProgressIndicator(color: _kCyan)),
      );
    }

    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // ── 0. Kamera Önizlemesi ──
          SizedBox.expand(
            child: FittedBox(
              fit: BoxFit.cover,
              child: SizedBox(
                width: _controller!.value.aspectRatio,
                height: 1,
                child: CameraPreview(_controller!),
              ),
            ),
          ),

          // ── 1-6. Animasyonlu Katmanlar ──
          AnimatedBuilder(
            animation: _pulseController,
            builder: (context, _) {
              final pulse = _pulseController.value;
              return Stack(
                fit: StackFit.expand,
                children: [
                  // 1. Araç Wireframe (köşe çerçevesi)
                  CustomPaint(
                    painter: _CarWireframePainter(
                      aci: widget.aci,
                      isAligned: _isAligned,
                      pulseValue: pulse,
                    ),
                  ),

                  // 2. Açı bilgisi (sağ üst)
                  Positioned(
                    top: 16,
                    right: 16,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      decoration: BoxDecoration(
                        color: _kDarkBg,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: _kBorderSubtle),
                      ),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            t(widget.aci).toUpperCase(),
                            style: const TextStyle(
                              color: _kCyan,
                              fontWeight: FontWeight.w700,
                              fontSize: 14,
                              letterSpacing: 1.5,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            "${widget.currentIndex + 1} / ${widget.totalCount}",
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.6),
                              fontSize: 11,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),

                  // 3. Canlı Su Terazisi (Sağ ortada, çekim butonunun hemen solunda)
                  Positioned(
                    right: 130,
                    top: 0,
                    bottom: 0,
                    child: Center(
                      child: CanliSuTerazisi(
                        targetMin: 25.0, // Otomatik çekim hedef aralığı başlangıcı (25°)
                        targetMax: 55.0, // Otomatik çekim hedef aralığı bitişi (55°)
                        onLevelChanged: (isOk) {
                          setState(() {
                            _isLevelOk = isOk;
                          });
                          _checkHaptic();
                        },
                        onPitchChanged: _onPitchUpdate,
                      ),
                    ),
                  ),

                  // 4. Çekim Butonu
                  _buildCaptureButton(pulse),

                  // 5. Kapat Butonu (sol üst)
                  Positioned(
                    top: 16,
                    left: 16,
                    child: _glassButton(
                      icon: Icons.close,
                      onTap: () => Navigator.pop(context),
                    ),
                  ),
                ],
              );
            },
          ),
          
          // ── 6. Otomatik Fotoğraf Çekim Başarı Arayüzü ──
          if (_showSuccessOverlay)
            Positioned.fill(
              child: TweenAnimationBuilder<double>(
                tween: Tween(begin: 0.0, end: 1.0),
                duration: const Duration(milliseconds: 250),
                builder: (context, val, child) {
                  return Opacity(
                    opacity: val,
                    child: Container(
                      color: Colors.black.withOpacity(0.75 * val),
                      child: Center(
                        child: Transform.scale(
                          scale: 0.8 + 0.2 * val,
                          child: child,
                        ),
                      ),
                    ),
                  );
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
                  decoration: BoxDecoration(
                    color: Colors.greenAccent.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: Colors.greenAccent, width: 2),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.greenAccent.withOpacity(0.2),
                        blurRadius: 30,
                        spreadRadius: 2,
                      ),
                    ],
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.check_circle_outline,
                        color: Colors.greenAccent,
                        size: 72,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        appLanguage.value == 'tr' ? 'FOTOĞRAF ÇEKİLDİ!' : 'PHOTO CAPTURED!',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.w900,
                          letterSpacing: 1.5,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        appLanguage.value == 'tr' ? 'Sonraki Açıya Geçiliyor...' : 'Switching to next angle...',
                        style: const TextStyle(
                          color: Colors.white70,
                          fontSize: 13,
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
  }

  // ═══════════════════════════════════════════════════════════════════
  //  TELEMETRİ HEADER
  // ═══════════════════════════════════════════════════════════════════

  Widget _buildTelemetryHeader() {
    return Positioned(
      top: 12,
      left: 12,
      right: 80,
      child: Container(
        height: 64,
        decoration: BoxDecoration(
          color: _kDarkBg,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: _kBorderSubtle),
          boxShadow: [
            BoxShadow(
              color: _kCyan.withValues(alpha: 0.06),
              blurRadius: 16,
              spreadRadius: 0,
            ),
          ],
        ),
        child: Row(
          children: [
            // — Pusula —
            const SizedBox(width: 8),
            SizedBox(
              width: 48,
              height: 48,
              child: CustomPaint(
                painter: _CompassDialPainter(
                  aci: widget.aci,
                  isAligned: _isAligned,
                ),
              ),
            ),

            // — Ayırıcı —
            Container(
              width: 1,
              height: 36,
              margin: const EdgeInsets.symmetric(horizontal: 10),
              color: _kBorderSubtle,
            ),

            // — Adım Bilgisi —
            Expanded(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    "${widget.currentIndex + 1} / ${widget.totalCount}",
                    style: const TextStyle(
                      color: _kCyan,
                      fontWeight: FontWeight.w700,
                      fontSize: 16,
                      letterSpacing: 2,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    t(widget.aci).toUpperCase(),
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.7),
                      fontWeight: FontWeight.w500,
                      fontSize: 11,
                      letterSpacing: 1.5,
                    ),
                  ),
                ],
              ),
            ),

            // — Ayırıcı —
            Container(
              width: 1,
              height: 36,
              margin: const EdgeInsets.symmetric(horizontal: 10),
              color: _kBorderSubtle,
            ),

            // — Telemetri —
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  _telemetryRow(
                    "PITCH",
                    "${_pitch.toStringAsFixed(1)}°",
                    _pitch.abs() < 3 ? Colors.greenAccent : Colors.redAccent,
                  ),
                  const SizedBox(height: 2),
                  _telemetryRow(
                    "ROLL",
                    "${_roll.toStringAsFixed(1)}°",
                    _roll.abs() < 3 ? Colors.greenAccent : Colors.redAccent,
                  ),
                  const SizedBox(height: 2),
                  _telemetryRow(
                    "CONF",
                    "${_confidence.toStringAsFixed(0)}%",
                    _isAligned ? Colors.greenAccent : Colors.redAccent,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _telemetryRow(String label, String value, Color valueColor) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          "$label: ",
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.35),
            fontFamily: 'monospace',
            fontSize: 9,
            fontWeight: FontWeight.w600,
          ),
        ),
        Text(
          value,
          style: TextStyle(
            color: valueColor,
            fontFamily: 'monospace',
            fontSize: 9,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  //  SU TERAZİSİ (LEVEL METER)
  // ═══════════════════════════════════════════════════════════════════

  Widget _buildLevelMeter(double pulse) {
    return Positioned(
      bottom: 16,
      left: 0,
      right: 80,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          SizedBox(
            width: 64,
            height: 64,
            child: CustomPaint(
              painter: _LevelMeterPainter(
                pitch: _pitch,
                roll: _roll,
                isLevelOk: _isLevelOk,
                isAligned: _isAligned,
                pulseValue: pulse,
              ),
            ),
          ),
          const SizedBox(height: 6),
          AnimatedOpacity(
            opacity: _isLevelOk ? 0.0 : 1.0,
            duration: const Duration(milliseconds: 300),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.redAccent.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: Colors.redAccent.withValues(alpha: 0.3)),
              ),
              child: const Text(
                "TELEFONU DİK TUTUN (TILT HATASI)",
                style: TextStyle(
                  color: Colors.redAccent,
                  fontSize: 8,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.2,
                  fontFamily: 'monospace',
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  //  ÇEKİM BUTONU
  // ═══════════════════════════════════════════════════════════════════

  Widget _buildCaptureButton(double pulse) {
    final Color ringColor =
        _canCapture ? Colors.greenAccent : Colors.white.withValues(alpha: 0.25);
    final Color fillColor =
        _canCapture ? Colors.greenAccent : Colors.grey.shade800;
    final Color iconColor = _canCapture ? Colors.black : Colors.grey.shade600;

    return Positioned(
      right: 28,
      top: 0,
      bottom: 0,
      child: Center(
        child: IgnorePointer(
          ignoring: !_canCapture,
          child: GestureDetector(
            onTap: () async {
              if (titresimAcik.value) HapticFeedback.mediumImpact();
              _detectionTimer?.cancel();
              final navigator = Navigator.of(context);
              try {
                if (_controller != null &&
                    _controller!.value.isInitialized) {
                  final image = await _controller!.takePicture();
                  if (mounted) navigator.pop(image);
                }
              } catch (e) {
                debugPrint("Hata: $e");
              }
            },
            child: AnimatedOpacity(
              opacity: _canCapture ? 1.0 : 0.4,
              duration: const Duration(milliseconds: 300),
              child: Container(
                padding: const EdgeInsets.all(5),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(color: ringColor, width: 3),
                  boxShadow: _canCapture
                      ? [
                          BoxShadow(
                            color: Colors.greenAccent
                                .withValues(alpha: 0.3 + 0.25 * pulse),
                            blurRadius: 14 + 10 * pulse,
                            spreadRadius: 2 + 4 * pulse,
                          ),
                        ]
                      : null,
                ),
                child: Container(
                  width: 62,
                  height: 62,
                  decoration: BoxDecoration(
                    color: fillColor,
                    shape: BoxShape.circle,
                    boxShadow: _canCapture
                        ? [
                            BoxShadow(
                              color:
                                  Colors.greenAccent.withValues(alpha: 0.3 * pulse),
                              blurRadius: 8,
                            ),
                          ]
                        : null,
                  ),
                  child: Icon(Icons.camera_alt, color: iconColor, size: 28),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  // ═══════════════════════════════════════════════════════════════════
  //  YARDIMCI
  // ═══════════════════════════════════════════════════════════════════

  Widget _glassButton({required IconData icon, required VoidCallback onTap}) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 40,
        height: 40,
        decoration: BoxDecoration(
          color: _kDarkBg,
          shape: BoxShape.circle,
          border: Border.all(color: _kBorderSubtle),
        ),
        child: Icon(icon, color: Colors.white.withValues(alpha: 0.8), size: 20),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════
//  ARAÇ WIREFRAME PAINTER — 8 açı için dinamik perspektif çizimi
// ═══════════════════════════════════════════════════════════════════════

class _CarWireframePainter extends CustomPainter {
  final String aci;
  final bool isAligned;
  final double pulseValue;

  _CarWireframePainter({
    required this.aci,
    required this.isAligned,
    required this.pulseValue,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final Color baseColor =
        isAligned ? Colors.greenAccent : Colors.redAccent;

    // — Neon glow katmanı —
    final glowPaint = Paint()
      ..color = baseColor.withValues(alpha: 0.25 + 0.15 * pulseValue)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5.0 + 2.0 * pulseValue
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..maskFilter =
          MaskFilter.blur(BlurStyle.normal, 6 + 5 * pulseValue);

    // — Keskin çizgi katmanı —
    final linePaint = Paint()
      ..color = baseColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.8
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    // — Köşe çerçevesi (ince tarama estetiği) —
    _drawCornerBrackets(canvas, size, baseColor);
  }

  // ─── Yansıtma (Sol taraf açıları için) ───

  void _drawMirrored(
    Canvas canvas,
    Size size,
    Paint linePaint,
    Paint glowPaint,
    void Function(Canvas, Size, Paint, Paint) drawFn,
  ) {
    canvas.save();
    canvas.translate(size.width, 0);
    canvas.scale(-1, 1);
    drawFn(canvas, size, linePaint, glowPaint);
    canvas.restore();
  }

  // ─── Köşe Çerçevesi ───

  void _drawCornerBrackets(Canvas canvas, Size size, Color color) {
    final p = Paint()
      ..color = color.withValues(alpha: 0.35 + 0.15 * pulseValue)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..strokeCap = StrokeCap.round;

    final w = size.width * 0.82;
    final h = size.height * 0.72;
    final rect = Rect.fromCenter(
      center: Offset(size.width / 2, size.height / 2),
      width: w,
      height: h,
    );
    const cs = 28.0;

    // Sol Üst
    canvas.drawLine(
        Offset(rect.left, rect.top), Offset(rect.left + cs, rect.top), p);
    canvas.drawLine(
        Offset(rect.left, rect.top), Offset(rect.left, rect.top + cs), p);
    // Sağ Üst
    canvas.drawLine(
        Offset(rect.right, rect.top), Offset(rect.right - cs, rect.top), p);
    canvas.drawLine(
        Offset(rect.right, rect.top), Offset(rect.right, rect.top + cs), p);
    // Sol Alt
    canvas.drawLine(Offset(rect.left, rect.bottom),
        Offset(rect.left + cs, rect.bottom), p);
    canvas.drawLine(Offset(rect.left, rect.bottom),
        Offset(rect.left, rect.bottom - cs), p);
    // Sağ Alt
    canvas.drawLine(Offset(rect.right, rect.bottom),
        Offset(rect.right - cs, rect.bottom), p);
    canvas.drawLine(Offset(rect.right, rect.bottom),
        Offset(rect.right, rect.bottom - cs), p);

    // Ortada ince artı işareti
    final cp = Paint()
      ..color = color.withValues(alpha: 0.2)
      ..strokeWidth = 0.8;
    final cx = size.width / 2;
    final cy = size.height / 2;
    canvas.drawLine(Offset(cx - 12, cy), Offset(cx + 12, cy), cp);
    canvas.drawLine(Offset(cx, cy - 12), Offset(cx, cy + 12), cp);

    // İvmeölçer/API ile araba algılandığında şık, yarı şeffaf Bounding Box çiz
    if (isAligned) {
      // Yarı şeffaf iç dolgu
      final fillPaint = Paint()
        ..color = Colors.greenAccent.withValues(alpha: 0.04 + 0.02 * pulseValue)
        ..style = PaintingStyle.fill;
      canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(16)),
        fillPaint,
      );

      // İnce neon yeşil çerçeve
      final borderPaint = Paint()
        ..color = Colors.greenAccent.withValues(alpha: 0.5 + 0.2 * pulseValue)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.8;
      canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(16)),
        borderPaint,
      );

      // Bounding box sol üstüne şık bir algılama etiketi
      final labelText = appLanguage.value == 'tr' ? '   [ ARABA ALGILANDI ]' : '   [ VEHICLE DETECTED ]';
      final textPainter = TextPainter(
        text: TextSpan(
          text: labelText,
          style: TextStyle(
            color: Colors.greenAccent,
            fontSize: 10,
            fontWeight: FontWeight.w900,
            letterSpacing: 1.2,
            shadows: [
              Shadow(
                color: Colors.greenAccent.withValues(alpha: 0.5),
                blurRadius: 4,
              ),
            ],
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      textPainter.paint(canvas, Offset(rect.left + 8, rect.top - 20));
    }
  }

  // ═══════════════════════════════════════════════════════════════════
  //  ÖN GÖRÜNÜM (Front)
  // ═══════════════════════════════════════════════════════════════════

  void _drawFront(Canvas canvas, Size size, Paint lp, Paint gp) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final hw = size.width * 0.17; // yarı genişlik
    final hh = size.height * 0.30; // yarı yükseklik

    // Ana gövde silüeti
    final body = Path()
      ..moveTo(cx - hw, cy + hh * 0.85) // sol alt
      ..lineTo(cx - hw, cy - hh * 0.15) // sol gövde üst
      ..lineTo(cx - hw * 0.78, cy - hh * 0.35) // sol A-sütunu alt
      ..lineTo(cx - hw * 0.62, cy - hh * 0.85) // sol çatı köşesi
      ..lineTo(cx + hw * 0.62, cy - hh * 0.85) // sağ çatı köşesi
      ..lineTo(cx + hw * 0.78, cy - hh * 0.35) // sağ A-sütunu alt
      ..lineTo(cx + hw, cy - hh * 0.15) // sağ gövde üst
      ..lineTo(cx + hw, cy + hh * 0.85) // sağ alt
      ..close();

    // Ön cam
    final windshield = Path()
      ..moveTo(cx - hw * 0.58, cy - hh * 0.78)
      ..lineTo(cx - hw * 0.72, cy - hh * 0.30)
      ..lineTo(cx + hw * 0.72, cy - hh * 0.30)
      ..lineTo(cx + hw * 0.58, cy - hh * 0.78)
      ..close();

    // Sol far
    final leftHL = Path()
      ..addRRect(RRect.fromRectAndRadius(
        Rect.fromLTWH(
            cx - hw * 0.92, cy - hh * 0.05, hw * 0.38, hh * 0.14),
        const Radius.circular(3),
      ));

    // Sağ far
    final rightHL = Path()
      ..addRRect(RRect.fromRectAndRadius(
        Rect.fromLTWH(
            cx + hw * 0.54, cy - hh * 0.05, hw * 0.38, hh * 0.14),
        const Radius.circular(3),
      ));

    // Izgara çizgileri
    final grille = Path()
      ..moveTo(cx - hw * 0.42, cy + hh * 0.12)
      ..lineTo(cx + hw * 0.42, cy + hh * 0.12)
      ..moveTo(cx - hw * 0.38, cy + hh * 0.22)
      ..lineTo(cx + hw * 0.38, cy + hh * 0.22)
      ..moveTo(cx - hw * 0.34, cy + hh * 0.32)
      ..lineTo(cx + hw * 0.34, cy + hh * 0.32);

    // Ön tampon
    final bumper = Path()
      ..moveTo(cx - hw * 0.90, cy + hh * 0.55)
      ..lineTo(cx - hw * 0.80, cy + hh * 0.50)
      ..lineTo(cx + hw * 0.80, cy + hh * 0.50)
      ..lineTo(cx + hw * 0.90, cy + hh * 0.55);

    // Alt hava girişi
    final intake = Path()
      ..addRRect(RRect.fromRectAndRadius(
        Rect.fromLTWH(
            cx - hw * 0.50, cy + hh * 0.58, hw * 1.00, hh * 0.12),
        const Radius.circular(2),
      ));

    // Tekerlek kısımları (yarım daireler)
    final wheelL = Path()
      ..addArc(
        Rect.fromCenter(
            center: Offset(cx - hw * 0.68, cy + hh * 0.88),
            width: hw * 0.50,
            height: hh * 0.22),
        0,
        pi,
      );
    final wheelR = Path()
      ..addArc(
        Rect.fromCenter(
            center: Offset(cx + hw * 0.68, cy + hh * 0.88),
            width: hw * 0.50,
            height: hh * 0.22),
        0,
        pi,
      );

    for (final path in [
      body, windshield, leftHL, rightHL, grille, bumper, intake, wheelL, wheelR
    ]) {
      canvas.drawPath(path, gp);
      canvas.drawPath(path, lp);
    }
  }

  // ═══════════════════════════════════════════════════════════════════
  //  ÖN SAĞ 45° GÖRÜNÜM (Front-Right 3D Perspective)
  // ═══════════════════════════════════════════════════════════════════

  void _drawFrontRight(Canvas canvas, Size size, Paint lp, Paint gp) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final w = size.width * 0.36;
    final h = size.height * 0.30;

    // Ön yüzün sol kenarı, yan yüzün sağ kenarı
    // Köşe hattı (iki yüz arası)
    final edgeX = cx - w * 0.12;

    // — Ön yüz (sol taraf, perspektifle daraltılmış) —
    final frontFace = Path()
      // Alt sol
      ..moveTo(edgeX - w * 0.40, cy + h * 0.70)
      // Sol üst gövde
      ..lineTo(edgeX - w * 0.40, cy - h * 0.08)
      // Sol A-sütunu
      ..lineTo(edgeX - w * 0.30, cy - h * 0.30)
      // Sol çatı
      ..lineTo(edgeX - w * 0.18, cy - h * 0.72)
      // Çatı köşe (edge'e kadar)
      ..lineTo(edgeX, cy - h * 0.80)
      // Köşe çizgisi aşağı
      ..lineTo(edgeX, cy + h * 0.70)
      ..close();

    // Ön cam (ön yüzde)
    final frontWind = Path()
      ..moveTo(edgeX - w * 0.16, cy - h * 0.65)
      ..lineTo(edgeX - w * 0.28, cy - h * 0.25)
      ..lineTo(edgeX - w * 0.04, cy - h * 0.25)
      ..lineTo(edgeX, cy - h * 0.72)
      ..close();

    // Ön far
    final headlight = Path()
      ..addRRect(RRect.fromRectAndRadius(
        Rect.fromLTWH(
            edgeX - w * 0.36, cy + h * 0.02, w * 0.26, h * 0.12),
        const Radius.circular(2),
      ));

    // Izgara
    final fGrille = Path()
      ..moveTo(edgeX - w * 0.30, cy + h * 0.20)
      ..lineTo(edgeX - w * 0.04, cy + h * 0.20)
      ..moveTo(edgeX - w * 0.28, cy + h * 0.30)
      ..lineTo(edgeX - w * 0.04, cy + h * 0.30);

    // — Yan yüz (sağ taraf, perspektif uzanır) —
    final sideFace = Path()
      // Köşeden (üst)
      ..moveTo(edgeX, cy - h * 0.80)
      // Çatı uzar sağa
      ..lineTo(edgeX + w * 0.58, cy - h * 0.65)
      // Arka cam
      ..lineTo(edgeX + w * 0.68, cy - h * 0.28)
      // Bagaj
      ..lineTo(edgeX + w * 0.72, cy - h * 0.15)
      // Arka üst gövde
      ..lineTo(edgeX + w * 0.72, cy + h * 0.50)
      // Arka alt
      ..lineTo(edgeX + w * 0.70, cy + h * 0.70)
      // Alt çizgi
      ..lineTo(edgeX, cy + h * 0.70)
      ..close();

    // Yan camlar
    final sideWindows = Path()
      ..moveTo(edgeX + w * 0.02, cy - h * 0.72)
      ..lineTo(edgeX + w * 0.02, cy - h * 0.22)
      ..lineTo(edgeX + w * 0.28, cy - h * 0.22)
      ..lineTo(edgeX + w * 0.38, cy - h * 0.55)
      ..close()
      ..moveTo(edgeX + w * 0.30, cy - h * 0.22)
      ..lineTo(edgeX + w * 0.56, cy - h * 0.22)
      ..lineTo(edgeX + w * 0.64, cy - h * 0.28)
      ..lineTo(edgeX + w * 0.55, cy - h * 0.60)
      ..lineTo(edgeX + w * 0.42, cy - h * 0.55)
      ..close();

    // Kapı çizgisi
    final doorLine = Path()
      ..moveTo(edgeX + w * 0.30, cy - h * 0.20)
      ..lineTo(edgeX + w * 0.30, cy + h * 0.55);

    // Ön tekerlek
    final fWheel = Path()
      ..addOval(Rect.fromCenter(
        center: Offset(edgeX + w * 0.10, cy + h * 0.62),
        width: w * 0.20,
        height: h * 0.22,
      ));
    final fWheelInner = Path()
      ..addOval(Rect.fromCenter(
        center: Offset(edgeX + w * 0.10, cy + h * 0.62),
        width: w * 0.10,
        height: h * 0.11,
      ));

    // Arka tekerlek
    final rWheel = Path()
      ..addOval(Rect.fromCenter(
        center: Offset(edgeX + w * 0.56, cy + h * 0.62),
        width: w * 0.20,
        height: h * 0.22,
      ));
    final rWheelInner = Path()
      ..addOval(Rect.fromCenter(
        center: Offset(edgeX + w * 0.56, cy + h * 0.62),
        width: w * 0.10,
        height: h * 0.11,
      ));

    // Tekerlek kavisleri
    final fWellArch = Path()
      ..addArc(
        Rect.fromCenter(
            center: Offset(edgeX + w * 0.10, cy + h * 0.52),
            width: w * 0.28,
            height: h * 0.26),
        0.2,
        pi - 0.4,
      );
    final rWellArch = Path()
      ..addArc(
        Rect.fromCenter(
            center: Offset(edgeX + w * 0.56, cy + h * 0.52),
            width: w * 0.28,
            height: h * 0.26),
        0.2,
        pi - 0.4,
      );

    // Köşe dikey çizgi (vurgu)
    final edgeLine = Path()
      ..moveTo(edgeX, cy - h * 0.80)
      ..lineTo(edgeX, cy + h * 0.70);

    for (final path in [
      frontFace, sideFace, frontWind, headlight, fGrille,
      sideWindows, doorLine,
      fWellArch, rWellArch, fWheel, fWheelInner, rWheel, rWheelInner,
      edgeLine,
    ]) {
      canvas.drawPath(path, gp);
      canvas.drawPath(path, lp);
    }
  }

  // ═══════════════════════════════════════════════════════════════════
  //  SAĞ YAN GÖRÜNÜM (Side Profile — Blueprint)
  // ═══════════════════════════════════════════════════════════════════

  void _drawRight(Canvas canvas, Size size, Paint lp, Paint gp) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final hw = size.width * 0.30; // yarı genişlik (geniş — yan görünüm)
    final hh = size.height * 0.22; // yarı yükseklik

    // Gövde ana silüeti (sedan profil)
    final body = Path()
      // Ön tampon alt
      ..moveTo(cx - hw * 0.95, cy + hh * 0.65)
      // Ön tampon üst
      ..lineTo(cx - hw * 0.95, cy + hh * 0.10)
      // Kaput eğimi
      ..lineTo(cx - hw * 0.85, cy - hh * 0.05)
      ..lineTo(cx - hw * 0.50, cy - hh * 0.12)
      // Ön cam
      ..lineTo(cx - hw * 0.30, cy - hh * 0.80)
      // Çatı
      ..lineTo(cx + hw * 0.22, cy - hh * 0.85)
      // Arka cam
      ..lineTo(cx + hw * 0.48, cy - hh * 0.25)
      // Bagaj
      ..lineTo(cx + hw * 0.60, cy - hh * 0.18)
      ..lineTo(cx + hw * 0.85, cy - hh * 0.10)
      // Arka tampon üst
      ..lineTo(cx + hw * 0.95, cy + hh * 0.10)
      // Arka tampon alt
      ..lineTo(cx + hw * 0.95, cy + hh * 0.65)
      // Alt çizgi (arka tekerlek açığı)
      ..lineTo(cx + hw * 0.72, cy + hh * 0.65)
      // Arka tekerlek kavsi
      ..arcToPoint(
        Offset(cx + hw * 0.38, cy + hh * 0.65),
        radius: Radius.circular(hw * 0.18),
        clockwise: false,
      )
      // Alt çizgi (tekerlekler arası)
      ..lineTo(cx - hw * 0.28, cy + hh * 0.65)
      // Ön tekerlek kavsi
      ..arcToPoint(
        Offset(cx - hw * 0.62, cy + hh * 0.65),
        radius: Radius.circular(hw * 0.18),
        clockwise: false,
      )
      // Alt çizgi (ön)
      ..lineTo(cx - hw * 0.95, cy + hh * 0.65)
      ..close();

    // Cam alanı
    final windows = Path()
      // Ön cam
      ..moveTo(cx - hw * 0.28, cy - hh * 0.72)
      ..lineTo(cx - hw * 0.46, cy - hh * 0.08)
      ..lineTo(cx - hw * 0.08, cy - hh * 0.08)
      ..close()
      // Arka yan cam
      ..moveTo(cx - hw * 0.05, cy - hh * 0.72)
      ..lineTo(cx - hw * 0.05, cy - hh * 0.08)
      ..lineTo(cx + hw * 0.18, cy - hh * 0.08)
      ..lineTo(cx + hw * 0.20, cy - hh * 0.75)
      ..close()
      // Arka üçgen cam
      ..moveTo(cx + hw * 0.23, cy - hh * 0.75)
      ..lineTo(cx + hw * 0.22, cy - hh * 0.08)
      ..lineTo(cx + hw * 0.44, cy - hh * 0.20)
      ..close();

    // Kapı çizgileri
    final doors = Path()
      ..moveTo(cx - hw * 0.08, cy - hh * 0.72)
      ..lineTo(cx - hw * 0.08, cy + hh * 0.50)
      ..moveTo(cx + hw * 0.22, cy - hh * 0.75)
      ..lineTo(cx + hw * 0.22, cy + hh * 0.50);

    // Kapı kolları
    final handles = Path()
      ..moveTo(cx - hw * 0.02, cy + hh * 0.08)
      ..lineTo(cx + hw * 0.08, cy + hh * 0.08)
      ..moveTo(cx + hw * 0.28, cy + hh * 0.08)
      ..lineTo(cx + hw * 0.38, cy + hh * 0.08);

    // Ön tekerlek
    final fWheel = Path()
      ..addOval(Rect.fromCenter(
        center: Offset(cx - hw * 0.45, cy + hh * 0.58),
        width: hw * 0.32,
        height: hh * 0.40,
      ));
    final fWheelHub = Path()
      ..addOval(Rect.fromCenter(
        center: Offset(cx - hw * 0.45, cy + hh * 0.58),
        width: hw * 0.14,
        height: hh * 0.18,
      ));

    // Arka tekerlek
    final rWheel = Path()
      ..addOval(Rect.fromCenter(
        center: Offset(cx + hw * 0.55, cy + hh * 0.58),
        width: hw * 0.32,
        height: hh * 0.40,
      ));
    final rWheelHub = Path()
      ..addOval(Rect.fromCenter(
        center: Offset(cx + hw * 0.55, cy + hh * 0.58),
        width: hw * 0.14,
        height: hh * 0.18,
      ));

    // Far çizgisi
    final headlightLine = Path()
      ..moveTo(cx - hw * 0.92, cy + hh * 0.02)
      ..lineTo(cx - hw * 0.82, cy + hh * 0.02);

    // Arka stop çizgisi
    final tailLight = Path()
      ..moveTo(cx + hw * 0.92, cy + hh * 0.02)
      ..lineTo(cx + hw * 0.82, cy + hh * 0.02);

    // Eşik çizgisi
    final sill = Path()
      ..moveTo(cx - hw * 0.60, cy + hh * 0.50)
      ..lineTo(cx + hw * 0.40, cy + hh * 0.50);

    for (final path in [
      body, windows, doors, handles,
      fWheel, fWheelHub, rWheel, rWheelHub,
      headlightLine, tailLight, sill,
    ]) {
      canvas.drawPath(path, gp);
      canvas.drawPath(path, lp);
    }
  }

  // ═══════════════════════════════════════════════════════════════════
  //  ARKA SAĞ 45° GÖRÜNÜM (Rear-Right 3D Perspective)
  // ═══════════════════════════════════════════════════════════════════

  void _drawRearRight(Canvas canvas, Size size, Paint lp, Paint gp) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final w = size.width * 0.36;
    final h = size.height * 0.30;

    // Köşe hattı
    final edgeX = cx + w * 0.12;

    // — Arka yüz (sağ taraf, perspektifle daraltılmış) —
    final rearFace = Path()
      ..moveTo(edgeX, cy + h * 0.70)
      ..lineTo(edgeX, cy - h * 0.80)
      ..lineTo(edgeX + w * 0.18, cy - h * 0.72)
      ..lineTo(edgeX + w * 0.30, cy - h * 0.30)
      ..lineTo(edgeX + w * 0.40, cy - h * 0.08)
      ..lineTo(edgeX + w * 0.40, cy + h * 0.70)
      ..close();

    // Arka cam (arka yüzde)
    final rearWind = Path()
      ..moveTo(edgeX + w * 0.04, cy - h * 0.72)
      ..lineTo(edgeX + w * 0.16, cy - h * 0.65)
      ..lineTo(edgeX + w * 0.28, cy - h * 0.25)
      ..lineTo(edgeX + w * 0.04, cy - h * 0.25)
      ..close();

    // Arka stop
    final taillight = Path()
      ..addRRect(RRect.fromRectAndRadius(
        Rect.fromLTWH(
            edgeX + w * 0.04, cy + h * 0.02, w * 0.26, h * 0.12),
        const Radius.circular(2),
      ));

    // Plaka
    final plate = Path()
      ..addRRect(RRect.fromRectAndRadius(
        Rect.fromLTWH(
            edgeX + w * 0.08, cy + h * 0.28, w * 0.18, h * 0.10),
        const Radius.circular(1),
      ));

    // — Yan yüz (sol taraf, perspektif uzanır) —
    final sideFace = Path()
      ..moveTo(edgeX, cy - h * 0.80)
      ..lineTo(edgeX - w * 0.58, cy - h * 0.65)
      ..lineTo(edgeX - w * 0.68, cy - h * 0.28)
      ..lineTo(edgeX - w * 0.72, cy - h * 0.15)
      ..lineTo(edgeX - w * 0.72, cy + h * 0.50)
      ..lineTo(edgeX - w * 0.70, cy + h * 0.70)
      ..lineTo(edgeX, cy + h * 0.70)
      ..close();

    // Yan camlar
    final sideWin = Path()
      ..moveTo(edgeX - w * 0.02, cy - h * 0.72)
      ..lineTo(edgeX - w * 0.02, cy - h * 0.22)
      ..lineTo(edgeX - w * 0.28, cy - h * 0.22)
      ..lineTo(edgeX - w * 0.38, cy - h * 0.55)
      ..close()
      ..moveTo(edgeX - w * 0.30, cy - h * 0.22)
      ..lineTo(edgeX - w * 0.56, cy - h * 0.22)
      ..lineTo(edgeX - w * 0.64, cy - h * 0.28)
      ..lineTo(edgeX - w * 0.55, cy - h * 0.60)
      ..lineTo(edgeX - w * 0.42, cy - h * 0.55)
      ..close();

    // Kapı çizgisi
    final door = Path()
      ..moveTo(edgeX - w * 0.30, cy - h * 0.20)
      ..lineTo(edgeX - w * 0.30, cy + h * 0.55);

    // Tekerlekler
    final fWheel = Path()
      ..addOval(Rect.fromCenter(
        center: Offset(edgeX - w * 0.56, cy + h * 0.62),
        width: w * 0.20,
        height: h * 0.22,
      ));
    final fWheelIn = Path()
      ..addOval(Rect.fromCenter(
        center: Offset(edgeX - w * 0.56, cy + h * 0.62),
        width: w * 0.10,
        height: h * 0.11,
      ));
    final rWheel = Path()
      ..addOval(Rect.fromCenter(
        center: Offset(edgeX - w * 0.10, cy + h * 0.62),
        width: w * 0.20,
        height: h * 0.22,
      ));
    final rWheelIn = Path()
      ..addOval(Rect.fromCenter(
        center: Offset(edgeX - w * 0.10, cy + h * 0.62),
        width: w * 0.10,
        height: h * 0.11,
      ));

    // Tekerlek kavisleri
    final fArch = Path()
      ..addArc(
        Rect.fromCenter(
            center: Offset(edgeX - w * 0.56, cy + h * 0.52),
            width: w * 0.28,
            height: h * 0.26),
        0.2, pi - 0.4);
    final rArch = Path()
      ..addArc(
        Rect.fromCenter(
            center: Offset(edgeX - w * 0.10, cy + h * 0.52),
            width: w * 0.28,
            height: h * 0.26),
        0.2, pi - 0.4);

    // Köşe vurgu
    final edge = Path()
      ..moveTo(edgeX, cy - h * 0.80)
      ..lineTo(edgeX, cy + h * 0.70);

    for (final path in [
      rearFace, sideFace, rearWind, taillight, plate,
      sideWin, door, fArch, rArch,
      fWheel, fWheelIn, rWheel, rWheelIn, edge,
    ]) {
      canvas.drawPath(path, gp);
      canvas.drawPath(path, lp);
    }
  }

  // ═══════════════════════════════════════════════════════════════════
  //  ARKA GÖRÜNÜM (Rear)
  // ═══════════════════════════════════════════════════════════════════

  void _drawRear(Canvas canvas, Size size, Paint lp, Paint gp) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final hw = size.width * 0.17;
    final hh = size.height * 0.30;

    // Ana gövde silüeti
    final body = Path()
      ..moveTo(cx - hw, cy + hh * 0.85)
      ..lineTo(cx - hw, cy - hh * 0.15)
      ..lineTo(cx - hw * 0.78, cy - hh * 0.35)
      ..lineTo(cx - hw * 0.62, cy - hh * 0.85)
      ..lineTo(cx + hw * 0.62, cy - hh * 0.85)
      ..lineTo(cx + hw * 0.78, cy - hh * 0.35)
      ..lineTo(cx + hw, cy - hh * 0.15)
      ..lineTo(cx + hw, cy + hh * 0.85)
      ..close();

    // Arka cam
    final rearWindow = Path()
      ..moveTo(cx - hw * 0.55, cy - hh * 0.78)
      ..lineTo(cx - hw * 0.70, cy - hh * 0.30)
      ..lineTo(cx + hw * 0.70, cy - hh * 0.30)
      ..lineTo(cx + hw * 0.55, cy - hh * 0.78)
      ..close();

    // Sol stop lambası
    final leftTL = Path()
      ..addRRect(RRect.fromRectAndRadius(
        Rect.fromLTWH(
            cx - hw * 0.90, cy - hh * 0.08, hw * 0.35, hh * 0.18),
        const Radius.circular(3),
      ));

    // Sağ stop lambası
    final rightTL = Path()
      ..addRRect(RRect.fromRectAndRadius(
        Rect.fromLTWH(
            cx + hw * 0.55, cy - hh * 0.08, hw * 0.35, hh * 0.18),
        const Radius.circular(3),
      ));

    // Plaka alanı
    final plate = Path()
      ..addRRect(RRect.fromRectAndRadius(
        Rect.fromLTWH(
            cx - hw * 0.30, cy + hh * 0.18, hw * 0.60, hh * 0.12),
        const Radius.circular(2),
      ));

    // Bagaj çizgisi
    final trunk = Path()
      ..moveTo(cx - hw * 0.50, cy - hh * 0.20)
      ..lineTo(cx + hw * 0.50, cy - hh * 0.20);

    // Arka tampon
    final bumper = Path()
      ..moveTo(cx - hw * 0.90, cy + hh * 0.55)
      ..lineTo(cx - hw * 0.80, cy + hh * 0.50)
      ..lineTo(cx + hw * 0.80, cy + hh * 0.50)
      ..lineTo(cx + hw * 0.90, cy + hh * 0.55);

    // Egzoz çıkışları
    final exhaust = Path()
      ..addOval(Rect.fromCenter(
        center: Offset(cx - hw * 0.45, cy + hh * 0.68),
        width: hw * 0.18,
        height: hh * 0.08,
      ))
      ..addOval(Rect.fromCenter(
        center: Offset(cx + hw * 0.45, cy + hh * 0.68),
        width: hw * 0.18,
        height: hh * 0.08,
      ));

    // Difüzör çizgileri
    final diffuser = Path()
      ..moveTo(cx - hw * 0.35, cy + hh * 0.60)
      ..lineTo(cx + hw * 0.35, cy + hh * 0.60)
      ..moveTo(cx - hw * 0.25, cy + hh * 0.72)
      ..lineTo(cx + hw * 0.25, cy + hh * 0.72);

    // Tekerlek kısımları
    final wheelL = Path()
      ..addArc(
        Rect.fromCenter(
            center: Offset(cx - hw * 0.68, cy + hh * 0.88),
            width: hw * 0.50,
            height: hh * 0.22),
        0, pi);
    final wheelR = Path()
      ..addArc(
        Rect.fromCenter(
            center: Offset(cx + hw * 0.68, cy + hh * 0.88),
            width: hw * 0.50,
            height: hh * 0.22),
        0, pi);

    for (final path in [
      body, rearWindow, leftTL, rightTL, plate, trunk, bumper,
      exhaust, diffuser, wheelL, wheelR,
    ]) {
      canvas.drawPath(path, gp);
      canvas.drawPath(path, lp);
    }
  }

  @override
  bool shouldRepaint(covariant _CarWireframePainter old) =>
      old.isAligned != isAligned ||
      old.pulseValue != pulseValue ||
      old.aci != aci;
}

// ═══════════════════════════════════════════════════════════════════════
//  PUSULA KADRANI (Compass Dial) — Telemetri başlığı sol kenarı
// ═══════════════════════════════════════════════════════════════════════

class _CompassDialPainter extends CustomPainter {
  final String aci;
  final bool isAligned;

  _CompassDialPainter({required this.aci, required this.isAligned});

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final r = size.width * 0.40;

    // Dış halka
    final ringPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.15)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2;
    canvas.drawCircle(Offset(cx, cy), r, ringPaint);

    // 8 işaret çizgisi
    for (int i = 0; i < 8; i++) {
      final angle = (i * 45 - 90) * pi / 180;
      final inner = r * 0.72;
      final outer = r * 0.95;
      final p = Paint()
        ..color = Colors.white.withValues(alpha: 0.25)
        ..strokeWidth = 1.0;
      canvas.drawLine(
        Offset(cx + cos(angle) * inner, cy + sin(angle) * inner),
        Offset(cx + cos(angle) * outer, cy + sin(angle) * outer),
        p,
      );
    }

    // Aktif dilim (vurgulanan açı)
    final deg = _kAngleDegrees[aci] ?? 0;
    final startAngle = (deg - 90 - 22.5) * pi / 180;
    const sweepAngle = 45 * pi / 180;

    final sliceColor = isAligned ? Colors.greenAccent : _kCyan;
    final slicePaint = Paint()
      ..color = sliceColor.withValues(alpha: 0.35)
      ..style = PaintingStyle.fill;
    canvas.drawArc(
      Rect.fromCircle(center: Offset(cx, cy), radius: r),
      startAngle,
      sweepAngle,
      true,
      slicePaint,
    );

    // Dilim kenar çizgisi
    final sliceBorder = Paint()
      ..color = sliceColor.withValues(alpha: 0.7)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;
    canvas.drawArc(
      Rect.fromCircle(center: Offset(cx, cy), radius: r),
      startAngle,
      sweepAngle,
      true,
      sliceBorder,
    );

    // Merkez araba noktası
    final dotPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.6)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(cx, cy), 2.5, dotPaint);

    // Yön oku (aktif dilimin ortasında)
    final arrowAngle = (deg - 90) * pi / 180;
    final arrowTip =
        Offset(cx + cos(arrowAngle) * r * 0.55, cy + sin(arrowAngle) * r * 0.55);
    final arrowPaint = Paint()
      ..color = sliceColor
      ..strokeWidth = 1.5
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(Offset(cx, cy), arrowTip, arrowPaint);
    canvas.drawCircle(arrowTip, 2, Paint()..color = sliceColor);
  }

  @override
  bool shouldRepaint(covariant _CompassDialPainter old) =>
      old.aci != aci || old.isAligned != isAligned;
}

// ═══════════════════════════════════════════════════════════════════════
//  SU TERAZİSİ PAİNTER (Level Meter)
// ═══════════════════════════════════════════════════════════════════════

class _LevelMeterPainter extends CustomPainter {
  final double pitch;
  final double roll;
  final bool isLevelOk;
  final bool isAligned;
  final double pulseValue;

  _LevelMeterPainter({
    required this.pitch,
    required this.roll,
    required this.isLevelOk,
    required this.isAligned,
    required this.pulseValue,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    const outerR = 28.0;
    const innerR = 5.0;
    const dotR = 3.5;

    final bool perfect = isLevelOk && isAligned;

    // — Dış halka —
    final outerPaint = Paint()
      ..color = perfect
          ? Colors.greenAccent.withValues(alpha: 0.6)
          : Colors.white.withValues(alpha: 0.25)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.8;
    canvas.drawCircle(Offset(cx, cy), outerR, outerPaint);

    // Yeşil parlama (tam hizalanınca)
    if (perfect) {
      final glowPaint = Paint()
        ..color = Colors.greenAccent.withValues(alpha: 0.2 + 0.15 * pulseValue)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 5.0
        ..maskFilter =
            MaskFilter.blur(BlurStyle.normal, 8 + 4 * pulseValue);
      canvas.drawCircle(Offset(cx, cy), outerR, glowPaint);
    }

    // — İç hedef dairesi —
    final innerPaint = Paint()
      ..color = perfect
          ? Colors.greenAccent.withValues(alpha: 0.3)
          : Colors.white.withValues(alpha: 0.10)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(cx, cy), innerR, innerPaint);

    final innerStroke = Paint()
      ..color = Colors.white.withValues(alpha: 0.15)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.8;
    canvas.drawCircle(Offset(cx, cy), innerR, innerStroke);

    // — Artı nişan çizgileri —
    final crossP = Paint()
      ..color = Colors.white.withValues(alpha: 0.10)
      ..strokeWidth = 0.5;
    canvas.drawLine(
        Offset(cx - outerR, cy), Offset(cx + outerR, cy), crossP);
    canvas.drawLine(
        Offset(cx, cy - outerR), Offset(cx, cy + outerR), crossP);

    // — Hareketli nokta —
    // Roll → x ekseni, Pitch → y ekseni. Max ±8° → tam kenar
    final scale = outerR / 8.0;
    final dotX = (cx + roll * scale).clamp(cx - outerR + dotR, cx + outerR - dotR);
    final dotY = (cy + pitch * scale).clamp(cy - outerR + dotR, cy + outerR - dotR);

    final dist = sqrt(pow(dotX - cx, 2) + pow(dotY - cy, 2));
    final dotInTarget = dist <= innerR;

    final dotColor = dotInTarget && isAligned
        ? Colors.greenAccent
        : Colors.redAccent;

    // Nokta glow
    final dotGlow = Paint()
      ..color = dotColor.withValues(alpha: 0.4)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4);
    canvas.drawCircle(Offset(dotX, dotY), dotR + 2, dotGlow);

    // Nokta
    final dotPaint = Paint()
      ..color = dotColor
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(dotX, dotY), dotR, dotPaint);
  }

  @override
  bool shouldRepaint(covariant _LevelMeterPainter old) =>
      old.pitch != pitch ||
      old.roll != roll ||
      old.isLevelOk != isLevelOk ||
      old.isAligned != isAligned ||
      old.pulseValue != pulseValue;
}

// ═══════════════════════════════════════════════════════════════════════
//  AÇI REHBERİ — Kuşbakışı araç diyagramı + kamera pozisyonu
// ═══════════════════════════════════════════════════════════════════════

class _AngleGuidePainter extends CustomPainter {
  final String aci;
  final double pulseValue;

  _AngleGuidePainter({required this.aci, required this.pulseValue});

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;

    // ── Arabanın üstten görünüşü ──
    final carW = size.width * 0.28;
    final carH = size.height * 0.50;

    // Gövde
    final bodyPaint = Paint()
      ..color = Colors.white.withOpacity(0.15)
      ..style = PaintingStyle.fill;
    final bodyStroke = Paint()
      ..color = Colors.white.withOpacity(0.4)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;

    final bodyPath = Path()
      ..moveTo(cx - carW * 0.7, cy - carH * 0.35)  // sol ön köşe
      ..lineTo(cx - carW * 0.5, cy - carH * 0.5)   // sol burun
      ..lineTo(cx + carW * 0.5, cy - carH * 0.5)   // sağ burun
      ..lineTo(cx + carW * 0.7, cy - carH * 0.35)  // sağ ön köşe
      ..lineTo(cx + carW * 0.75, cy + carH * 0.35)  // sağ arka köşe
      ..lineTo(cx + carW * 0.5, cy + carH * 0.5)   // sağ arka
      ..lineTo(cx - carW * 0.5, cy + carH * 0.5)   // sol arka
      ..lineTo(cx - carW * 0.75, cy + carH * 0.35)  // sol arka köşe
      ..close();

    canvas.drawPath(bodyPath, bodyPaint);
    canvas.drawPath(bodyPath, bodyStroke);

    // Ön cam
    final windshieldPaint = Paint()
      ..color = _kCyan.withOpacity(0.15)
      ..style = PaintingStyle.fill;
    final wsPath = Path()
      ..moveTo(cx - carW * 0.5, cy - carH * 0.25)
      ..lineTo(cx - carW * 0.4, cy - carH * 0.38)
      ..lineTo(cx + carW * 0.4, cy - carH * 0.38)
      ..lineTo(cx + carW * 0.5, cy - carH * 0.25)
      ..close();
    canvas.drawPath(wsPath, windshieldPaint);

    // Ön yön işareti (küçük üçgen)
    final frontMark = Paint()
      ..color = _kCyan.withOpacity(0.6)
      ..style = PaintingStyle.fill;
    final fmPath = Path()
      ..moveTo(cx, cy - carH * 0.5 - 2)
      ..lineTo(cx - 3, cy - carH * 0.5 + 4)
      ..lineTo(cx + 3, cy - carH * 0.5 + 4)
      ..close();
    canvas.drawPath(fmPath, frontMark);

    // ── Kamera pozisyon göstergesi ──
    final degree = _kAngleDegrees[aci] ?? 0;
    // Açıyı radyana çevir (0° = ön = yukarı, saat yönünde artar)
    final rad = (degree - 90) * pi / 180;
    final orbitR = size.width * 0.40;
    final camX = cx + orbitR * cos(rad);
    final camY = cy + orbitR * sin(rad);

    // Kameradan arabaya doğru kesikli çizgi
    final dashPaint = Paint()
      ..color = _kCyan.withOpacity(0.3)
      ..strokeWidth = 1.0;
    // Basit kesikli çizgi
    final dx = cx - camX;
    final dy = cy - camY;
    final dist = sqrt(dx * dx + dy * dy);
    final ux = dx / dist;
    final uy = dy / dist;
    for (double d = 0; d < dist - 8; d += 6) {
      canvas.drawLine(
        Offset(camX + ux * d, camY + uy * d),
        Offset(camX + ux * (d + 3), camY + uy * (d + 3)),
        dashPaint,
      );
    }

    // Kamera ikonu glow
    final glowR = 7.0 + 3.0 * pulseValue;
    final camGlow = Paint()
      ..color = _kCyan.withOpacity(0.3 + 0.2 * pulseValue)
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, 6 + 4 * pulseValue);
    canvas.drawCircle(Offset(camX, camY), glowR, camGlow);

    // Kamera ikonu dolu daire
    final camPaint = Paint()
      ..color = _kCyan
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(camX, camY), 5, camPaint);

    // Kamera ikonu içi (küçük lens)
    final lensPaint = Paint()
      ..color = Colors.black.withOpacity(0.6)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(camX, camY), 2, lensPaint);
  }

  @override
  bool shouldRepaint(covariant _AngleGuidePainter old) =>
      old.aci != aci || old.pulseValue != pulseValue;
}
