/// Backend DraftResponse schema'sına uygun taslak modeli.
class Taslak {
  final int scanId;
  final String carName;
  final String lastStep;
  final String stepLabel;
  final DateTime createdAt;
  final String method;

  Taslak({
    required this.scanId,
    required this.carName,
    required this.lastStep,
    required this.stepLabel,
    required this.createdAt,
    required this.method,
  });

  factory Taslak.fromJson(Map<String, dynamic> json) {
    return Taslak(
      scanId: json['scan_id'],
      carName: json['car_name'] ?? '',
      lastStep: json['last_step'] ?? '',
      stepLabel: json['step_label'] ?? 'Devam Et',
      createdAt: DateTime.parse(json['created_at']),
      method: json['method'] ?? '',
    );
  }
}
