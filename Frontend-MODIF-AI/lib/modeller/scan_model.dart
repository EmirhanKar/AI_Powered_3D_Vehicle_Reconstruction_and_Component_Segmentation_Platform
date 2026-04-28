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

  Scan({
    required this.scanId,
    required this.method,
    required this.status,
    required this.createdAt,
    required this.carName,
    this.description,
    this.thumbnailUrl,
    this.modelUrl,
  });

  factory Scan.fromJson(Map<String, dynamic> json) {
    return Scan(
      scanId: json['scan_id'],
      method: json['method'] ?? '',
      status: json['status'] ?? 'pending',
      createdAt: DateTime.parse(json['created_at']),
      carName: json['car_name'] ?? '',
      description: json['description'],
      thumbnailUrl: json['thumbnail_url'],
      modelUrl: json['model_url'], // EKLENDİ
    );
  }

  bool get isCompleted => status == 'completed';
  bool get has3DModel => modelUrl != null && modelUrl!.isNotEmpty;
}