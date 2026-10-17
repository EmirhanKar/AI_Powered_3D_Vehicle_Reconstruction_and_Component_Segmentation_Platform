/// Backend Store endpoint'lerine uygun modeller.

class Paket {
  final String packageId;
  final String name;
  final String description;
  final int credits;
  final int bonusCredits;
  final double price;
  final String currency;
  final String type;
  final bool isFeatured;
  final int? durationDays;

  Paket({
    required this.packageId,
    required this.name,
    required this.description,
    required this.credits,
    required this.bonusCredits,
    required this.price,
    required this.currency,
    required this.type,
    required this.isFeatured,
    this.durationDays,
  });

  factory Paket.fromJson(Map<String, dynamic> json) {
    return Paket(
      packageId: json['package_id'] ?? '',
      name: json['name'] ?? '',
      description: json['description'] ?? '',
      credits: json['credits'] ?? 0,
      bonusCredits: json['bonus_credits'] ?? 0,
      price: (json['price'] ?? 0).toDouble(),
      currency: json['currency'] ?? 'TRY',
      type: json['type'] ?? 'credits',
      isFeatured: json['is_featured'] ?? false,
      durationDays: json['duration_days'],
    );
  }

  int get totalCredits => credits + bonusCredits;
  bool get isSubscription => type == 'subscription';
}

class SatinAlmaSonuc {
  final String message;
  final String packageName;
  final int creditsAdded;
  final int currentCredits;
  final String? subscriptionTier;
  final DateTime? subscriptionEnd;

  SatinAlmaSonuc({
    required this.message,
    required this.packageName,
    required this.creditsAdded,
    required this.currentCredits,
    this.subscriptionTier,
    this.subscriptionEnd,
  });

  factory SatinAlmaSonuc.fromJson(Map<String, dynamic> json) {
    return SatinAlmaSonuc(
      message: json['message'] ?? '',
      packageName: json['package_name'] ?? '',
      creditsAdded: json['credits_added'] ?? 0,
      currentCredits: json['current_credits'] ?? 0,
      subscriptionTier: json['subscription_tier'],
      subscriptionEnd: json['subscription_end'] != null
          ? DateTime.parse(json['subscription_end'])
          : null,
    );
  }
}

class KrediBilgisi {
  final int credits;
  final bool isPremium;
  final String subscriptionTier;
  final DateTime? subscriptionEnd;

  KrediBilgisi({
    required this.credits,
    required this.isPremium,
    required this.subscriptionTier,
    this.subscriptionEnd,
  });

  factory KrediBilgisi.fromJson(Map<String, dynamic> json) {
    return KrediBilgisi(
      credits: json['credits'] ?? 0,
      isPremium: json['is_premium'] ?? false,
      subscriptionTier: json['subscription_tier'] ?? 'free',
      subscriptionEnd: json['subscription_end'] != null
          ? DateTime.parse(json['subscription_end'])
          : null,
    );
  }
}
