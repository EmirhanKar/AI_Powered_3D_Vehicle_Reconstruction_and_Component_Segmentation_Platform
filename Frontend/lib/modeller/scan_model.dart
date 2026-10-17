class Modification {
  final int? modificationId;
  final String? jantName;
  final String? colorCode;
  final String? paintLocation;
  
  Modification({this.modificationId, this.jantName, this.colorCode, this.paintLocation});
  
  factory Modification.fromJson(Map<String, dynamic> json) {
    return Modification(
      modificationId: json['modification_id'],
      jantName: json['jant']?['model_name'],
      colorCode: json['colors']?['color_code'],
      paintLocation: json['paint_location'],
    );
  }
}

/// Backend ScanResponse schema'sına uygun tarama modeli.
class Scan {
  final int scanId;
  final String method;
  final String status;
  final DateTime createdAt;
  final String carName;
  final String? description;
  final String? thumbnailUrl;
  final String? modelUrl; // 3D model hazırsa dolu gelir
  final String? imageUrl; // 2D işlenmiş görsel hazırsa dolu gelir
  final bool isShared; // Keşfette paylaşıldı mı?
  final List<Modification> modifications;

  final int progress;

  // Yeni akış alanları
  final bool canModify;       // Model hazır mı? Modifikasyon butonu gösterilecek mi?
  final bool hasModification; // Modifikasyon zaten uygulanmış mı?

  Scan({
    required this.scanId,
    required this.method,
    required this.status,
    required this.createdAt,
    required this.carName,
    this.description,
    this.thumbnailUrl,
    this.modelUrl,
    this.imageUrl,
    this.isShared = false,
    this.modifications = const [],
    this.progress = 0,
    this.canModify = false,
    this.hasModification = false,
  });

  factory Scan.fromJson(Map<String, dynamic> json) {
    List<Modification> mods = [];
    if (json['modifications'] != null) {
      mods = (json['modifications'] as List).map((m) => Modification.fromJson(m)).toList();
    }

    return Scan(
      scanId: json['scan_id'],
      method: json['method'] ?? '',
      status: json['status'] ?? 'pending',
      createdAt: DateTime.parse(json['created_at']),
      carName: json['car_name'] ?? '',
      description: json['description'],
      thumbnailUrl: json['thumbnail_url'],
      modelUrl: json['model_url'],
      imageUrl: json['image_url'],
      isShared: json['is_shared'] == true,
      modifications: mods,
      progress: json['progress'] ?? 0,
      canModify: json['can_modify'] == true,
      hasModification: json['has_modification'] == true,
    );
  }

  bool get isCompleted => status == 'completed';
  bool get has3DModel => modelUrl != null && modelUrl!.isNotEmpty;
  bool get is3D => method == '3d' || method == '3d_single';
}