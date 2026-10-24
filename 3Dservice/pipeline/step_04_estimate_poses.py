"""
Adım 04: COLMAP ile Kamera Poz Tahmini ve Seyrek (Sparse) Nokta Bulutu (`step_04_estimate_poses.py`).

Amaç:
    Kareler (`frames_dir`) üzerinde COLMAP CLI (`feature_extractor`, `exhaustive_matcher`
    veya `sequential_matcher`, `mapper` ve `model_converter`) çalıştırarak her karenin
    3B kamera pozunu (extrinsics) ve kamera iç parametrelerini (intrinsics) hesaplar.
    Sonuçları Nerfstudio / Gaussian Splatting standardı olan `transforms.json` formatına
    dönüştürür ve kayıt oranını (`registration_rate`) hesaplar.

Kritik Kalite Kapısı:
    Kayıt oranı `MIN_REGISTRATION_RATE` (varsayılan 0.70) değerinin altındaysa,
    COLMAP yeterli kareyi birbirine bağlayamamış demektir. Bu durumda öncelikle
    ileride eklenecek olan ileri-beslemeli (feed-forward: VGGT / MASt3R) yedek
    tahminci kancası (`_run_feedforward_fallback_hook`) kontrol edilir; aktif değilse
    `POSE_REGISTRATION_LOW` hatasıyla erken durulur (fail-fast).

Girdiler (requires):
    - `frames_dir`: Perspektif görüntü karelerinin klasörü.
    - `camera_info`: Kamera başlangıç bilgisi JSON dosyası.
    - `masks_dir`: Adım 03'te üretilen araç maskeleri (`transforms.json` içine `mask_path` olarak bağlanır).

Çıktılar (produces):
    - `colmap_sparse_dir`: COLMAP `cameras.txt`, `images.txt`, `points3D.txt` çıktılarının bulunduğu klasör.
    - `transforms_json`: Nerfstudio uyumlu kamera matrislerini (`transform_matrix`) içeren JSON dosyası.
    - `pose_report`: Kayıtlı kare sayısı, kayıt oranı ve 3B nokta sayısını içeren rapor.

Tipik Hata Durumları ve Kodları:
    - `COLMAP_BINARY_MISSING`: Sistemde COLMAP çalıştırılabilir dosyası bulunamadı.
    - `COLMAP_FEATURE_FAILED` / `COLMAP_MATCH_FAILED` / `COLMAP_MAPPER_FAILED`: COLMAP alt süreç hatası.
    - `POSE_REGISTRATION_LOW`: Kayıt edilen kare oranı `MIN_REGISTRATION_RATE` altında kaldı.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from pipeline.base import PipelineContext, Step, StepResult
from pipeline.errors import StepError
from pipeline.utils.subprocess_runner import run_subprocess


def _quat_to_rotmat(qw: float, qx: float, qy: float, qz: float) -> np.ndarray:
    """COLMAP birim kuaterniyonunu `(qw, qx, qy, qz)` 3x3 dönüş matrisine (`R`) çevirir."""
    n = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    if n > 0:
        qw, qx, qy, qz = qw / n, qx / n, qy / n, qz / n
    return np.array(
        [
            [1.0 - 2.0 * (qy * qy + qz * qz), 2.0 * (qx * qy - qz * qw), 2.0 * (qx * qz + qy * qw)],
            [2.0 * (qx * qy + qz * qw), 1.0 - 2.0 * (qx * qx + qz * qz), 2.0 * (qy * qz - qx * qw)],
            [2.0 * (qx * qz - qy * qw), 2.0 * (qy * qz + qx * qw), 1.0 - 2.0 * (qx * qx + qy * qy)],
        ],
        dtype=np.float64,
    )


def _colmap_world_to_cam_to_nerfstudio_c2w(rot_w2c: np.ndarray, trans_w2c: np.ndarray) -> List[List[float]]:
    """
    COLMAP'in Dünya->Kamera (`[R | t]`, OpenCV: +X sağ, +Y aşağı, +Z ileri) matrisini
    Nerfstudio / OpenGL Kamera->Dünya (`c2w`: +X sağ, +Y yukarı, -Z ileri) 4x4
    homojen matrisine dönüştürür.
    """
    rot_c2w = rot_w2c.T
    pos_c2w = -rot_c2w @ trans_w2c.reshape(3, 1)

    c2w = np.eye(4, dtype=np.float64)
    c2w[:3, :3] = rot_c2w
    c2w[:3, 3] = pos_c2w.squeeze()

    # OpenCV -> OpenGL/Nerfstudio eksen dönüşümü: Y ve Z sütunlarının işaretini ters çevir
    c2w[:3, 1:3] *= -1.0
    return [[round(float(val), 6) for val in row] for row in c2w]


class Step04EstimatePoses(Step):
    """COLMAP ile kamera pozlarını tahmin eden ve kayıt oranını denetleyen adım."""

    name = "estimate_poses"
    order = 4
    requires = ("frames_dir", "camera_info", "masks_dir")
    produces = ("colmap_sparse_dir", "transforms_json", "pose_report")

    def _run_feedforward_fallback_hook(
        self,
        frame_files: List[Path],
        camera_info: Dict[str, Any],
        ctx: PipelineContext,
    ) -> Optional[Dict[str, Any]]:
        """
        İleride eklenecek olan ileri-beslemeli (feed-forward) 3B poz tahmincileri
        (VGGT / MASt3R / DUSt3R) için temiz genişleme kancası (extension hook).

        Neden Bu Kanca Var?
        Düz beyaz/siyah araçlarda veya dokusuz otopark zeminlerinde klasik SIFT + COLMAP
        yeterli eşleşme bulamayabilir. İleride bu metodun içine VGGT veya MASt3R
        entegre edildiğinde, COLMAP kayıt oranı düşük kaldığında pipeline çökmeden
        otomatik olarak öğrenilmiş pozlara geçiş yapabilecektir. Şu an istem gereği
        yalnızca kanca bırakılmıştır ve `None` döndürür.
        """
        estimator = ctx.config.pose_fallback_estimator
        if estimator and estimator != "none":
            ctx.logger.warning(
                "Yedek poz tahmincisi ('%s') istendi ancak henüz uygulanmadı (hook).",
                estimator,
            )
        _ = (frame_files, camera_info)
        return None

    def _generate_mock_poses(
        self,
        frame_files: List[Path],
        masks_dir: Path,
        camera_info: Dict[str, Any],
        sparse_txt_dir: Path,
    ) -> Tuple[Dict[str, Any], int]:
        """
        `DEV_MOCK_MODE=true` olduğunda aracın etrafında 360° dairesel yörüngede
        merkeze bakan (look-at) gerçekçi kamera pozları ve sentetik 3B seyrek nokta
        bulutu (`cameras.txt`, `images.txt`, `points3D.txt`) üretir.
        """
        sparse_txt_dir.mkdir(parents=True, exist_ok=True)
        w = int(camera_info.get("width", 640))
        h = int(camera_info.get("height", 480))
        fl_x = float(camera_info.get("fl_x", 500.0))
        fl_y = float(camera_info.get("fl_y", 500.0))
        cx = float(camera_info.get("cx", w / 2.0))
        cy = float(camera_info.get("cy", h / 2.0))

        # 1. cameras.txt yaz
        cameras_txt = (
            "# Camera list with one line of data per camera:\n"
            "#   CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n"
            f"1 PINHOLE {w} {h} {fl_x:.4f} {fl_y:.4f} {cx:.4f} {cy:.4f}\n"
        )
        (sparse_txt_dir / "cameras.txt").write_text(cameras_txt, encoding="utf-8")

        # 2. Dairesel kamera pozları ve transforms.json girdileri oluştur
        n_frames = len(frame_files)
        radius = 3.8
        cam_height = 1.35
        transforms_frames: List[Dict[str, Any]] = []
        images_lines = ["# Image list with two lines of data per image:\n"]

        for idx, f_path in enumerate(frame_files):
            theta = (2.0 * math.pi * idx) / float(max(n_frames, 1))
            cam_pos = np.array(
                [radius * math.sin(theta), cam_height, radius * math.cos(theta)],
                dtype=np.float64,
            )
            target = np.array([0.0, 0.55, 0.0], dtype=np.float64)
            up_world = np.array([0.0, 1.0, 0.0], dtype=np.float64)

            # OpenGL/Nerfstudio c2w: -Z kameranın baktığı yön (forward), +Y yukarı, +X sağ
            forward = target - cam_pos
            forward /= np.linalg.norm(forward)
            right = np.cross(forward, up_world)
            right /= np.linalg.norm(right)
            up = np.cross(right, forward)

            c2w = np.eye(4, dtype=np.float64)
            c2w[:3, 0] = right
            c2w[:3, 1] = up
            c2w[:3, 2] = -forward
            c2w[:3, 3] = cam_pos

            mask_candidate = masks_dir / f"{f_path.stem}.png"
            transforms_frames.append(
                {
                    "file_path": str(f_path.resolve()),
                    "mask_path": str(mask_candidate.resolve()) if mask_candidate.exists() else None,
                    "transform_matrix": [[round(float(v), 6) for v in row] for row in c2w],
                }
            )
            images_lines.append(f"{idx + 1} 1.0 0.0 0.0 0.0 { -cam_pos[0]:.4f} { -cam_pos[1]:.4f} { -cam_pos[2]:.4f} 1 {f_path.name}\n\n")

        (sparse_txt_dir / "images.txt").write_text("".join(images_lines), encoding="utf-8")

        # 3. points3D.txt — Zemin düzlemi (y=0) ve araç gövdesi etrafında seyrek 3B noktalar
        rng = np.random.default_rng(seed=104)
        pts_lines = ["# 3D point list with one line of data per point:\n"]
        point_id = 1
        # Araç kutusu noktaları: X in [-0.9, 0.9], Y in [0.0, 1.4], Z in [-2.1, 2.1]
        for _ in range(250):
            px = float(rng.uniform(-0.85, 0.85))
            py = float(rng.uniform(0.05, 1.35))
            pz = float(rng.uniform(-2.05, 2.05))
            pts_lines.append(f"{point_id} {px:.4f} {py:.4f} {pz:.4f} 40 90 210 0.5\n")
            point_id += 1
        # Zemin noktaları (y ≈ 0.0)
        for _ in range(150):
            px = float(rng.uniform(-3.0, 3.0))
            py = float(rng.normal(0.0, 0.004))
            pz = float(rng.uniform(-3.0, 3.0))
            pts_lines.append(f"{point_id} {px:.4f} {py:.4f} {pz:.4f} 120 120 120 0.4\n")
            point_id += 1

        (sparse_txt_dir / "points3D.txt").write_text("".join(pts_lines), encoding="utf-8")

        transforms_data = {
            "camera_model": "OPENCV",
            "w": w,
            "h": h,
            "fl_x": fl_x,
            "fl_y": fl_y,
            "cx": cx,
            "cy": cy,
            "k1": 0.0,
            "k2": 0.0,
            "p1": 0.0,
            "p2": 0.0,
            "frames": transforms_frames,
        }
        return transforms_data, point_id - 1

    def _run_real_colmap(
        self,
        frames_dir: Path,
        frame_files: List[Path],
        masks_dir: Path,
        camera_info: Dict[str, Any],
        step_dir: Path,
        sparse_txt_dir: Path,
        ctx: PipelineContext,
    ) -> Tuple[Dict[str, Any], int]:
        """Gerçek COLMAP CLI komutlarını sırasıyla çalıştırır ve çıktıyı ayrıştırır."""
        db_path = step_dir / "database.db"
        sparse_bin_root = step_dir / "sparse_bin"
        sparse_bin_root.mkdir(parents=True, exist_ok=True)
        sparse_txt_dir.mkdir(parents=True, exist_ok=True)

        colmap_bin = ctx.config.colmap_bin
        timeout = ctx.config.step_timeout_seconds

        # 1. SIFT Özellik Çıkarma (Feature Extraction)
        # Not: Tek bir videodan gelen kareler aynı kamerayı paylaştığı için `single_camera=1`
        # verilmesi COLMAP'in odak uzaklığı (focal length) sapmasını önler.
        single_cam = "0" if camera_info.get("is_360_reprojected") else "1"
        run_subprocess(
            command=[
                colmap_bin,
                "feature_extractor",
                "--database_path",
                str(db_path),
                "--image_path",
                str(frames_dir),
                "--ImageReader.camera_model",
                "OPENCV",
                "--ImageReader.single_camera",
                single_cam,
            ],
            step_name=self.step_id,
            error_code="COLMAP_FEATURE_FAILED",
            error_message="COLMAP özellik çıkarma (feature_extractor) aşaması başarısız oldu",
            timeout_seconds=timeout,
            logger=ctx.logger,
        )

        # 2. Özellik Eşleştirme (Exhaustive Matcher — <=120 karelik araç videolarında döngü kapatmayı
        # [loop closure] garantilediği için sequential_matcher'dan çok daha güvenilirdir)
        run_subprocess(
            command=[
                colmap_bin,
                "exhaustive_matcher",
                "--database_path",
                str(db_path),
            ],
            step_name=self.step_id,
            error_code="COLMAP_MATCH_FAILED",
            error_message="COLMAP özellik eşleştirme (exhaustive_matcher) aşaması başarısız oldu",
            timeout_seconds=timeout,
            logger=ctx.logger,
        )

        # 3. Artımlı SfM Haritalama (Mapper)
        run_subprocess(
            command=[
                colmap_bin,
                "mapper",
                "--database_path",
                str(db_path),
                "--image_path",
                str(frames_dir),
                "--output_path",
                str(sparse_bin_root),
            ],
            step_name=self.step_id,
            error_code="COLMAP_MAPPER_FAILED",
            error_message="COLMAP seyrek haritalama (mapper) aşaması başarısız oldu",
            hint="Aracın etrafında kopukluk olmadan ve yeterli arka plan detayı görünecek şekilde çekim yapın.",
            timeout_seconds=timeout,
            logger=ctx.logger,
        )

        # COLMAP birden fazla alt model (0, 1, ...) üretebilir; en büyük olan 0 numaralı modeli al
        model_0_dir = sparse_bin_root / "0"
        if not model_0_dir.exists():
            subdirs = sorted([d for d in sparse_bin_root.iterdir() if d.is_dir()])
            if not subdirs:
                raise StepError(
                    step=self.step_id,
                    code="COLMAP_MAPPER_FAILED",
                    message="COLMAP hiçbir 3B seyrek model üretemedi (sparse/0 klasörü oluşmadı).",
                    hint="Kareler arasında yeterli örtüşme (overlap) yok; aracın etrafında daha yavaş yürüyün.",
                )
            model_0_dir = subdirs[0]

        # 4. İkili (.bin) modeli kolay okunabilir metin (.txt) formatına dönüştür
        run_subprocess(
            command=[
                colmap_bin,
                "model_converter",
                "--input_path",
                str(model_0_dir),
                "--output_path",
                str(sparse_txt_dir),
                "--output_type",
                "TXT",
            ],
            step_name=self.step_id,
            error_code="COLMAP_CONVERTER_FAILED",
            error_message="COLMAP model_converter aşaması başarısız oldu",
            timeout_seconds=120,
            logger=ctx.logger,
        )

        # cameras.txt ayrıştır
        w = int(camera_info.get("width", 640))
        h = int(camera_info.get("height", 480))
        fl_x = float(camera_info.get("fl_x", 500.0))
        fl_y = float(camera_info.get("fl_y", 500.0))
        cx = float(camera_info.get("cx", w / 2.0))
        cy = float(camera_info.get("cy", h / 2.0))

        cam_txt_file = sparse_txt_dir / "cameras.txt"
        if cam_txt_file.exists():
            for line in cam_txt_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 8:
                    w = int(parts[2])
                    h = int(parts[3])
                    fl_x = float(parts[4])
                    fl_y = float(parts[5])
                    cx = float(parts[6])
                    cy = float(parts[7])
                    break

        # images.txt ayrıştır (her görüntü 2 satırdır: 1. satır poz, 2. satır 2D noktalar)
        img_txt_file = sparse_txt_dir / "images.txt"
        img_lines = [
            ln.strip()
            for ln in img_txt_file.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]

        frame_lookup = {f.name: f for f in frame_files}
        transforms_frames: List[Dict[str, Any]] = []

        for idx in range(0, len(img_lines), 2):
            parts = img_lines[idx].split()
            if len(parts) < 10:
                continue
            qw, qx, qy, qz = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            tx, ty, tz = float(parts[5]), float(parts[6]), float(parts[7])
            img_name = " ".join(parts[9:])

            f_path = frame_lookup.get(img_name, frames_dir / img_name)
            mask_candidate = masks_dir / f"{f_path.stem}.png"

            rot_w2c = _quat_to_rotmat(qw, qx, qy, qz)
            c2w_list = _colmap_world_to_cam_to_nerfstudio_c2w(rot_w2c, np.array([tx, ty, tz]))
            transforms_frames.append(
                {
                    "file_path": str(f_path.resolve()),
                    "mask_path": str(mask_candidate.resolve()) if mask_candidate.exists() else None,
                    "transform_matrix": c2w_list,
                }
            )

        pts_txt_file = sparse_txt_dir / "points3D.txt"
        num_points = 0
        if pts_txt_file.exists():
            num_points = sum(
                1
                for ln in pts_txt_file.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            )

        transforms_data = {
            "camera_model": "OPENCV",
            "w": w,
            "h": h,
            "fl_x": fl_x,
            "fl_y": fl_y,
            "cx": cx,
            "cy": cy,
            "k1": 0.0,
            "k2": 0.0,
            "p1": 0.0,
            "p2": 0.0,
            "frames": transforms_frames,
        }
        return transforms_data, num_points

    def run(self, ctx: PipelineContext) -> StepResult:
        step_dir = self.prepare_step_dir(ctx)
        frames_dir = ctx.get_artifact_path("frames_dir")
        camera_info_path = ctx.get_artifact_path("camera_info")
        masks_dir = ctx.get_artifact_path("masks_dir")

        camera_info: Dict[str, Any] = json.loads(camera_info_path.read_text(encoding="utf-8"))
        frame_files = sorted(frames_dir.glob("*.jpg")) + sorted(frames_dir.glob("*.png"))
        total_input_frames = len(frame_files)

        if total_input_frames == 0:
            raise StepError(
                step=self.step_id,
                code="NO_FRAMES_FOR_POSE",
                message="Poz tahmini için girdi karesi bulunamadı.",
            )

        sparse_txt_dir = step_dir / "sparse"
        transforms_path = step_dir / "transforms.json"
        pose_report_path = step_dir / "pose_report.json"

        if ctx.config.dev_mock_mode:
            ctx.logger.info("DEV_MOCK_MODE aktif: %d kare için dairesel COLMAP kamera pozları üretiliyor.", total_input_frames)
            transforms_data, num_points3d = self._generate_mock_poses(
                frame_files=frame_files,
                masks_dir=masks_dir,
                camera_info=camera_info,
                sparse_txt_dir=sparse_txt_dir,
            )
        else:
            transforms_data, num_points3d = self._run_real_colmap(
                frames_dir=frames_dir,
                frame_files=frame_files,
                masks_dir=masks_dir,
                camera_info=camera_info,
                step_dir=step_dir,
                sparse_txt_dir=sparse_txt_dir,
                ctx=ctx,
            )

        registered_count = len(transforms_data.get("frames", []))
        registration_rate = float(registered_count) / float(max(total_input_frames, 1))

        # Eğer kayıt oranı eşik değerinin altındaysa önce yedek (fallback) kancayı dene
        if registration_rate < ctx.config.min_registration_rate:
            fallback_transforms = self._run_feedforward_fallback_hook(frame_files, camera_info, ctx)
            if fallback_transforms is not None:
                transforms_data = fallback_transforms
                registered_count = len(transforms_data.get("frames", []))
                registration_rate = float(registered_count) / float(max(total_input_frames, 1))

        # Kalite Kapısı: Yeterli kare kayıt olmadıysa 3B rekonstrüksiyon bozuk çıkacağından erken dur
        if registration_rate < ctx.config.min_registration_rate:
            raise StepError(
                step=self.step_id,
                code="POSE_REGISTRATION_LOW",
                message=(
                    f"Kamera pozlarının yalnızca {registered_count}/{total_input_frames} tanesi "
                    f"(%{registration_rate * 100:.1f}) hesaplanabildi "
                    f"(minimum %{ctx.config.min_registration_rate * 100:.0f} gerekli)."
                ),
                hint=(
                    "Aracın etrafında kopukluk olmadan, ani kamera dönüşlerinden kaçınarak ve "
                    "arka planda sabit nesnelerin bulunduğu bir ortamda tam bir tur yürüyün."
                ),
                details={
                    "registered_frames": registered_count,
                    "total_frames": total_input_frames,
                    "registration_rate": round(registration_rate, 4),
                    "min_registration_rate": ctx.config.min_registration_rate,
                },
            )

        transforms_path.write_text(json.dumps(transforms_data, indent=2, ensure_ascii=False), encoding="utf-8")

        report_data = {
            "total_frames": total_input_frames,
            "registered_frames": registered_count,
            "registration_rate": round(registration_rate, 4),
            "sparse_points_count": num_points3d,
            "estimator": "mock_colmap" if ctx.config.dev_mock_mode else "colmap",
        }
        pose_report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")

        ctx.logger.info(
            "Poz tahmini tamamlandı: %d/%d kare kayıt edildi (oran=%.1f%%, 3B nokta=%d).",
            registered_count,
            total_input_frames,
            registration_rate * 100.0,
            num_points3d,
        )

        return StepResult(
            status="done",
            artifacts={
                "colmap_sparse_dir": str(sparse_txt_dir),
                "transforms_json": str(transforms_path),
                "pose_report": str(pose_report_path),
            },
            metrics={
                "total_frames": total_input_frames,
                "registered_frames": registered_count,
                "registration_rate": round(registration_rate, 4),
                "sparse_points_count": num_points3d,
            },
            summary=f"{registered_count}/{total_input_frames} kamera pozu hesaplandı (%{registration_rate * 100:.1f}).",
        )
