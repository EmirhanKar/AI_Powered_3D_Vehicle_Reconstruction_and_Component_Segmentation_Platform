class Araba {
  final int id;
  final String marka;
  final String model;
  final String imageUrl;

  Araba({required this.id, required this.marka, required this.model, required this.imageUrl});

  // FastAPI'den gelen JSON paketini Dart diline (Araba nesnesine) çeviren sihirli fabrika
  factory Araba.fromJson(Map<String, dynamic> json) {
    return Araba(
      id: json['id'],
      marka: json['marka'],
      model: json['model'],
      imageUrl: json['image_url'] ?? '', // Eğer resim yoksa boş string ata
    );
  }
}