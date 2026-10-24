"""
Adım 02: 360° Equirectangular Videodan Sanal Perspektif Kameralara Bölme (`step_02_reproject_360.py`).

Amaç:
    Eğer Adım 00'da videonun 360° (`is_360=True`) olduğu tespit edilmişse, her bir
    küresel (equirectangular) kareyi `VIRTUAL_VIEW_COUNT` adet doğrusal (rectilinear /
    pinhole) sanal perspektif kameraya böler ve kamera düzeneği (rig) bilgisini
    `camera_info.json` içine yazar.
    Eğer video normal bir perspektif video ise (`is_360=False`), adım durumu `skipped`
    olarak işaretlenir, kareler olduğu gibi aktarılır ve standart iğne deliği (pinhole)
    kamera bilgisi üretilir.

Mimari Önem:
    Adım 03 ve sonrası girdi kaynağından bağımsızdır (input-agnostic): asla orijinal
    videoya bakmazlar, yalnızca bu adımın ürettiği `frames_dir` ve `camera_info`
    artefaktlarını tüketirler.

Girdiler (requires):
    - `raw_frames_dir`: Adım 01 tarafından seçilen karelerin klasörü.
    - `video_metadata`: `is_360`, `width`, `height` bilgilerini içeren JSON dosyası.

Çıktılar (produces):
    - `frames_dir`: Adım 03..07 tarafından kullanılacak perspektif kareler klasörü.
    - `camera_info`: Kamera iç parametreleri (FOV, odak uzaklığı, sanal kamera açıları) JSON dosyası.

Tipik Hata Durumları ve Kodları:
    - `EMPTY_RAW_FRAMES`: Adım 01'den gelen klasörde hiç kare bulunamadı.
    - `REPROJECTION_FAILED`: Küresel-perspektif dönüşümü sırasında görüntü işleme hatası.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

from pipeline.base import PipelineContext, Step, StepResult
from pipeline.errors import StepError


def build_equirect_to_perspective_map(
    eq_w: int,
    eq_h: int,
    out_w: int,
    out_h: int,
    fov_deg: float,
    yaw_deg: float,
    pitch_deg: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    360° equirectangular bir görüntüden belirli bir `yaw` (yatay dönüş) ve `pitch`
    (dikey eğim) açısına bakan iğne deliği (pinhole) perspektif görüntü elde etmek
    için OpenCV `cv2.remap` haritalarını (`map_x`, `map_y`) ve odak uzaklığını (`focal_px`)
    hesaplar.

    Matematiksel Model:
    1. Çıktı pikseli `(u, v)` kamera uzayında 3B birim ışına `(x, y, z)` dönüştürülür.
    2. Kamera dönüş matrisi `R = R_y(yaw) @ R_x(pitch)` ile ışın dünya küresine çevrilir.
    3. Küresel koordinatlar `(lon, lat)` = `(atan2(x, z), asin(y))` hesaplanıp
       equirectangular piksel koordinatlarına eşlenir.
    """
    fov_rad = math.radians(fov_deg)
    focal = (0.5 * out_w) / math.tan(0.5 * fov_rad)

    u = np.linspace(0.5, out_w - 0.5, out_w, dtype=np.float32) - (0.5 * out_w)
    v = (0.5 * out_h) - np.linspace(0.5, out_h - 0.5, out_h, dtype=np.float32)
    grid_x, grid_y = np.meshgrid(u, v)
    grid_z = np.full_like(grid_x, focal, dtype=np.float32)

    norm = np.sqrt(grid_x**2 + grid_y**2 + grid_z**2)
    dirs = np.stack([grid_x / norm, grid_y / norm, grid_z / norm], axis=-1)

    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)

    cos_p, sin_p = math.cos(pitch), math.sin(pitch)
    cos_y, sin_y = math.cos(yaw), math.sin(yaw)

    # Önce pitch (X ekseni), sonra yaw (Y ekseni) dönüşü
    rx = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, cos_p, -sin_p],
            [0.0, sin_p, cos_p],
        ],
        dtype=np.float32,
    )
    ry = np.array(
        [
            [cos_y, 0.0, sin_y],
            [0.0, 1.0, 0.0],
            [-sin_y, 0.0, cos_y],
        ],
        dtype=np.float32,
    )
    rot = ry @ rx
    world_dirs = dirs @ rot.T

    wx = world_dirs[..., 0]
    wy = np.clip(world_dirs[..., 1], -1.0, 1.0)
    wz = world_dirs[..., 2]

    lon = np.arctan2(wx, wz)  # [-pi, pi]
    lat = np.arcsin(wy)       # [-pi/2, pi/2]

    map_x = ((lon / (2.0 * math.pi)) + 0.5) * float(eq_w)
    map_y = (0.5 - (lat / math.pi)) * float(eq_h)

    map_x = np.mod(map_x, float(eq_w)).astype(np.float32)
    map_y = np.clip(map_y, 0.0, float(eq_h - 1)).astype(np.float32)
    return map_x, map_y, float(focal)


class Step02Reproject360(Step):
    """360° kareleri sanal perspektif kameralara bölen veya normal kareleri doğrudan geçiren adım."""

    name = "reproject_360"
    order = 2
    requires = ("raw_frames_dir", "video_metadata")
    produces = ("frames_dir", "camera_info")

    def run(self, ctx: PipelineContext) -> StepResult:
        step_dir = self.prepare_step_dir(ctx)
        raw_frames_dir = ctx.get_artifact_path("raw_frames_dir")
        meta_path = ctx.get_artifact_path("video_metadata")
        meta: Dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))

        raw_files = sorted(raw_frames_dir.glob("*.jpg"))
        if not raw_files:
            raise StepError(
                step=self.step_id,
                code="EMPTY_RAW_FRAMES",
                message=f"'{raw_frames_dir}' klasöründe işlenecek kare bulunamadı.",
                hint="Adım 01'in başarıyla tamamlandığından emin olun.",
            )

        is_360 = bool(meta.get("is_360", False))
        frames_out_dir = step_dir / "frames"
        frames_out_dir.mkdir(parents=True, exist_ok=True)
        camera_info_path = step_dir / "camera_info.json"

        # ── Durum A: Normal Perspektif Video (`is_360 == False`) ──
        if not is_360:
            sample_img = cv2.imread(str(raw_files[0]))
            if sample_img is None:
                raise StepError(
                    step=self.step_id,
                    code="REPROJECTION_FAILED",
                    message=f"Örnek kare okunamadı: {raw_files[0]}",
                )
            h, w = sample_img.shape[:2]
            # Standart akıllı telefon kamerası için yaklaşık ~65° yatay FOV varsayımı
            default_fov = 65.0
            focal_px = (0.5 * w) / math.tan(0.5 * math.radians(default_fov))

            frame_entries: List[Dict[str, Any]] = []
            for idx, src_file in enumerate(raw_files):
                dst_file = frames_out_dir / src_file.name
                shutil.copy2(src_file, dst_file)
                frame_entries.append(
                    {
                        "file_name": dst_file.name,
                        "source_frame": src_file.name,
                        "camera_id": 0,
                        "yaw_deg": None,
                        "pitch_deg": 0.0,
                    }
                )

            camera_info = {
                "is_360_reprojected": False,
                "camera_model": "OPENCV",
                "width": w,
                "height": h,
                "fov_deg": default_fov,
                "fl_x": round(focal_px, 3),
                "fl_y": round(focal_px, 3),
                "cx": round(w / 2.0, 3),
                "cy": round(h / 2.0, 3),
                "virtual_view_count": 1,
                "total_frames": len(frame_entries),
                "frames": frame_entries,
            }
            camera_info_path.write_text(json.dumps(camera_info, indent=2, ensure_ascii=False), encoding="utf-8")

            ctx.logger.info(
                "Video 360° değil (is_360=False); Adım 02 'skipped' olarak işaretlendi ve %d kare doğrudan aktarıldı.",
                len(frame_entries),
            )
            return StepResult(
                status="skipped",
                artifacts={
                    "frames_dir": str(frames_out_dir),
                    "camera_info": str(camera_info_path),
                },
                metrics={
                    "is_360": False,
                    "input_frames": len(raw_files),
                    "output_frames": len(frame_entries),
                    "virtual_view_count": 1,
                },
                summary="Normal video tespit edildi; 360° yeniden izdüşüm atlandı.",
            )

        # ── Durum B: 360° Equirectangular Video (`is_360 == True`) ──
        sample_eq = cv2.imread(str(raw_files[0]))
        if sample_eq is None:
            raise StepError(
                step=self.step_id,
                code="REPROJECTION_FAILED",
                message=f"360° kare okunamadı: {raw_files[0]}",
            )

        eq_h, eq_w = sample_eq.shape[:2]
        view_count = ctx.config.virtual_view_count
        fov_deg = ctx.config.virtual_view_fov
        out_w = max(512, min(1024, eq_w // 2))
        out_h = out_w

        # Sanal kamera dönüş haritalarını (remap tablolarını) bir kez önceden hesapla (precompute)
        yaw_angles = [round((360.0 * i) / view_count, 2) for i in range(view_count)]
        precomputed_maps: List[Tuple[int, float, np.ndarray, np.ndarray, float]] = []
        for cam_idx, yaw in enumerate(yaw_angles):
            mx, my, focal_px = build_equirect_to_perspective_map(
                eq_w=eq_w,
                eq_h=eq_h,
                out_w=out_w,
                out_h=out_h,
                fov_deg=fov_deg,
                yaw_deg=yaw,
                pitch_deg=-5.0,  # Kamerayı hafifçe aşağı (-5°) eğerek zemin ve tekerlekleri kadraja al
            )
            precomputed_maps.append((cam_idx, yaw, mx, my, focal_px))

        # Toplam çıktı karesi sayısının aşırı şişmesini önlemek için anahtar kareleri örnekle
        max_source_frames = max(4, math.ceil(ctx.config.target_frame_count / view_count))
        if len(raw_files) > max_source_frames:
            idxs = np.linspace(0, len(raw_files) - 1, num=max_source_frames, dtype=int)
            selected_raw_files = [raw_files[i] for i in dict.fromkeys(idxs)]
        else:
            selected_raw_files = raw_files

        reprojected_entries: List[Dict[str, Any]] = []
        focal_val = precomputed_maps[0][4]

        for src_idx, src_file in enumerate(selected_raw_files):
            eq_img = cv2.imread(str(src_file))
            if eq_img is None:
                continue
            if eq_img.shape[:2] != (eq_h, eq_w):
                eq_img = cv2.resize(eq_img, (eq_w, eq_h))

            for cam_idx, yaw, mx, my, _ in precomputed_maps:
                persp = cv2.remap(
                    eq_img,
                    mx,
                    my,
                    interpolation=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_WRAP,
                )
                out_name = f"frame_{src_idx:03d}_cam_{cam_idx:02d}.jpg"
                out_path = frames_out_dir / out_name
                cv2.imwrite(str(out_path), persp, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                reprojected_entries.append(
                    {
                        "file_name": out_name,
                        "source_frame": src_file.name,
                        "camera_id": cam_idx,
                        "yaw_deg": yaw,
                        "pitch_deg": -5.0,
                    }
                )

        if not reprojected_entries:
            raise StepError(
                step=self.step_id,
                code="REPROJECTION_FAILED",
                message="360° karelerden hiçbir sanal perspektif görüntü üretilemedi.",
            )

        camera_info = {
            "is_360_reprojected": True,
            "camera_model": "PINHOLE",
            "width": out_w,
            "height": out_h,
            "fov_deg": fov_deg,
            "fl_x": round(focal_val, 3),
            "fl_y": round(focal_val, 3),
            "cx": round(out_w / 2.0, 3),
            "cy": round(out_h / 2.0, 3),
            "virtual_view_count": view_count,
            "yaw_angles_deg": yaw_angles,
            "total_frames": len(reprojected_entries),
            "frames": reprojected_entries,
        }
        camera_info_path.write_text(json.dumps(camera_info, indent=2, ensure_ascii=False), encoding="utf-8")

        ctx.logger.info(
            "360° yeniden izdüşüm tamamlandı: %d küresel kare x %d sanal açı = %d perspektif kare.",
            len(selected_raw_files),
            view_count,
            len(reprojected_entries),
        )

        return StepResult(
            status="done",
            artifacts={
                "frames_dir": str(frames_out_dir),
                "camera_info": str(camera_info_path),
            },
            metrics={
                "is_360": True,
                "input_frames": len(selected_raw_files),
                "virtual_view_count": view_count,
                "output_frames": len(reprojected_entries),
                "fov_deg": fov_deg,
            },
            summary=f"360° kareler {view_count} sanal kameraya bölündü (toplam {len(reprojected_entries)} kare).",
        )
