"""
ModifAI 3D Servisi — Yapılandırma ve Ortam Değişkenleri Doğrulama Modülü.

Bu modül, `.env` dosyasındaki tüm gizli anahtarları, dosya yollarını, kalite
eşiklerini (thresholds) ve model parametrelerini tek bir noktadan okur, tip
dönüşümlerini yapar ve servis başlangıcında (startup) doğrular. Hatalı bir
parametre (örneğin `MIN_REGISTRATION_RATE > 1.0` veya desteklenmeyen bir
`RECON_METHOD`) varsa, servis ayağa kalkmadan önce anlaşılır bir Türkçe hata
mesajıyla durur.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple
from dotenv import load_dotenv

# Servisin bulunduğu ana klasörü (`3Dservice/`) baz alarak `.env` dosyasını yükle.
# Çalışma dizini farklı olsa bile her zaman `3Dservice/.env` dosyasını bulabilmesi için
# `Path(__file__).resolve().parent` kullanılır.
SERVICE_ROOT_DIR: Path = Path(__file__).resolve().parent
load_dotenv(dotenv_path=SERVICE_ROOT_DIR / ".env", override=False)


def _env_str(key: str, default: str = "") -> str:
    """Ortam değişkenini metin (string) olarak okur ve kenar boşluklarını temizler."""
    val = os.getenv(key)
    return val.strip() if val is not None else default


def _env_int(key: str, default: int) -> int:
    """Ortam değişkenini tam sayı (int) olarak okur; dönüştürülemezse ValueError fırlatır."""
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ValueError(
            f"Yapılandırma hatası: '{key}' tam sayı olmalıdır, ancak '{raw}' değeri verildi."
        ) from exc


def _env_float(key: str, default: float) -> float:
    """Ortam değişkenini ondalıklı sayı (float) olarak okur."""
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ValueError(
            f"Yapılandırma hatası: '{key}' sayısal (float) olmalıdır, ancak '{raw}' değeri verildi."
        ) from exc


def _env_bool(key: str, default: bool) -> bool:
    """Ortam değişkenini mantıksal (bool) değere çevirir ('true', '1', 'yes', 'on')."""
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "evet"}


def _resolve_path(raw_path: str) -> Path:
    """
    Göreli (relative) yolları `3Dservice/` kök dizinine göre mutlak yola çevirir.
    İşletim sistemi bağımsızlığı için her yerde `pathlib.Path` kullanılır.
    """
    p = Path(raw_path)
    if not p.is_absolute():
        return (SERVICE_ROOT_DIR / p).resolve()
    return p.resolve()


@dataclass(frozen=True)
class ServiceConfig:
    """
    3D Servisinin çalışma zamanı boyunca ihtiyaç duyduğu tüm ayarları barındıran
    değiştirilemez (immutable) veri sınıfı.
    """

    # ── 1. API Sunucu ve Güvenlik Ayarları ──
    service_host: str = field(default_factory=lambda: _env_str("SERVICE_HOST", "0.0.0.0"))
    service_port: int = field(default_factory=lambda: _env_int("SERVICE_PORT", 8001))
    api_key: str = field(default_factory=lambda: _env_str("API_KEY", "ABCDEFGHIJKLMNOPRSTUVYZ123"))

    # ── 2. Mevcut Backend Entegrasyonu ve Poller Ayarları ──
    backend_url: str = field(default_factory=lambda: _env_str("BACKEND_URL", "http://localhost:8000"))
    backend_callback_url: str = field(default_factory=lambda: _env_str("BACKEND_CALLBACK_URL", ""))
    # Mevcut Backend `/scans/pending_3d` kuyruk yapısını kullandığı için varsayılan olarak
    # poller aktiftir; böylece Backend koduna dokunulmadan mevcut sistemle tam uyum sağlanır.
    enable_backend_poller: bool = field(default_factory=lambda: _env_bool("ENABLE_BACKEND_POLLER", True))
    poll_interval_seconds: int = field(default_factory=lambda: _env_int("POLL_INTERVAL_SECONDS", 5))
    backend_max_retries: int = field(default_factory=lambda: _env_int("BACKEND_MAX_RETRIES", 3))

    # ── 3. Dizin, Depolama ve Eşzamanlılık ──
    jobs_dir: Path = field(default_factory=lambda: _resolve_path(_env_str("JOBS_DIR", "./jobs")))
    outputs_dir: Path = field(default_factory=lambda: _resolve_path(_env_str("OUTPUTS_DIR", "./outputs")))
    storage_backend: str = field(default_factory=lambda: _env_str("STORAGE_BACKEND", "local").lower())
    s3_bucket_name: str = field(default_factory=lambda: _env_str("S3_BUCKET_NAME", "modifai-3d-artifacts"))
    s3_region: str = field(default_factory=lambda: _env_str("S3_REGION", "eu-central-1"))
    s3_endpoint_url: str = field(default_factory=lambda: _env_str("S3_ENDPOINT_URL", ""))
    max_concurrent_jobs: int = field(default_factory=lambda: _env_int("MAX_CONCURRENT_JOBS", 1))
    step_timeout_seconds: int = field(default_factory=lambda: _env_int("STEP_TIMEOUT_SECONDS", 1800))

    # ── 4. Adım 00: Girdi Doğrulama (Validate Input) Eşikleri ──
    max_video_mb: float = field(default_factory=lambda: _env_float("MAX_VIDEO_MB", 500.0))
    max_video_seconds: float = field(default_factory=lambda: _env_float("MAX_VIDEO_SECONDS", 180.0))
    min_video_seconds: float = field(default_factory=lambda: _env_float("MIN_VIDEO_SECONDS", 3.0))
    min_video_width: int = field(default_factory=lambda: _env_int("MIN_VIDEO_WIDTH", 640))
    min_video_height: int = field(default_factory=lambda: _env_int("MIN_VIDEO_HEIGHT", 480))
    ffmpeg_bin: str = field(default_factory=lambda: _env_str("FFMPEG_BIN", "ffmpeg"))
    ffprobe_bin: str = field(default_factory=lambda: _env_str("FFPROBE_BIN", "ffprobe"))

    # ── 5. Adım 01: Kare Çıkarma (Extract Frames) ──
    target_frame_count: int = field(default_factory=lambda: _env_int("TARGET_FRAME_COUNT", 80))
    min_frame_count: int = field(default_factory=lambda: _env_int("MIN_FRAME_COUNT", 24))
    blur_threshold: float = field(default_factory=lambda: _env_float("BLUR_THRESHOLD", 80.0))
    min_parallax_score: float = field(default_factory=lambda: _env_float("MIN_PARALLAX_SCORE", 2.5))

    # ── 6. Adım 02: 360° Video Yeniden İzdüşümü (Reproject 360) ──
    virtual_view_count: int = field(default_factory=lambda: _env_int("VIRTUAL_VIEW_COUNT", 6))
    virtual_view_fov: float = field(default_factory=lambda: _env_float("VIRTUAL_VIEW_FOV", 80.0))

    # ── 7. Adım 03: Araç Segmentasyonu (SAM 2) ──
    sam_checkpoint_path: Path = field(
        default_factory=lambda: _resolve_path(_env_str("SAM_CHECKPOINT_PATH", "./checkpoints/sam2_hiera_large.pt"))
    )
    sam_model_cfg: str = field(default_factory=lambda: _env_str("SAM_MODEL_CFG", "sam2_hiera_l.yaml"))
    min_mask_area_ratio: float = field(default_factory=lambda: _env_float("MIN_MASK_AREA_RATIO", 0.05))

    # ── 8. Adım 04: Kamera Poz Tahmini (COLMAP) ──
    colmap_bin: str = field(default_factory=lambda: _env_str("COLMAP_BIN", "colmap"))
    min_registration_rate: float = field(default_factory=lambda: _env_float("MIN_REGISTRATION_RATE", 0.70))
    pose_fallback_estimator: str = field(
        default_factory=lambda: _env_str("POSE_FALLBACK_ESTIMATOR", "none").lower()
    )

    # ── 9. Adım 05: 3B Rekonstrüksiyon (Nerfstudio) ──
    recon_method: str = field(default_factory=lambda: _env_str("RECON_METHOD", "2dgs").lower())
    train_iterations: int = field(default_factory=lambda: _env_int("TRAIN_ITERATIONS", 15000))
    device: str = field(default_factory=lambda: _env_str("DEVICE", "cuda").lower())
    min_psnr: float = field(default_factory=lambda: _env_float("MIN_PSNR", 20.0))

    # ── 10. Adım 06: Mesh Çıkarma, Hizalama ve Ölçekleme ──
    mesh_target_faces: int = field(default_factory=lambda: _env_int("MESH_TARGET_FACES", 50000))
    tsdf_voxel_length: float = field(default_factory=lambda: _env_float("TSDF_VOXEL_LENGTH", 0.015))
    tsdf_sdf_trunc: float = field(default_factory=lambda: _env_float("TSDF_SDF_TRUNC", 0.06))
    ransac_ground_dist_threshold: float = field(
        default_factory=lambda: _env_float("RANSAC_GROUND_DIST_THRESHOLD", 0.02)
    )
    # Eğer > 0.0 ise sahnenin gerçek ölçeği biliniyor demektir (`scale_known=True`).
    known_meters_per_unit: float = field(default_factory=lambda: _env_float("KNOWN_METERS_PER_UNIT", 0.0))

    # ── 11. Adım 07: UV Açma ve Doku Fırınlama ──
    texture_size: int = field(default_factory=lambda: _env_int("TEXTURE_SIZE", 2048))

    # ── 12. Adım 09: Dışa Aktarım (Export) ──
    export_formats_raw: str = field(default_factory=lambda: _env_str("EXPORT_FORMATS", "glb"))

    # ── 13. Geliştirme ve Günlükleme ──
    dev_mock_mode: bool = field(default_factory=lambda: _env_bool("DEV_MOCK_MODE", False))
    log_level: str = field(default_factory=lambda: _env_str("LOG_LEVEL", "INFO").upper())

    @property
    def export_formats(self) -> Tuple[str, ...]:
        """Dışa aktarılacak 3B model formatlarını temizlenmiş demet (tuple) olarak döndürür."""
        formats = [fmt.strip().lower() for fmt in self.export_formats_raw.split(",") if fmt.strip()]
        return tuple(dict.fromkeys(formats))

    def validate(self) -> None:
        """
        Başlangıçta tüm yapılandırma değerlerinin mantıksal tutarlılığını denetler.
        Aykırı bir durum tespit edilirse açıklayıcı Türkçe mesajla `ValueError` fırlatır.
        """
        errors: List[str] = []

        if not (1 <= self.service_port <= 65535):
            errors.append(f"SERVICE_PORT 1-65535 aralığında olmalıdır (verilen: {self.service_port}).")

        if not self.api_key:
            errors.append("API_KEY boş bırakılamaz.")

        if self.storage_backend not in {"local", "s3"}:
            errors.append(f"STORAGE_BACKEND 'local' veya 's3' olmalıdır (verilen: {self.storage_backend}).")

        if self.max_concurrent_jobs < 1:
            errors.append(f"MAX_CONCURRENT_JOBS en az 1 olmalıdır (verilen: {self.max_concurrent_jobs}).")

        if self.step_timeout_seconds < 10:
            errors.append(f"STEP_TIMEOUT_SECONDS en az 10 saniye olmalıdır (verilen: {self.step_timeout_seconds}).")

        if self.max_video_mb <= 0:
            errors.append(f"MAX_VIDEO_MB pozitif olmalıdır (verilen: {self.max_video_mb}).")

        if self.max_video_seconds <= self.min_video_seconds:
            errors.append(
                f"MAX_VIDEO_SECONDS ({self.max_video_seconds}) > MIN_VIDEO_SECONDS ({self.min_video_seconds}) olmalıdır."
            )

        if self.min_frame_count < 3:
            errors.append(f"MIN_FRAME_COUNT çoklu açı rekonstrüksiyonu için en az 3 olmalıdır (verilen: {self.min_frame_count}).")

        if self.target_frame_count < self.min_frame_count:
            errors.append(
                f"TARGET_FRAME_COUNT ({self.target_frame_count}) >= MIN_FRAME_COUNT ({self.min_frame_count}) olmalıdır."
            )

        if not (1 <= self.virtual_view_count <= 24):
            errors.append(f"VIRTUAL_VIEW_COUNT 1 ile 24 arasında olmalıdır (verilen: {self.virtual_view_count}).")

        if not (30.0 <= self.virtual_view_fov <= 140.0):
            errors.append(f"VIRTUAL_VIEW_FOV 30° ile 140° arasında olmalıdır (verilen: {self.virtual_view_fov}).")

        if not (0.05 <= self.min_registration_rate <= 1.0):
            errors.append(
                f"MIN_REGISTRATION_RATE 0.05 ile 1.0 arasında olmalıdır (verilen: {self.min_registration_rate})."
            )

        if self.recon_method not in {"splatfacto", "2dgs"}:
            errors.append(f"RECON_METHOD 'splatfacto' veya '2dgs' olmalıdır (verilen: {self.recon_method}).")

        if self.train_iterations < 100:
            errors.append(f"TRAIN_ITERATIONS en az 100 olmalıdır (verilen: {self.train_iterations}).")

        if self.device not in {"cuda", "cpu"} and not self.device.startswith("cuda:"):
            errors.append(f"DEVICE 'cuda', 'cuda:N' veya 'cpu' olmalıdır (verilen: {self.device}).")

        if self.mesh_target_faces < 500:
            errors.append(f"MESH_TARGET_FACES en az 500 olmalıdır (verilen: {self.mesh_target_faces}).")

        if self.texture_size < 256 or (self.texture_size & (self.texture_size - 1)) != 0:
            errors.append(
                f"TEXTURE_SIZE 256 veya üzeri 2'nin kuvveti (512, 1024, 2048, 4096) olmalıdır (verilen: {self.texture_size})."
            )

        if "glb" not in self.export_formats:
            errors.append(f"EXPORT_FORMATS içinde 'glb' zorunludur (verilen: {self.export_formats_raw}).")

        unsupported_formats = set(self.export_formats) - {"glb", "usdz"}
        if unsupported_formats:
            errors.append(f"Desteklenmeyen EXPORT_FORMATS değerleri: {sorted(unsupported_formats)}.")

        if errors:
            joined = "\n  - ".join(errors)
            raise ValueError(f"3D Servisi yapılandırma (.env) doğrulaması başarısız oldu:\n  - {joined}")

        # Çalışma dizinlerini güvenli bir şekilde hazırla
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)


def load_config() -> ServiceConfig:
    """Yapılandırmayı yükler, doğrular ve kullanıma hazır `ServiceConfig` nesnesini döndürür."""
    cfg = ServiceConfig()
    cfg.validate()
    return cfg


# Modül import edildiğinde tekil (singleton) yapılandırma nesnesini hazırla
settings: ServiceConfig = load_config()
