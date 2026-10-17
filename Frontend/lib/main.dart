import 'package:flutter/material.dart';
import 'sistem_ve_dil.dart';
import 'sayfalar_ana.dart';
import 'global_render_banner.dart';

final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await temaYukle();
  runApp(const ArabaApp());
}


class ArabaApp extends StatelessWidget {
  const ArabaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<String>(
      valueListenable: appLanguage,
      builder: (context, currentLang, child) {
        return ValueListenableBuilder<bool>(
          valueListenable: isDarkMode,
          builder: (context, dark, child) {
            return MaterialApp(
              navigatorKey: navigatorKey,
              title: 'Modif AI',
              debugShowCheckedModeBanner: false,
              builder: (context, child) {
                return Stack(
                  children: [
                    if (child != null) child,
                    const GlobalRenderBanner(),
                  ],
                );
              },

              theme: ThemeData(
                brightness: Brightness.light,
                scaffoldBackgroundColor: const Color(0xFFF5F7FA),
                primaryColor: const Color(0xFF257bf4),
                fontFamily: 'Roboto',
                colorScheme: ColorScheme.light(
                  primary: const Color(0xFF257bf4),
                  surface: Colors.white,
                ),
                pageTransitionsTheme: const PageTransitionsTheme(
                  builders: {
                    TargetPlatform.android: FadeUpwardsPageTransitionsBuilder(),
                    TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
                  },
                ),
              ),

              darkTheme: ThemeData(
                brightness: Brightness.dark,
                scaffoldBackgroundColor: const Color(0xFF0A1017),
                primaryColor: const Color(0xFF257bf4),
                fontFamily: 'Roboto',
                colorScheme: ColorScheme.dark(
                  primary: const Color(0xFF257bf4),
                  surface: const Color(0xFF182434),
                ),
                pageTransitionsTheme: const PageTransitionsTheme(
                  builders: {
                    TargetPlatform.android: FadeUpwardsPageTransitionsBuilder(),
                    TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
                  },
                ),
              ),

              themeMode: dark ? ThemeMode.dark : ThemeMode.light,

              home: const AcilisSayfasi(),
            );
          },
        );
      },
    );
  }
}