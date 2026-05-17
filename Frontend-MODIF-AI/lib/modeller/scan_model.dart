class Modification {
  final String? jantName;
  final String? colorCode;
  
  Modification({this.jantName, this.colorCode});
  
  factory Modification.fromJson(Map<String, dynamic> json) {
    return Modification(
      jantName: json['jant']?['model_name'],
      colorCode: json['colors']?['color_code'],
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
  final bool isShared; // Keşfette paylaşıldı mı?
  final List<Modification> modifications;

  Scan({
    required this.scanId,
    required this.method,
    required this.status,
    required this.createdAt,
    required this.carName,
    this.description,
    this.thumbnailUrl,
    this.modelUrl,
    this.isShared = false,
    this.modifications = const [],
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
      isShared: json['is_shared'] == true,
      modifications: mods,
    );
  }

  bool get isCompleted => status == 'completed';
  bool get has3DModel => modelUrl != null && modelUrl!.isNotEmpty;
}