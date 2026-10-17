import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../sistem_ve_dil.dart';
import '../servisler/api_servisi.dart';
import 'model_3d_viewer.dart';

class TextTo3DSayfasi extends StatefulWidget {
  const TextTo3DSayfasi({super.key});

  @override
  State<TextTo3DSayfasi> createState() => _TextTo3DSayfasiState();
}

class _TextTo3DSayfasiState extends State<TextTo3DSayfasi> {
  final _promptCtrl = TextEditingController();
  bool _isLoading = false;
  String? _taskId;
  String _status = '';
  int _progress = 0;
  String? _modelUrl;
  Timer? _timer;
  String _modelVersion = 'default';

  @override
  void dispose() {
    _promptCtrl.dispose();
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _generateModel() async {
    final prompt = _promptCtrl.text.trim();
    if (prompt.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(t('signup_fill_all')),
          backgroundColor: Colors.orange,
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }

    if (titresimAcik.value) HapticFeedback.mediumImpact();

    setState(() {
      _isLoading = true;
      _status = 'Queued';
      _progress = 0;
      _modelUrl = null;
      _taskId = null;
    });

    try {
      final taskId = await ApiServisi().tripoTextTo3D(prompt, modelVersion: _modelVersion);
      setState(() {
        _taskId = taskId;
      });
      _startPolling(taskId);
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(e.toString().replaceAll("Exception: ", "")),
            backgroundColor: Colors.redAccent,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  void _startPolling(String taskId) {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 5), (timer) async {
      try {
        final result = await ApiServisi().tripoGetTaskStatus(taskId);
        final status = result['status'] ?? 'queued';
        final progress = result['progress'] ?? 0;
        final modelUrl = result['model_url'];

        setState(() {
          _status = status;
          _progress = progress;
        });

        if (status == 'success' && modelUrl != null) {
          _timer?.cancel();
          setState(() {
            _isLoading = false;
            _modelUrl = modelUrl;
          });
          if (mounted && titresimAcik.value) HapticFeedback.mediumImpact();
        } else if (status == 'failed' || status == 'cancelled' || status == 'expired') {
          _timer?.cancel();
          setState(() {
            _isLoading = false;
          });
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Model üretimi başarısız oldu: $status'),
                backgroundColor: Colors.redAccent,
                behavior: SnackBarBehavior.floating,
              ),
            );
          }
        }
      } catch (e) {
        // Hataları sessizce geç
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final Color anaRenk = const Color(0xFF257bf4);
    final Color koyuArkaplan = arkaplanRengi();
    final Color koyuYuzey = yuzeyRengi();

    return Scaffold(
      backgroundColor: koyuArkaplan,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          t('text_to_3d_title'),
          style: const TextStyle(
            color: Colors.white,
            fontSize: 16,
            fontWeight: FontWeight.bold,
          ),
        ),
        centerTitle: true,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Üst Görsel / Simge Kartı
              Container(
                padding: const EdgeInsets.symmetric(vertical: 32, horizontal: 16),
                decoration: BoxDecoration(
                  color: koyuYuzey,
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: kartBorderRengi()),
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      koyuYuzey,
                      anaRenk.withOpacity(0.05),
                    ],
                  ),
                ),
                child: Column(
                  children: [
                    ShaderMask(
                      shaderCallback: (bounds) => LinearGradient(
                        colors: [anaRenk, Colors.purpleAccent],
                      ).createShader(bounds),
                      child: const Icon(
                        Icons.text_fields_outlined,
                        size: 64,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      t('text_to_3d'),
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      t('text_to_3d_desc'),
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: ikinciYaziRengi(),
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // Giriş Alanı
              if (!_isLoading && _modelUrl == null) ...[
                Text(
                  t('text_to_3d_title'),
                  style: const TextStyle(
                    color: Colors.white70,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _promptCtrl,
                  maxLines: 3,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    filled: true,
                    fillColor: koyuYuzey,
                    hintText: t('text_to_3d_hint'),
                    hintStyle: const TextStyle(color: Colors.grey, fontSize: 13),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(16),
                      borderSide: BorderSide.none,
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(16),
                      borderSide: BorderSide(color: anaRenk, width: 1.5),
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                // Model Versiyon Seçimi
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Tripo Versiyonu:',
                      style: TextStyle(color: Colors.white70, fontSize: 13),
                    ),
                    DropdownButton<String>(
                      value: _modelVersion,
                      dropdownColor: koyuYuzey,
                      style: const TextStyle(color: Colors.white, fontSize: 13),
                      underline: Container(),
                      items: const [
                        DropdownMenuItem(value: 'default', child: Text('Varsayılan')),
                        DropdownMenuItem(value: 'v2.0', child: Text('Tripo v2.0')),
                        DropdownMenuItem(value: 'v2.5', child: Text('Tripo v2.5')),
                      ],
                      onChanged: (val) {
                        if (val != null) {
                          setState(() => _modelVersion = val);
                        }
                      },
                    ),
                  ],
                ),
                const SizedBox(height: 24),

                // Üretim Butonu
                ElevatedButton(
                  onPressed: _generateModel,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: anaRenk,
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                    elevation: 8,
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.auto_awesome, color: Colors.white, size: 18),
                      const SizedBox(width: 8),
                      Text(
                        t('text_to_3d_btn'),
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: Colors.black26,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Text(
                          '60 Kredi',
                          style: TextStyle(color: Colors.yellow, fontSize: 11, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                ),
              ],

              // Loading / Processing Bölümü
              if (_isLoading) ...[
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: koyuYuzey,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: kartBorderRengi()),
                  ),
                  child: Column(
                    children: [
                      const CircularProgressIndicator(strokeWidth: 3),
                      const SizedBox(height: 24),
                      Text(
                        t('text_to_3d_generating'),
                        style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Durum: $_status',
                        style: TextStyle(color: ikinciYaziRengi(), fontSize: 13),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'İlerleme: %$_progress',
                        style: TextStyle(color: anaRenk, fontSize: 14, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 16),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: LinearProgressIndicator(
                          value: _progress / 100,
                          backgroundColor: Colors.black26,
                          valueColor: AlwaysStoppedAnimation<Color>(anaRenk),
                          minHeight: 8,
                        ),
                      ),
                    ],
                  ),
                ),
              ],

              // Başarı / Model Hazır Bölümü
              if (_modelUrl != null) ...[
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: koyuYuzey,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: Colors.green.withOpacity(0.3)),
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        koyuYuzey,
                        Colors.green.withOpacity(0.02),
                      ],
                    ),
                  ),
                  child: Column(
                    children: [
                      const Icon(Icons.check_circle_outline, color: Colors.greenAccent, size: 56),
                      const SizedBox(height: 16),
                      Text(
                        t('text_to_3d_success'),
                        style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 24),
                      ElevatedButton(
                        onPressed: () {
                          if (titresimAcik.value) HapticFeedback.lightImpact();
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (c) => Model3DViewer(
                                modelUrl: _modelUrl!,
                                carName: _promptCtrl.text.trim(),
                              ),
                            ),
                          );
                        },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.green,
                          padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 32),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Icon(Icons.view_in_ar, color: Colors.white),
                            const SizedBox(width: 12),
                            Text(
                              t('view_3d_model'),
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextButton(
                        onPressed: () {
                          setState(() {
                            _modelUrl = null;
                            _promptCtrl.clear();
                          });
                        },
                        child: const Text('Yeni Model Üret', style: TextStyle(color: Colors.grey)),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
