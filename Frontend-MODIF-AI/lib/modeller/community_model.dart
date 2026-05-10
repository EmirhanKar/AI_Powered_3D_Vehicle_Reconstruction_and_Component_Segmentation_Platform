/// Backend FeedItemResponse ve CommentResponse schema'larına uygun modeller.

class FeedItem {
  final int scanId;
  final String carName;
  final String? thumbnailUrl;
  int likeCount;
  int commentCount;
  bool isLiked;
  final String ownerName;

  FeedItem({
    required this.scanId,
    required this.carName,
    this.thumbnailUrl,
    this.likeCount = 0,
    this.commentCount = 0,
    this.isLiked = false,
    required this.ownerName,
  });

  factory FeedItem.fromJson(Map<String, dynamic> json) {
    return FeedItem(
      scanId: json['scan_id'],
      carName: json['car_name'] ?? '',
      thumbnailUrl: json['thumbnail_url'],
      likeCount: json['like_count'] ?? 0,
      commentCount: json['comment_count'] ?? 0,
      isLiked: json['is_liked'] ?? false,
      ownerName: json['owner_name'] ?? 'Bilinmiyor',
    );
  }
}

class Yorum {
  final int commentId;
  final int scanId;
  final int userId;
  final String userName;
  final String content;
  int likeCount;
  bool isLiked;
  final DateTime createdAt;

  Yorum({
    required this.commentId,
    required this.scanId,
    required this.userId,
    required this.userName,
    required this.content,
    this.likeCount = 0,
    this.isLiked = false,
    required this.createdAt,
  });

  factory Yorum.fromJson(Map<String, dynamic> json) {
    return Yorum(
      commentId: json['comment_id'],
      scanId: json['scan_id'],
      userId: json['user_id'],
      userName: json['user_name'] ?? 'Kullanıcı',
      content: json['content'] ?? '',
      likeCount: json['like_count'] ?? 0,
      isLiked: json['is_liked'] ?? false,
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

