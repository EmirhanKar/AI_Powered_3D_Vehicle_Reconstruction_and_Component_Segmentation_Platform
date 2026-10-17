import 'dart:async';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:sensors_plus/sensors_plus.dart';

/// Canlı Su Terazisi (Pitch/Eğim Ölçer) Widget'ı.
/// Cihazın dikey eğim açısını (pitch) sensors_plus ile dinler
/// ve hedeflenen açı aralığına (35° - 45° öne eğik) ulaşılması için
/// kullanıcıyı görsel ve haptik (titreşimli) olarak yönlendirir.
class CanliSuTerazisi extends StatefulWidget {
  /// Hedeflenen minimum eğim açısı (varsayılan: 35.0°)
  final double targetMin;

  /// Hedeflenen maksimum eğim açısı (varsayılan: 45.0°)
  final double targetMax;

  /// Eğim açısı doğru aralığa girdiğinde ya da çıktığında tetiklenen callback
  final ValueChanged<bool>? onLevelChanged;

  /// Eğim açısı her güncellendiğinde tetiklenen callback
  final ValueChanged<double>? onPitchChanged;

  const CanliSuTerazisi({
    super.key,
    this.targetMin = 35.0,
    this.targetMax = 45.0,
    this.onLevelChanged,
    this.onPitchChanged,
  });

  @override
  State<CanliSuTerazisi> createState() => _CanliSuTerazisiState();
}

class _CanliSuTerazisiState extends State<CanliSuTerazisi> {
  StreamSubscription<AccelerometerEvent>? _accelerometerSubscription;
  double _pitch = 0.0;
  bool _isLevelOk = false;

  // Sensör gürültüsünü engellemek için Low Pass Filter (Düşük Geçişli Filtre) katsayısı.
  // 1.0 anlık değişimdir, 0.05 ise çok yavaş ve yumuşaktır. 0.15 optimumdur.
  static const double _filterCoeff = 0.15;
  double _filteredPitch = 0.0;

  @override
  void initState() {
    super.initState();
    _startListening();
  }

  @override
  void dispose() {
    _accelerometerSubscription?.cancel();
    super.dispose();
  }

  void _startListening() {
    // sensors_plus ile ivmeölçer verilerini dinlemeye başlıyoruz.
    _accelerometerSubscription = accelerometerEventStream().listen((AccelerometerEvent event) {
      if (!mounted) return;

      final double x = event.x;
      final double y = event.y;
      final double z = event.z;

      // İvme vektörünün büyüklüğünü hesaplıyoruz
      final double norm = sqrt(x * x + y * y + z * z);
      if (norm == 0) return;

      // Pitch (Dikey Eğim) Açısı Hesaplama:
      // Y ve Z eksenlerini kullanan atan2 formülü:
      // - Telefon dik konumdayken (y ≈ -9.8, z ≈ 0) eğim 0° referans alınır.
      // - Öne doğru eğildikçe derece canlı ve akıcı bir şekilde artar.
      double rawPitch = atan2(-z, -y) * 180 / pi;

      // Filtreleme uygulayarak ani titremeleri ve sensör parazitlerini temizliyoruz
      _filteredPitch = _filteredPitch + _filterCoeff * (rawPitch - _filteredPitch);

      // Açının belirlenen hedef aralıkta olup olmadığını denetliyoruz
      final bool currentLevelOk = _filteredPitch >= widget.targetMin && _filteredPitch <= widget.targetMax;

      if (currentLevelOk != _isLevelOk) {
        _isLevelOk = currentLevelOk;
        
        // Açı doğru aralığa girdiğinde kullanıcıya hafif bir haptik (titreşim) geri bildirimi veriyoruz
        if (_isLevelOk) {
          HapticFeedback.lightImpact();
        }
        widget.onLevelChanged?.call(_isLevelOk);
      }

      setState(() {
        _pitch = _filteredPitch;
      });
      widget.onPitchChanged?.call(_filteredPitch);
    });
  }

  @override
  Widget build(BuildContext context) {
    // Hedeflenen açının tam merkezini hesaplayalım (Örn: 40.0°)
    final double targetCenter = (widget.targetMin + widget.targetMax) / 2;
    // Anlık açının merkezden sapma miktarını bulalım
    final double deviation = _pitch - targetCenter;

    // Sapmayı [-30, 30] derece aralığında sınırlandırıp ekran hareket alanına oranlayalım.
    // Dış halkanın yarıçapına uygun olarak [-35, 35] piksel aralığına clamp ediyoruz.
    double yOffset = -deviation * 1.5; // Eğim yönüyle görsel hareketi eşlemek için tersine çeviriyoruz
    yOffset = yOffset.clamp(-35.0, 35.0);

    // Eğer açı doğru aralıktaysa küçük daireyi tam merkeze kilitliyoruz.
    if (_isLevelOk) {
      yOffset = 0.0;
    }

    // Duruma göre renk ve uyarı mesajı seçimi
    final Color statusColor = _isLevelOk ? Colors.greenAccent : Colors.redAccent;
    
    String warningText;
    if (_pitch < widget.targetMin) {
      warningText = "Telefonu Öne Eğ";
    } else if (_pitch > widget.targetMax) {
      warningText = "Telefonu Dikleştir";
    } else {
      warningText = "Açı Mükemmel";
    }

    return Container(
      width: 130,
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 10),
      decoration: BoxDecoration(
        color: const Color(0xCC0A1017), // Şeffaf koyu premium cam arka plan
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: _isLevelOk 
              ? Colors.greenAccent.withOpacity(0.4) 
              : Colors.white.withOpacity(0.08),
          width: 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.4),
            blurRadius: 16,
            spreadRadius: 2,
          ),
          if (_isLevelOk)
            BoxShadow(
              color: Colors.greenAccent.withOpacity(0.05),
              blurRadius: 20,
              spreadRadius: 1,
            ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Küçük Kılavuz Başlığı
          Text(
            "CİHAZ EĞİMİ",
            style: TextStyle(
              color: Colors.white.withOpacity(0.5),
              fontSize: 10,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.2,
            ),
          ),
          const SizedBox(height: 12),

          // Su Terazisi Daire Grafiği
          SizedBox(
            width: 90,
            height: 90,
            child: Stack(
              alignment: Alignment.center,
              children: [
                // Sabit Dış Halka (Hedef Çemberi)
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: _isLevelOk 
                          ? Colors.greenAccent.withOpacity(0.6) 
                          : Colors.white.withOpacity(0.2),
                      width: 2.5,
                    ),
                  ),
                ),
                
                // Tam Merkez Noktası (Referans Noktası)
                Container(
                  width: 6,
                  height: 6,
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.3),
                    shape: BoxShape.circle,
                  ),
                ),

                // Hareketli İç Küçük Daire
                AnimatedContainer(
                  duration: const Duration(milliseconds: 60), // Hızlı ve akıcı hareket tepkisi
                  curve: Curves.easeOutCubic,
                  transform: Matrix4.translationValues(0, yOffset, 0),
                  child: Container(
                    width: 22,
                    height: 22,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: statusColor,
                      boxShadow: [
                        BoxShadow(
                          color: statusColor.withOpacity(0.5),
                          blurRadius: 8,
                          spreadRadius: 1,
                        ),
                      ],
                    ),
                    child: _isLevelOk
                        ? const Center(
                            child: Icon(
                              Icons.check,
                              color: Colors.black,
                              size: 13,
                            ),
                          )
                        : null,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),

          // Dijital Eğim Derecesi
          Text(
            "${_pitch.toStringAsFixed(1)}°",
            style: TextStyle(
              color: statusColor,
              fontSize: 18,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 4),

          // Yönlendirme Metni
          Text(
            warningText,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: _isLevelOk ? Colors.greenAccent : Colors.white70,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
