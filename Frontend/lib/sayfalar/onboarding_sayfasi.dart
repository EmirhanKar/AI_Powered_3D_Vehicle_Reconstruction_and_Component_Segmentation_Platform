import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../sistem_ve_dil.dart';
import '../ortak_widgetlar.dart';
import '../sayfalar_ana.dart';

class OnboardingSayfasi extends StatefulWidget {
  const OnboardingSayfasi({super.key});
  @override
  State<OnboardingSayfasi> createState() => _OnboardingSayfasiState();
}

class _OnboardingSayfasiState extends State<OnboardingSayfasi>
    with TickerProviderStateMixin {
  final PageController _pageController = PageController();
  int _currentPage = 0;

  late AnimationController _fadeController;
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..forward();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pageController.dispose();
    _fadeController.dispose();
    _pulseController.dispose();
    super.dispose();
  }

  void _goToPage(int page) {
    if (titresimAcik.value) HapticFeedback.selectionClick();
    _pageController.animateToPage(
      page,
      duration: const Duration(milliseconds: 400),
      curve: Curves.easeInOutCubic,
    );
  }

  void _onNext() {
    if (_currentPage < 2) {
      _goToPage(_currentPage + 1);
    }
  }

  void _navigateToLogin() {
    if (titresimAcik.value) HapticFeedback.mediumImpact();
    yumusakGecisYap(context, const GirisSayfasi(), eskiSayfayiKapat: true);
  }

  void _navigateAsGuest() {
    if (titresimAcik.value) HapticFeedback.lightImpact();
    yumusakGecisYap(context, const AnaSayfa(), eskiSayfayiKapat: true);
  }

  @override
  Widget build(BuildContext context) {
    const Color koyuArkaplan = Color(0xFF0A1017);
    const Color anaRenk = Color(0xFF257bf4);

    return Scaffold(
      backgroundColor: koyuArkaplan,
      body: Stack(
        children: [
          // Background gradient
          Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color(0xFF0F1A2A),
                  Color(0xFF0A1017),
                  Color(0xFF05080C),
                ],
              ),
            ),
          ),
          // Background glow effects
          Positioned(
            top: -100,
            right: -100,
            child: Container(
              width: 300,
              height: 300,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    anaRenk.withValues(alpha: 0.15),
                    Colors.transparent,
                  ],
                ),
              ),
            ),
          ),
          Positioned(
            bottom: -50,
            left: -80,
            child: Container(
              width: 250,
              height: 250,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    const Color(0xFF8A2387).withValues(alpha: 0.1),
                    Colors.transparent,
                  ],
                ),
              ),
            ),
          ),
          // PageView
          SafeArea(
            child: Column(
              children: [
                // Skip button
                Align(
                  alignment: Alignment.centerRight,
                  child: Padding(
                    padding: const EdgeInsets.only(right: 16, top: 8),
                    child: TextButton(
                      onPressed: _navigateAsGuest,
                      child: Text(
                        t('onboarding_skip'),
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.5),
                          fontSize: 14,
                        ),
                      ),
                    ),
                  ),
                ),
                // Pages
                Expanded(
                  child: PageView(
                    controller: _pageController,
                    onPageChanged: (page) {
                      setState(() => _currentPage = page);
                      _fadeController.reset();
                      _fadeController.forward();
                    },
                    children: [
                      _buildWelcomePage(anaRenk),
                      _buildFeaturePage(anaRenk),
                      _buildSignupPage(anaRenk),
                    ],
                  ),
                ),
                // Dot indicators
                Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(3, (index) {
                      return AnimatedContainer(
                        duration: const Duration(milliseconds: 300),
                        margin: const EdgeInsets.symmetric(horizontal: 4),
                        width: _currentPage == index ? 28 : 8,
                        height: 8,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(4),
                          color: _currentPage == index
                              ? anaRenk
                              : Colors.white.withValues(alpha: 0.2),
                          boxShadow: _currentPage == index
                              ? [
                                  BoxShadow(
                                    color: anaRenk.withValues(alpha: 0.4),
                                    blurRadius: 8,
                                    spreadRadius: 1,
                                  ),
                                ]
                              : [],
                        ),
                      );
                    }),
                  ),
                ),
                // Bottom action button
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
                  child: _currentPage < 2
                      ? _buildNextButton(anaRenk)
                      : _buildSignupButtons(anaRenk),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ── PAGE 1: WELCOME ──
  Widget _buildWelcomePage(Color anaRenk) {
    return FadeTransition(
      opacity: _fadeController,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Animated Logo
            AnimatedBuilder(
              animation: _pulseController,
              builder: (context, child) {
                return Transform.scale(
                  scale: 1.0 + _pulseController.value * 0.05,
                  child: child,
                );
              },
              child: Container(
                width: 160,
                height: 160,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: anaRenk.withValues(alpha: 0.3),
                      blurRadius: 40,
                      spreadRadius: 10,
                    ),
                  ],
                ),
                child: ClipOval(
                  child: Image.asset(
                    'assets/LOGO101.png',
                    fit: BoxFit.contain,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 48),
            // Title
            ShaderMask(
              shaderCallback: (bounds) => const LinearGradient(
                colors: [Color(0xFF257bf4), Color(0xFF8A2387)],
              ).createShader(bounds),
              child: Text(
                t('ob_welcome_title'),
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 32,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.2,
                  height: 1.2,
                ),
              ),
            ),
            const SizedBox(height: 20),
            // Description
            Text(
              t('ob_welcome_desc'),
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white.withValues(alpha: 0.7),
                fontSize: 16,
                height: 1.6,
                letterSpacing: 0.3,
              ),
            ),
            const SizedBox(height: 40),
            // Feature pills
            Wrap(
              spacing: 12,
              runSpacing: 12,
              alignment: WrapAlignment.center,
              children: [
                _buildFeaturePill(Icons.auto_fix_high, 'AI Modifiye', anaRenk),
                _buildFeaturePill(Icons.threed_rotation, '3D Model', const Color(0xFF8A2387)),
                _buildFeaturePill(Icons.people, 'Topluluk', const Color(0xFF00C853)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFeaturePill(IconData icon, String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(30),
        border: Border.all(
          color: color.withValues(alpha: 0.3),
          width: 1,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(width: 8),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  // ── PAGE 2: FEATURE SHOWCASE ──
  Widget _buildFeaturePage(Color anaRenk) {
    return FadeTransition(
      opacity: _fadeController,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Car Image
            Container(
              height: 260,
              width: double.infinity,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(24),
                boxShadow: [
                  BoxShadow(
                    color: anaRenk.withValues(alpha: 0.3),
                    blurRadius: 30,
                    spreadRadius: 5,
                    offset: const Offset(0, 10),
                  ),
                ],
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(24),
                child: Stack(
                  children: [
                    Image.asset(
                      'assets/onboarding/onboarding_car.png',
                      width: double.infinity,
                      height: 260,
                      fit: BoxFit.cover,
                      errorBuilder: (c, e, s) => Container(
                        color: const Color(0xFF182434),
                        child: const Center(
                          child: Icon(
                            Icons.directions_car,
                            size: 80,
                            color: Colors.grey,
                          ),
                        ),
                      ),
                    ),
                    // Gradient overlay
                    Positioned.fill(
                      child: Container(
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            begin: Alignment.topCenter,
                            end: Alignment.bottomCenter,
                            colors: [
                              Colors.transparent,
                              Colors.black.withValues(alpha: 0.6),
                            ],
                            stops: const [0.5, 1.0],
                          ),
                        ),
                      ),
                    ),
                    // Overlay icons
                    Positioned(
                      bottom: 16,
                      left: 16,
                      child: Row(
                        children: [
                          _buildMiniTag(Icons.camera_alt, 'Çek', Colors.white),
                          const SizedBox(width: 8),
                          _buildMiniTag(Icons.threed_rotation, '3D', anaRenk),
                          const SizedBox(width: 8),
                          _buildMiniTag(Icons.image, '2D', const Color(0xFF8A2387)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 40),
            // Title
            Text(
              t('ob_feature_title'),
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 28,
                fontWeight: FontWeight.bold,
                height: 1.3,
              ),
            ),
            const SizedBox(height: 16),
            // Description
            Text(
              t('ob_feature_desc'),
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white.withValues(alpha: 0.65),
                fontSize: 16,
                height: 1.6,
              ),
            ),
            const SizedBox(height: 32),
            // Feature cards
            Row(
              children: [
                Expanded(child: _buildFeatureCard(
                  Icons.threed_rotation,
                  '3D Test',
                  'Modifiyeni 3 boyutlu incele',
                  anaRenk,
                )),
                const SizedBox(width: 12),
                Expanded(child: _buildFeatureCard(
                  Icons.share,
                  '2D Paylaş',
                  '2D modifiye edip paylaş',
                  const Color(0xFF8A2387),
                )),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMiniTag(IconData icon, String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: color, size: 14),
          const SizedBox(width: 4),
          Text(
            text,
            style: TextStyle(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFeatureCard(
    IconData icon,
    String title,
    String desc,
    Color color,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: color, size: 24),
          ),
          const SizedBox(height: 10),
          Text(
            title,
            style: TextStyle(
              color: color,
              fontSize: 14,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            desc,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.5),
              fontSize: 11,
            ),
          ),
        ],
      ),
    );
  }

  // ── PAGE 3: SIGNUP CTA ──
  Widget _buildSignupPage(Color anaRenk) {
    return FadeTransition(
      opacity: _fadeController,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Icon with glow
            AnimatedBuilder(
              animation: _pulseController,
              builder: (context, child) {
                return Container(
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: anaRenk.withValues(alpha: 0.2 + _pulseController.value * 0.15),
                        blurRadius: 40 + _pulseController.value * 20,
                        spreadRadius: 5,
                      ),
                    ],
                  ),
                  child: child,
                );
              },
              child: Container(
                width: 120,
                height: 120,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      anaRenk,
                      const Color(0xFF8A2387),
                    ],
                  ),
                ),
                child: const Icon(
                  Icons.auto_fix_high,
                  color: Colors.white,
                  size: 56,
                ),
              ),
            ),
            const SizedBox(height: 48),
            // Title
            Text(
              t('ob_signup_title'),
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 30,
                fontWeight: FontWeight.bold,
                height: 1.2,
              ),
            ),
            const SizedBox(height: 16),
            // Description
            Text(
              t('ob_signup_desc'),
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white.withValues(alpha: 0.65),
                fontSize: 16,
                height: 1.6,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Eğer uygulamayla alakalı bilgi almak isterseniz lütfen ilk önce misafir olarak devam ediniz.',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: Colors.white.withValues(alpha: 0.5),
                fontSize: 12,
              ),
            ),
            const SizedBox(height: 48),
            // Benefits row
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _buildBenefitItem(Icons.speed, 'Hızlı AI'),
                _buildBenefitItem(Icons.palette, 'Sınırsız Renk'),
                _buildBenefitItem(Icons.diamond, 'Premium Jant'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBenefitItem(IconData icon, String label) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.06),
            shape: BoxShape.circle,
            border: Border.all(
              color: Colors.white.withValues(alpha: 0.1),
            ),
          ),
          child: Icon(icon, color: Colors.white.withValues(alpha: 0.8), size: 24),
        ),
        const SizedBox(height: 8),
        Text(
          label,
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.6),
            fontSize: 12,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }

  // ── BOTTOM BUTTONS ──
  Widget _buildNextButton(Color anaRenk) {
    return SizedBox(
      width: double.infinity,
      height: 56,
      child: ElevatedButton(
        onPressed: _onNext,
        style: ElevatedButton.styleFrom(
          backgroundColor: anaRenk,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          elevation: 8,
          shadowColor: anaRenk.withValues(alpha: 0.5),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              t('onboarding_next'),
              style: const TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.bold,
                letterSpacing: 0.5,
              ),
            ),
            const SizedBox(width: 8),
            const Icon(Icons.arrow_forward, color: Colors.white),
          ],
        ),
      ),
    );
  }

  Widget _buildSignupButtons(Color anaRenk) {
    return Column(
      children: [
        // Primary: Signup/Login
        SizedBox(
          width: double.infinity,
          height: 56,
          child: ElevatedButton(
            onPressed: _navigateToLogin,
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.transparent,
              padding: EdgeInsets.zero,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              elevation: 0,
            ),
            child: Ink(
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF257bf4), Color(0xFF8A2387)],
                ),
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: anaRenk.withValues(alpha: 0.4),
                    blurRadius: 15,
                    spreadRadius: 2,
                  ),
                ],
              ),
              child: Container(
                alignment: Alignment.center,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.person_add, color: Colors.white, size: 20),
                    const SizedBox(width: 10),
                    Text(
                      t('ob_signup_btn'),
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 17,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        // Secondary: Guest
        SizedBox(
          width: double.infinity,
          height: 48,
          child: OutlinedButton(
            onPressed: _navigateAsGuest,
            style: OutlinedButton.styleFrom(
              side: BorderSide(color: Colors.white.withValues(alpha: 0.15)),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
            ),
            child: Text(
              t('ob_guest_btn'),
              style: TextStyle(
                color: Colors.white.withValues(alpha: 0.6),
                fontSize: 15,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
