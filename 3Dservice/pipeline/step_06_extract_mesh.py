"""
Adım 06: Mesh Çıkarma, Zemin Kesimi (RANSAC), Eksen Hizalama (PCA) ve Ölçekleme (`step_06_extract_mesh.py`).

Amaç:
    Adım 05'te üretilen 3B temsilden (TSDF / Poisson veya yoğun yüzey) üçgen ağ
    (mesh) çıkarır ve aşağıdaki geometrik işlemleri sırasıyla uygular:
    1. Havada asılı gürültü parçalarını (floaters) temizler ve yalnızca en büyük
       bağlı bileşeni (largest connected component — araç gövdesi) tutar.
    2. Alt bölgedeki noktalar üzerinden **RANSAC** ile zemin düzlemini (`ax + by + cz + d = 0`)
       bulur, zemini keser ve zemin normalini **+Y (Yukarı)** eksenine hizalar.
    3. Yatay düzlemde (X-Z) **PCA (Temel Bileşen Analizi)** çalıştırarak aracın
       en uzun eksenini **Z eksenine** hizalar. Kaput/tavan yükseklik profili
       asimetrisinden ön/arka yönünü belirler (`+Z` = araç önü). Ön/arka simetrisi
       yüksekse (örn. sedan/simetrik profil) `front_confidence` değerini düşük
       işaretler ve bunu hem logda hem de metriklerde raporlar.
    4. Modeli yatayda `X=0, Z=0` merkezine alır, tekerlek tabanını tam olarak
       **`y = 0.0` (zemin referanslı)** düzlemine oturtur (`(0,0,0)` kütle merkezi
       kullanılmaz).
    5. Ölçek referansı (`KNOWN_METERS_PER_UNIT > 0`) biliniyorsa doğrudan metre
       cinsinden ölçekler (`scale_known=True`, `meters_per_unit=1.0`); bilinmiyorsa
       birim küpe normalize ederken tahmini gerçek ölçeği `meters_per_unit` içinde
       saklar (`scale_known=False`).
    6. Delikleri kapatır ve yüz sayısını `MESH_TARGET_FACES` hedefine indirger (decimation).

Girdiler (requires):
    - `radiance_field_model`: Adım 05'ten gelen 3B sahne/nokta bulutu/config dosyası.
    - `transforms_json`: Kamera pozları.
    - `masks_dir`: Araç maskeleri.

Çıktılar (produces):
    - `clean_mesh_ply`: Hizalanmış, temizlenmiş ve ölçeklenmiş `.ply` mesh dosyası.
    - `mesh_metrics`: Yüz sayısı, su geçirmezlik (`is_watertight`), sınır kutusu (`bbox`),
      `meters_per_unit`, `scale_known` ve `front_confidence` değerlerini içeren JSON dosyası.

Tipik Hata Durumları ve Kodları:
    - `DEPTH_RENDER_FAILED` / `TSDF_FUSION_FAILED`: Nerfstudio mesh çıkarımı başarısız oldu.
    - `EMPTY_MESH`: Temizleme sonrasında geçerli üçgen yüz kalmadı.
    - `GROUND_REMOVAL_FAILED` / `DECIMATION_FAILED`: Geometri işleme hatası.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import trimesh

from pipeline.base import PipelineContext, Step, StepResult
from pipeline.errors import StepError
from pipeline.utils.subprocess_runner import run_subprocess


def fit_ground_plane_ransac(
    vertices: np.ndarray,
    distance_threshold: float = 0.02,
    num_iterations: int = 250,
) -> Tuple[np.ndarray, float, np.ndarray]:
    """
    Nokta bulutunun alt %25'lik dilimindeki aday noktalar üzerinde RANSAC
    çalıştırarak zemin düzlemini (`normal`, `d`) ve zemin içi (inlier) maskesini bulur.

    Neden Alt %25 Dilim Kullanılır?
    Tüm araç üzerinde doğrudan RANSAC çalıştırılırsa aracın yan kapı sacı veya
    tavanı en büyük düzlem olarak seçilebilir. Yalnızca dikey eksende (Y) en altta
    kalan %25'lik dilim (asfalt + tekerlek altları) aday havuzu yapıldığında RANSAC
    her zaman gerçek yer düzlemini yakalar.
    """
    rng = np.random.default_rng(seed=306)
    y_vals = vertices[:, 1]
    y_cutoff = np.percentile(y_vals, 25.0)
    bottom_candidates = vertices[y_vals <= y_cutoff]

    if len(bottom_candidates) < 10:
        bottom_candidates = vertices

    best_normal = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    best_d = -float(np.min(y_vals))
    best_inliers_count = -1

    n_cand = len(bottom_candidates)
    for _ in range(num_iterations):
        if n_cand < 3:
            break
        sample_idx = rng.choice(n_cand, size=3, replace=False)
        p0, p1, p2 = bottom_candidates[sample_idx]
        v1 = p1 - p0
        v2 = p2 - p0
        normal = np.cross(v1, v2)
        norm_len = float(np.linalg.norm(normal))
        if norm_len < 1e-8:
            continue
        normal = normal / norm_len

        # Normalin her zaman yukarı (+Y yarı-uzayına) bakmasını sağla
        if normal[1] < 0:
            normal = -normal

        # Dikey eksenden 45 dereceden fazla sapan düzlemler duvar/kaportadır, zemin olamaz
        if normal[1] < 0.70:
            continue

        d = -float(np.dot(normal, p0))
        dists = np.abs(bottom_candidates @ normal + d)
        inliers = int(np.count_nonzero(dists <= distance_threshold))
        if inliers > best_inliers_count:
            best_inliers_count = inliers
            best_normal = normal
            best_d = d

    signed_dists = vertices @ best_normal + best_d
    ground_inlier_mask = np.abs(signed_dists) <= distance_threshold
    return best_normal, best_d, ground_inlier_mask


def rotation_matrix_from_vectors(vec_from: np.ndarray, vec_to: np.ndarray) -> np.ndarray:
    """`vec_from` birim vektörünü `vec_to` birim vektörüne döndüren 3x3 Rodrigues matrisini hesaplar."""
    a = vec_from / max(float(np.linalg.norm(vec_from)), 1e-12)
    b = vec_to / max(float(np.linalg.norm(vec_to)), 1e-12)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    s = float(np.linalg.norm(v))
    if s < 1e-8:
        return np.eye(3, dtype=np.float64) if c > 0 else -np.eye(3, dtype=np.float64)
    kmat = np.array(
        [
            [0.0, -v[2], v[1]],
            [v[2], 0.0, -v[0]],
            [-v[1], v[0], 0.0],
        ],
        dtype=np.float64,
    )
    return np.eye(3, dtype=np.float64) + kmat + (kmat @ kmat) * ((1.0 - c) / (s * s))


def align_car_axes_and_estimate_front(vertices: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Yatay (X-Z) düzleminde PCA çalıştırarak aracın uzun eksenini **Z eksenine**
    hizalar ve kaput/kabin yükseklik profilinden ön yönün `+Z` olmasını sağlar.

    Ön/Arka Yönü (`front_confidence`) Nasıl Hesaplanır?
    Binek araçlarda ön kaput bölgesi (`+Z` ucu), tavan/kabin ve bagaj bölgesine
    göre genellikle daha uzun bir alçalma eğimine sahiptir; tavanın tepe noktası
    merkezin biraz gerisinde (`-Z` tarafında) yer alır. Bu geometrik asimetri
    ölçülerek `[0.0, 1.0]` aralığında bir `front_confidence` skoru üretilir.
    Eğer araç tamamen simetrik bir kutu gibiyse `front_confidence < 0.5` döner.
    """
    xz = vertices[:, [0, 2]]
    mean_xz = np.mean(xz, axis=0)
    centered_xz = xz - mean_xz

    # 2x2 kovaryans matrisi ve özvektörler (PCA)
    cov = np.cov(centered_xz, rowvar=False)
    eigvals, eigvecs = np.linalg.eigh(cov)
    # En büyük özdeğere karşılık gelen özvektör aracın uzun (boyuna) eksenidir
    major_vec_2d = eigvecs[:, int(np.argmax(eigvals))]
    major_vec_2d = major_vec_2d / max(float(np.linalg.norm(major_vec_2d)), 1e-12)

    # Uzun ekseni +Z (0, 1) yönüne döndüren Y-ekseni dönüş açısı
    yaw_angle = math.atan2(float(major_vec_2d[0]), float(major_vec_2d[1]))
    cos_y, sin_y = math.cos(-yaw_angle), math.sin(-yaw_angle)
    rot_y = np.array(
        [
            [cos_y, 0.0, sin_y],
            [0.0, 1.0, 0.0],
            [-sin_y, 0.0, cos_y],
        ],
        dtype=np.float64,
    )
    aligned = vertices @ rot_y.T

    # Ön (+Z) ve Arka (-Z) yön belirsizliğini (180° ambiguity) çöz
    z_coords = aligned[:, 2]
    y_coords = aligned[:, 1]
    z_min, z_max = float(np.min(z_coords)), float(np.max(z_coords))
    z_span = max(z_max - z_min, 1e-6)

    # +Z ucundaki %30'luk bölge ile -Z ucundaki %30'luk bölgenin 90. yüzdelik yüksekliklerini karşılaştır
    pos_z_mask = z_coords >= (z_max - 0.30 * z_span)
    neg_z_mask = z_coords <= (z_min + 0.30 * z_span)

    pos_height = float(np.percentile(y_coords[pos_z_mask], 90.0)) if np.any(pos_z_mask) else 1.0
    neg_height = float(np.percentile(y_coords[neg_z_mask], 90.0)) if np.any(neg_z_mask) else 1.0

    # Ayrıca üst %25'lik tavan (kabin) noktalarının Z ağırlık merkezine bak
    y_top_thresh = np.percentile(y_coords, 75.0)
    roof_z_mean = float(np.mean(z_coords[y_coords >= y_top_thresh]))

    # Eğer +Z tarafı daha yüksekse (tavan/kabin +Z'ye kaymışsa), aracın önü -Z'de demektir -> 180° çevir
    height_diff_ratio = abs(neg_height - pos_height) / max(pos_height, neg_height, 1e-6)
    roof_offset_ratio = abs(roof_z_mean) / (0.5 * z_span)

    if pos_height > neg_height + 0.04 or roof_z_mean > 0.05 * z_span:
        flip_180 = np.array(
            [
                [-1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, -1.0],
            ],
            dtype=np.float64,
        )
        aligned = aligned @ flip_180.T

    # Ön/arka güven skoru: uzun/kısa eksen oranı + kaput/kabin asimetrisi
    aspect_elongation = float(np.max(eigvals)) / max(float(np.min(eigvals)), 1e-6)
    elongation_score = min(1.0, max(0.0, (aspect_elongation - 1.2) / 2.5))
    asymmetry_score = min(1.0, (height_diff_ratio * 2.5) + (roof_offset_ratio * 2.0))
    front_confidence = round(float(0.35 * elongation_score + 0.65 * asymmetry_score), 3)
    front_confidence = max(0.15, min(0.99, front_confidence))

    return aligned, front_confidence


class Step06ExtractMesh(Step):
    """TSDF/Poisson mesh çıkaran, RANSAC zemin kesimi, PCA hizalama ve ölçekleme yapan adım."""

    name = "extract_mesh"
    order = 6
    requires = ("radiance_field_model", "transforms_json", "masks_dir")
    produces = ("clean_mesh_ply", "mesh_metrics")

    def _extract_raw_mesh_from_model(
        self,
        model_path: Path,
        step_dir: Path,
        ctx: PipelineContext,
    ) -> trimesh.Trimesh:
        """
        Adım 05'ten gelen model bir `.ply` dosyasıysa doğrudan yükler (veya nokta
        bulutuysa dışbükey/alfa yüzeyine çevirir); Nerfstudio `config.yml` dosyasıysa
        `ns-export tsdf` çalıştırarak ham mesh'i üretir.
        """
        if model_path.suffix.lower() == ".yml":
            tsdf_dir = step_dir / "tsdf_raw"
            tsdf_dir.mkdir(parents=True, exist_ok=True)
            run_subprocess(
                command=[
                    "ns-export",
                    "tsdf",
                    "--load-config",
                    str(model_path),
                    "--output-dir",
                    str(tsdf_dir),
                    "--target-num-faces",
                    str(ctx.config.mesh_target_faces * 2),
                ],
                step_name=self.step_id,
                error_code="TSDF_FUSION_FAILED",
                error_message="Nerfstudio TSDF mesh çıkarımı başarısız oldu",
                timeout_seconds=ctx.config.step_timeout_seconds,
                logger=ctx.logger,
            )
            ply_candidates = sorted(tsdf_dir.glob("*.ply")) + sorted(tsdf_dir.glob("*.obj"))
            if not ply_candidates:
                raise StepError(
                    step=self.step_id,
                    code="TSDF_FUSION_FAILED",
                    message="TSDF dışa aktarımı sonrasında mesh dosyası bulunamadı.",
                )
            model_path = ply_candidates[0]

        loaded = trimesh.load(str(model_path), force="mesh")
        if isinstance(loaded, trimesh.Scene):
            loaded = loaded.dump(concatenate=True)
        if not isinstance(loaded, trimesh.Trimesh) or len(loaded.vertices) == 0:
            raise StepError(
                step=self.step_id,
                code="EMPTY_MESH",
                message=f"Yüklenen 3B model geçerli köşe (vertex) içermiyor: {model_path}",
            )
        return loaded

    def run(self, ctx: PipelineContext) -> StepResult:
        step_dir = self.prepare_step_dir(ctx)
        model_path = ctx.get_artifact_path("radiance_field_model")
        _transforms_path = ctx.get_artifact_path("transforms_json")
        _masks_dir = ctx.get_artifact_path("masks_dir")

        mesh = self._extract_raw_mesh_from_model(model_path, step_dir, ctx)
        initial_faces = int(len(mesh.faces))
        ctx.logger.info("Ham mesh yüklendi: %d köşe, %d üçgen yüz.", len(mesh.vertices), initial_faces)

        # ── 1. RANSAC ile Zemin Düzlemini Bul, +Y'yi Hizala ve Zemini Kes ──
        ground_normal, ground_d, _ground_mask = fit_ground_plane_ransac(
            vertices= np.asarray(mesh.vertices, dtype=np.float64),
            distance_threshold=ctx.config.ransac_ground_dist_threshold,
        )
        rot_to_up = rotation_matrix_from_vectors(ground_normal, np.array([0.0, 1.0, 0.0]))
        verts_up = (np.asarray(mesh.vertices, dtype=np.float64) @ rot_to_up.T)
        # Zemin düzlemini y ≈ 0 seviyesine taşı ve zemin plakasındaki üçgenleri kes
        ground_y_level = -ground_d
        verts_up[:, 1] -= ground_y_level
        mesh.vertices = verts_up

        # Üçgen yüzlerin merkez yüksekliği zemin eşiğinin (`ransac_ground_dist_threshold * 0.5`)
        # altında kalanları (asfalt plakasını) kaldır
        face_centers_y = mesh.triangles_center[:, 1]
        non_ground_faces = face_centers_y > (ctx.config.ransac_ground_dist_threshold * 0.25)
        if np.count_nonzero(non_ground_faces) >= 12:
            mesh.update_faces(non_ground_faces)
            mesh.remove_unreferenced_vertices()

        # ── 2. Floater (Havada Asılı Gürültü) Temizliği ──
        # Yalnızca zeminle bağlantısı olmayan çok küçük izole parçaları (ana bileşenin %1'inden
        # küçük olan gürültü kürelerini) at, tekerlek ve kabin gibi araç parçalarını koru.
        components = mesh.split(only_watertight=False)
        if len(components) > 1:
            components_sorted = sorted(components, key=lambda m: len(m.faces), reverse=True)
            max_comp_faces = len(components_sorted[0].faces)
            kept_components = [
                comp
                for comp in components_sorted
                if len(comp.faces) >= max(8, int(max_comp_faces * 0.02))
                and float(np.min(comp.vertices[:, 1])) < 1.5
            ]
            mesh = trimesh.util.concatenate(kept_components) if kept_components else components_sorted[0]

        if len(mesh.faces) < 4:
            raise StepError(
                step=self.step_id,
                code="EMPTY_MESH",
                message="Zemin ve gürültü temizliği sonrasında yeterli üçgen yüz kalmadı.",
                hint="Aracın video boyunca net göründüğünden ve maskelerin aracı kesmediğinden emin olun.",
            )

        # ── 3. PCA ile Uzun Ekseni +Z'ye Hizala ve Ön/Arka Yönünü (`front_confidence`) Belirle ──
        aligned_verts, front_confidence = align_car_axes_and_estimate_front(
            np.asarray(mesh.vertices, dtype=np.float64)
        )
        mesh.vertices = aligned_verts

        if front_confidence < 0.55:
            ctx.logger.warning(
                "DİKKAT: Aracın ön/arka profil asimetrisi düşük (front_confidence=%.3f). "
                "Uzun eksen +Z'ye hizalandı ancak ön/arka yönü %100 kesin olmayabilir.",
                front_confidence,
            )
        else:
            ctx.logger.info(
                "PCA eksen hizalaması tamamlandı (+Y yukarı, +Z araç önü, front_confidence=%.3f).",
                front_confidence,
            )

        # ── 4. Zemin Referanslı Konumlandırma (X=0, Z=0 Ortala; Tekerlek Tabanı y=0.0 Olsun) ──
        # Karar 2b: Kütle merkezi (0,0,0) KULLANILMAZ; tekerleklerin bastığı en alt nokta y=0 olur.
        bounds_min, bounds_max = mesh.bounds
        center_x = 0.5 * (bounds_min[0] + bounds_max[0])
        center_z = 0.5 * (bounds_min[2] + bounds_max[2])
        wheel_base_y = bounds_min[1]

        mesh.vertices[:, 0] -= center_x
        mesh.vertices[:, 2] -= center_z
        mesh.vertices[:, 1] -= wheel_base_y

        # ── 5. Ölçekleme ve Gerçek Ölçek Üstverisi (`meters_per_unit`, `scale_known`) ──
        # Karar 2a: Birim küpe ölçeklerken gerçek ölçeği kaybetme; ölçek referansı biliniyorsa
        # doğrudan metre cinsinden bırak.
        extents_before = mesh.extents
        max_extent = float(np.max(extents_before))
        if max_extent <= 1e-8:
            raise StepError(
                step=self.step_id,
                code="DEGENERATE_MESH_BOUNDS",
                message="Mesh sınır kutusu (bounding box) sıfır boyutlu.",
            )

        if ctx.config.known_meters_per_unit > 0.0:
            # Gerçek ölçek referansı biliniyor -> doğrudan metreye çevir ve birim küpe küçültme!
            scale_factor = float(ctx.config.known_meters_per_unit)
            mesh.vertices *= scale_factor
            scale_known = True
            meters_per_unit = 1.0
            ctx.logger.info(
                "Bilinen ölçek referansı uygulandı (KNOWN_METERS_PER_UNIT=%.4f -> doğrudan metre ölçeği).",
                scale_factor,
            )
        else:
            # Ölçek referansı bilinmiyorsa: modeli en uzun kenarı 1.0 birim olacak şekilde normalize et
            # (X ve Z [-0.5, 0.5] içinde, Y ise [0.0, height/max_extent] aralığında kalır) ve
            # sahnenin orijinal/tipik metre karşılığını `meters_per_unit` içinde koru.
            mesh.vertices /= max_extent
            scale_known = False
            # Eğer orijinal COLMAP sahnesi yaklaşık metre ölçeğindeyse (örn. 3.5m - 5.5m) onu kaydet,
            # aksi halde standart binek araç boyunu (~4.5m) referans olarak sakla.
            meters_per_unit = round(max_extent if 2.5 <= max_extent <= 6.5 else 4.5, 4)
            ctx.logger.info(
                "Ölçek referansı bilinmiyor (scale_known=False): Model birim boyuta normalize edildi "
                "(tekerlek tabanı y=0.0 korundu, tahmini meters_per_unit=%.4f).",
                meters_per_unit,
            )

        # ── 6. Delik Doldurma ve Hedef Yüz Sayısına İndirgeme (Decimation) ──
        trimesh.repair.fill_holes(mesh)
        target_faces = ctx.config.mesh_target_faces
        if len(mesh.faces) > target_faces:
            try:
                mesh = mesh.simplify_quadric_decimation(target_faces)
            except Exception as exc:
                ctx.logger.warning("Quadric decimation atlandı (%s); mevcut yüz sayısı korunuyor.", exc)

        mesh.remove_unreferenced_vertices()
        clean_ply_path = step_dir / "clean_mesh.ply"
        mesh.export(str(clean_ply_path), file_type="ply")

        final_bounds_min, final_bounds_max = mesh.bounds
        final_extents = mesh.extents

        metrics_data: Dict[str, Any] = {
            "initial_faces": initial_faces,
            "vertex_count": int(len(mesh.vertices)),
            "face_count": int(len(mesh.faces)),
            "is_watertight": bool(mesh.is_watertight),
            "wheel_base_y": round(float(final_bounds_min[1]), 6),
            "bbox_min": [round(float(v), 5) for v in final_bounds_min],
            "bbox_max": [round(float(v), 5) for v in final_bounds_max],
            "bbox_extents": [round(float(v), 5) for v in final_extents],
            "meters_per_unit": meters_per_unit,
            "scale_known": scale_known,
            "front_confidence": front_confidence,
            "coordinate_convention": "glTF right-handed (+Y up, +Z car front, y=0 ground plane)",
        }

        metrics_path = step_dir / "mesh_metrics.json"
        metrics_path.write_text(json.dumps(metrics_data, indent=2, ensure_ascii=False), encoding="utf-8")

        return StepResult(
            status="done",
            artifacts={
                "clean_mesh_ply": str(clean_ply_path),
                "mesh_metrics": str(metrics_path),
            },
            metrics=metrics_data,
            summary=(
                f"Mesh çıkarıldı ve hizalandı ({len(mesh.faces)} yüz, y_min={final_bounds_min[1]:.4f}, "
                f"front_confidence={front_confidence:.2f}, scale_known={scale_known})."
            ),
        )
