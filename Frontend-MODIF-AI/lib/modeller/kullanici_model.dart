/// Backend UserResponse schema'sına uygun kullanıcı modeli.
class Kullanici {
  final int userId;
  final String name;
  final String surname;
  final String email;
  final String? profilImageUrl;
  final int userCredi;
  final int createImage;
  final int renderImage;

  Kullanici({
    required this.userId,
    required this.name,
    required this.surname,
    required this.email,
    this.profilImageUrl,
    this.userCredi = 0,
    this.createImage = 0,
    this.renderImage = 0,
  });

  factory Kullanici.fromJson(Map<String, dynamic> json) {
    return Kullanici(
      userId: json['user_id'],
      name: json['name'] ?? '',
      surname: json['surname'] ?? '',
      email: json['email'] ?? '',
      profilImageUrl: json['profil_image_url'] ?? json['profile_image_url'],
      userCredi: json['user_credi'] ?? 0,
      createImage: json['create_image'] ?? 0,
      renderImage: json['render_image'] ?? 0,
    );
  }

  String get fullName => '$name $surname';
}
