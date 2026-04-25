import 'package:flutter/material.dart';
import 'sistem_ve_dil.dart';
import 'sayfalar_ana.dart';

void main() {
  // Uygulamayı başlatan ana komut
  runApp(const ArabaApp());
}

class ArabaApp extends StatelessWidget {
  const ArabaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<String>(
      valueListenable: appLanguage,
      builder: (context, currentLang, child) {
        return MaterialApp(
          // Uygulamanın yeni karizmatik ismi
          title: 'Modif AI',

          // Sağ üstteki 'Debug' yazısını kaldırır
          debugShowCheckedModeBanner: false,

          theme: ThemeData(
            brightness: Brightness.dark,
            scaffoldBackgroundColor: const Color(0xFF0A1017),
            primaryColor: const Color(0xFF257bf4),
            fontFamily: 'Roboto',

            // Bütün uygulama genelinde yumuşak geçiş ayarı
            pageTransitionsTheme: const PageTransitionsTheme(
              builders: {
                TargetPlatform.android: FadeUpwardsPageTransitionsBuilder(),
                TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
              },
            ),
          ),

          // --- KRİTİK NOKTA: Uygulama artık Açılış Ekranı ile başlayacak ---
          home: const AcilisSayfasi(),
        );
      },
    );
  }
}