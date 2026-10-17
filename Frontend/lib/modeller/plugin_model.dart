/// Backend JantResponse ve ColorResponse schema'larına uygun modeller.

class JantModel {
  final int jantId;
  final String modelName;
  final String category;
  final String? imageUrl;
  final String? lokalAsset; // Lokal asset yolu (backend boşken fallback)

  JantModel({
    required this.jantId,
    required this.modelName,
    required this.category,
    this.imageUrl,
    this.lokalAsset,
  });

  factory JantModel.fromJson(Map<String, dynamic> json) {
    return JantModel(
      jantId: json['jant_id'],
      modelName: json['model_name'] ?? '',
      category: json['category'] ?? '',
      imageUrl: json['image_url'],
    );
  }

  /// Lokal asset mi yoksa network image mı kullanılacak?
  bool get isLokal => lokalAsset != null && (imageUrl == null || imageUrl!.isEmpty);
}

class RenkModel {
  final int colorId;
  final String colorCode;

  RenkModel({
    required this.colorId,
    required this.colorCode,
  });

  factory RenkModel.fromJson(Map<String, dynamic> json) {
    return RenkModel(
      colorId: json['color_id'],
      colorCode: json['color_code'] ?? '#FFFFFF',
    );
  }

  /// Hex string'den Flutter Color nesnesine çevirir.
  int get colorValue {
    String hex = colorCode.replaceAll('#', '');
    if (hex.length == 6) hex = 'FF$hex';
    return int.parse(hex, radix: 16);
  }
}
