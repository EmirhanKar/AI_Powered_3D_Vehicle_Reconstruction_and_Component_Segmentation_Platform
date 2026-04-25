/// Backend ScanResponse schema'sına uygun tarama modeli.
class Scan {
  final int scanId;
  final String method;
  final String status;
  final DateTime createdAt;
  final String carName;
  final String? description;
  final String? thumbnailUrl;

  Scan({
    required this.scanId,
    required this.method,
    required this.status,
    required this.createdAt,
    required this.carName,
    this.description,
    this.thumbnailUrl,
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
    );
  }

  bool get isCompleted => status == 'completed';
}
