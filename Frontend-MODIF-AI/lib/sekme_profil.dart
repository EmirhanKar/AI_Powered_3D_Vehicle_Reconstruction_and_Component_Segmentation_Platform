import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'sistem_ve_dil.dart';
import 'modeller/kullanici_model.dart';
import 'servisler/api_servisi.dart';
import 'servisler/auth_servisi.dart';
import 'sayfalar_ana.dart';

class SekmeProfil extends StatelessWidget {
  final Kullanici? kullanici;
  final int kredi;
  final Map<String, dynamic> rankDetails;
  final VoidCallback onRanksTap;
  final VoidCallback onTopUpTap;
  final VoidCallback onLangTap;
  final VoidCallback onProfileUpdated;

  const SekmeProfil({
    super.key,
    required this.kullanici,
    required this.kredi,
    required this.rankDetails,
    required this.onRanksTap,
    required this.onTopUpTap,
    required this.onLangTap,
    required this.onProfileUpdated,
  });

  @override
  Widget build(BuildContext context) {
    final Color anaRenk = const Color(0xFF257bf4);
    final Color koyuYuzey = const Color(0xFF182434);
    final profilUrl = ApiServisi.buildImageUrl(kullanici?.profilImageUrl);
    final renderCount = kullanici?.renderImage ?? 0;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24.0),
      child: Column(children: [
        const SizedBox(height: 80),
        Center(child: Column(children: [
          GestureDetector(
            onTap: () => _profilFotoSec(context),
            child: Stack(children: [
              Container(width: 100, height: 100, decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: anaRenk, width: 3), image: profilUrl != null ? DecorationImage(image: NetworkImage(profilUrl), fit: BoxFit.cover) : null, color: profilUrl == null ? koyuYuzey : null), child: profilUrl == null ? const Icon(Icons.person, color: Colors.grey, size: 48) : null),
              Positioned(bottom: 0, right: 0, child: Container(padding: const EdgeInsets.all(6), decoration: BoxDecoration(color: anaRenk, shape: BoxShape.circle), child: const Icon(Icons.edit, color: Colors.white, size: 16))),
            ]),
          ),
          const SizedBox(height: 16),
          Text(kullanici?.fullName ?? '...', style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold)),
          Text(kullanici?.email ?? '', style: const TextStyle(color: Colors.grey, fontSize: 12)),
          const SizedBox(height: 12),
          GestureDetector(
            onTap: onRanksTap,
            child: Container(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8), decoration: BoxDecoration(color: (rankDetails['color'] as Color).withOpacity(0.1), border: Border.all(color: rankDetails['color']), borderRadius: BorderRadius.circular(20)),
              child: Row(mainAxisSize: MainAxisSize.min, children: [Text(rankDetails['icon'], style: const TextStyle(fontSize: 18)), const SizedBox(width: 8), Text('${rankDetails['level']}. ${t('level')} ${rankDetails['name']}', style: TextStyle(color: rankDetails['color'], fontWeight: FontWeight.bold, fontSize: 16))]),
            ),
          ),
          const SizedBox(height: 20),
          SizedBox(width: 220, child: Column(children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Text('${t('total_renders')}$renderCount', style: premiumNumberStyle.copyWith(color: Colors.grey, fontSize: 12)),
              Text(rankDetails['level'] == 5 ? t('max_level') : '${rankDetails['next']} ${t('target')}', style: const TextStyle(color: Colors.grey, fontSize: 12)),
            ]),
            const SizedBox(height: 8),
            ClipRRect(borderRadius: BorderRadius.circular(10), child: LinearProgressIndicator(value: (rankDetails['progress'] as double).clamp(0.0, 1.0), minHeight: 8, backgroundColor: Colors.white.withOpacity(0.05), valueColor: AlwaysStoppedAnimation<Color>(rankDetails['color']))),
          ])),
        ])),
        const SizedBox(height: 40),
        Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(color: anaRenk.withOpacity(0.1), borderRadius: BorderRadius.circular(16), border: Border.all(color: anaRenk.withOpacity(0.3))),
          child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(t('active_balance'), style: const TextStyle(color: Colors.grey, fontSize: 14)),
              const SizedBox(height: 4),
              Row(children: [const Icon(Icons.diamond, color: Colors.blueAccent, size: 24), const SizedBox(width: 8), Text('$kredi', style: premiumNumberStyle.copyWith(color: Colors.white, fontSize: 32)), Text(' ${t('credit')}', style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 16))]),
            ]),
            ElevatedButton(onPressed: onTopUpTap, style: ElevatedButton.styleFrom(backgroundColor: anaRenk, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))), child: Text(t('top_up'), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
          ]),
        ),
        const SizedBox(height: 32),
        Align(alignment: Alignment.centerLeft, child: Text(t('settings'), style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold))),
        const SizedBox(height: 12),
        _profilMenuElemani(koyuYuzey, t('lang_select'), onTap: onLangTap),
        const SizedBox(height: 12),
        _profilMenuElemani(koyuYuzey, t('edit_user'), onTap: () => _profilDuzenleDiyalogu(context)),
        const SizedBox(height: 12),
        _profilMenuElemani(koyuYuzey, t('logout'), isDestructive: true, onTap: () => _cikisYap(context)),
        const SizedBox(height: 100),
      ]),
    );
  }

  void _profilFotoSec(BuildContext context) async {
    HapticFeedback.lightImpact();
    final ImagePicker picker = ImagePicker();
    final XFile? photo = await picker.pickImage(source: ImageSource.gallery, maxWidth: 800, maxHeight: 800);
    if (photo == null) return;
    try {
      await ApiServisi().profilFotoYukle(photo);
      onProfileUpdated();
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Profil fotoğrafı güncellendi!'), backgroundColor: Colors.green, behavior: SnackBarBehavior.floating));
    } catch (e) {
      if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString()), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating));
    }
  }

  void _profilDuzenleDiyalogu(BuildContext context) {
    final nameCtrl = TextEditingController(text: kullanici?.name ?? '');
    final surnameCtrl = TextEditingController(text: kullanici?.surname ?? '');
    final emailCtrl = TextEditingController(text: kullanici?.email ?? '');
    showDialog(context: context, builder: (ctx) {
      return AlertDialog(
        backgroundColor: const Color(0xFF182434),
        title: Text(t('edit_user'), style: const TextStyle(color: Colors.white)),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(controller: nameCtrl, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'Ad', labelStyle: TextStyle(color: Colors.grey))),
          TextField(controller: surnameCtrl, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'Soyad', labelStyle: TextStyle(color: Colors.grey))),
          TextField(controller: emailCtrl, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'E-posta', labelStyle: TextStyle(color: Colors.grey))),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('İptal', style: TextStyle(color: Colors.grey))),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF257bf4)),
            onPressed: () async {
              try {
                await ApiServisi().profilGuncelle(name: nameCtrl.text, surname: surnameCtrl.text, email: emailCtrl.text);
                onProfileUpdated();
                if (ctx.mounted) Navigator.pop(ctx);
              } catch (e) {
                if (ctx.mounted) ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text(e.toString()), backgroundColor: Colors.redAccent));
              }
            },
            child: const Text('Kaydet', style: TextStyle(color: Colors.white)),
          ),
        ],
      );
    });
  }

  void _cikisYap(BuildContext context) async {
    HapticFeedback.mediumImpact();
    await AuthServisi().logout();
    if (context.mounted) {
      Navigator.pushAndRemoveUntil(context, MaterialPageRoute(builder: (context) => const GirisSayfasi()), (route) => false);
    }
  }

  Widget _profilMenuElemani(Color koyuYuzey, String baslik, {bool isDestructive = false, VoidCallback? onTap}) {
    return Container(
      decoration: BoxDecoration(color: koyuYuzey, borderRadius: BorderRadius.circular(12)),
      child: ListTile(title: Text(baslik, style: TextStyle(color: isDestructive ? Colors.redAccent : Colors.white, fontWeight: FontWeight.w500)), trailing: const Icon(Icons.chevron_right, color: Colors.grey), onTap: onTap ?? () { HapticFeedback.lightImpact(); }),
    );
  }
}