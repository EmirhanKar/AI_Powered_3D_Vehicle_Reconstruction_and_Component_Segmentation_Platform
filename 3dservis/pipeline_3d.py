"""
pipeline_3d.py
──────────────────────────────────────────────────────────────────────────────
4 Fotoğraftan 3 Boyutlu Araç Rekonstrüksiyon Pipeline'ı (Local 3D AI Pipeline)
MODIF-AI Projesi - Emirhan Kar & Ekibi

Akış Şeması:
1. 4 Açı Fotoğraf Girişi (Ön, Sağ Yan, Arka, Sol Yan)
2. SAM (Segment Anything) ile Arka Plan Temizleme & Araç Maskeleme
3. Depth Anything 3 (DA3-Large) ile Çoklu Açı Derinlik & Kamera Poz Kestirimi (PnP / Extrinsics)
4. 2D Derinlik Haritalarından 3D Dünya Koordinatlarına Geri İzdüşüm (Back-projection & Fusion)
5. KD-Tree Statistical Outlier Removal ile Gürültü ve Uçan Nokta Temizliği
6. Normal Kestirimi ve Poisson Surface Reconstruction ile 3D Mesh Üretimi
7. Düşük Yoğunluklu Yüzeylerin Kırpılması & Ağ Temizliği
8. Renkli GLB (glTF Binary) Formatında Dışa Aktarma
──────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import time
import argparse
import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional

import cv2
import numpy as np
import torch
import open3d as o3d
from scipy.spatial import cKDTree

# Depth Anything 3 kütüphanesini import et
DA3_SRC = os.path.join(os.path.dirname(__file__), "Depth-Anything-3", "src")
if os.path.exists(DA3_SRC) and DA3_SRC not in sys.path:
    sys.path.insert(0, DA3_SRC)

from depth_anything_3.api import DepthAnything3
from segment_anything import sam_model_registry, SamPredictor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("Pipeline3D")


@dataclass
class PipelineConfig:
    """3D Rekonstrüksiyon Hiperparametreleri"""
    sam_checkpoint: str = os.path.join(os.path.dirname(__file__), "SAM", "sam_vit_h_4b8939.pth")
    da3_model_name: str = "depth-anything/DA3-LARGE"
    conf_threshold: float = 0.65       # DA3 derinlik güven eşiği (0.0 - 1.0)
    outlier_neighbors: int = 21         # KD-Tree komşuluk sayısı
    outlier_std_ratio: float = 4.0      # Outlier standart sapma çarpanı
    poisson_depth: int = 9              # Poisson yüzey örme detayı (8: Hızlı, 9: Dengeli, 10: Yüksek)
    density_quantile: float = 0.02      # Düşük yoğunluklu gereksiz yüzeyleri budama yüzdesi (%2)
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


class FourView3DPipeline:
    """
    4 Fotoğraftan Tam 3 Boyutlu Araç Modeli Üreten Ana Pipeline Sınıfı.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.cfg = config or PipelineConfig()
        self.device = torch.device(self.cfg.device)
        self.sam_predictor: Optional[SamPredictor] = None
        self.da3_model: Optional[DepthAnything3] = None
        log.info(f"Pipeline hazırlandı. Çalışma Cihazı: {self.device}")

    def load_models(self):
        """Modelleri GPU/CPU belleğine yükler (Lazy loader)."""
        if self.sam_predictor is None:
            if not os.path.exists(self.cfg.sam_checkpoint):
                raise FileNotFoundError(
                    f"SAM checkpoint bulunamadı: {self.cfg.sam_checkpoint}\n"
                    "Lütfen 'sam_vit_h_4b8939.pth' dosyasının SAM klasöründe olduğunu doğrulayın."
                )
            log.info(f"SAM Modeli Yükleniyor -> {self.cfg.sam_checkpoint}")
            sam = sam_model_registry["vit_h"](checkpoint=self.cfg.sam_checkpoint)
            sam.to(self.device)
            self.sam_predictor = SamPredictor(sam)
            log.info("✓ SAM modeli başarıyla yüklendi.")

        if self.da3_model is None:
            log.info(f"Depth Anything 3 Modeli Yükleniyor -> {self.cfg.da3_model_name}")
            torch.cuda.empty_cache()
            self.da3_model = DepthAnything3.from_pretrained(self.cfg.da3_model_name)
            self.da3_model = self.da3_model.to(self.device)
            log.info("✓ Depth Anything 3 modeli başarıyla yüklendi.")

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 1: SAM ile Araç Segmentasyonu ve Arka Plan İzolasyonu
    # ──────────────────────────────────────────────────────────────────────────
    def extract_car_mask(self, image_rgb: np.ndarray) -> np.ndarray:
        """
        Görseldeki aracı arka plandan (zemin, binalar, gökyüzü) izole eder.
        Merkezi geometrik referans noktalarıyla araç gövdesini segment eder.
        """
        h, w = image_rgb.shape[:2]
        # Araç genelde karenin merkezinde konumlanır; 5 kritik odak noktası
        input_points = np.array([
            [w // 2, h // 2],          # Merkez
            [w // 2, int(h * 0.35)],   # Üst tavan/kaput
            [w // 2, int(h * 0.65)],   # Alt gövde/tampon
            [int(w * 0.30), h // 2],   # Sol gövde
            [int(w * 0.70), h // 2],   # Sağ gövde
        ], dtype=np.float32)
        input_labels = np.array([1, 1, 1, 1, 1], dtype=np.int32)

        self.sam_predictor.set_image(image_rgb)
        masks, scores, _ = self.sam_predictor.predict(
            point_coords=input_points,
            point_labels=input_labels,
            multimask_output=True
        )

        best_mask = masks[np.argmax(scores)].astype(np.uint8)

        # Morfolojik temizleme: delikleri kapat ve kenarları pürüzsüzleştir
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        best_mask = cv2.morphologyEx(best_mask, cv2.MORPH_CLOSE, kernel, iterations=3)
        best_mask = cv2.morphologyEx(best_mask, cv2.MORPH_OPEN, kernel, iterations=2)

        # En büyük bağlı bileşeni (aracı) seç, küçük parazitleri sil
        num_labels, labels_im = cv2.connectedComponents(best_mask)
        if num_labels > 1:
            sizes = np.bincount(labels_im.flatten())
            sizes[0] = 0  # Arka planı hariç tut
            best_mask = (labels_im == np.argmax(sizes)).astype(np.uint8)

        return best_mask

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 2: Derinlik Haritasından 3D Noktaya Geri İzdüşüm (Back-projection)
    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def depth_to_world_points(
        depth_map: np.ndarray,
        rgb_image: np.ndarray,
        intrinsics: np.ndarray,
        extrinsics: np.ndarray,
        car_mask: np.ndarray,
        conf_map: Optional[np.ndarray] = None,
        conf_thresh: float = 0.65
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Piksel koordinatlarını (u, v) ve derinlik değerini (d), kamera iç parametre matrisi K
        ve dış parametre matrisi [R | t] kullanarak 3D Dünya koordinatlarına dönüştürür.
        """
        h, w = depth_map.shape
        fx, fy = intrinsics[0, 0], intrinsics[1, 1]
        cx, cy = intrinsics[0, 2], intrinsics[1, 2]

        if car_mask.shape != (h, w):
            car_mask = cv2.resize(car_mask, (w, h), interpolation=cv2.INTER_NEAREST)

        valid = car_mask > 0

        # Güven haritası filtresi
        if conf_map is not None:
            if conf_map.shape != (h, w):
                conf_map = cv2.resize(conf_map.astype(np.float32), (w, h))
            valid = valid & (conf_map > conf_thresh)

        # Geçerli pikselleri seç
        u, v = np.meshgrid(np.arange(w), np.arange(h))
        u = u[valid]
        v = v[valid]
        z = depth_map[valid]
        colors = rgb_image[valid].astype(np.float32) / 255.0

        if len(u) == 0:
            return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.float32)

        # Kamera koordinat sistemi: X = (u - cx)*Z/fx, Y = (v - cy)*Z/fy, Z = d
        x = (u - cx) * z / fx
        y = (v - cy) * z / fy
        points_cam = np.stack([x, y, z], axis=-1)

        # Dünya koordinat sistemine dönüşüm: P_world = R^(-1) * (P_cam - t)
        R = extrinsics[:3, :3]
        t = extrinsics[:3, 3]
        points_world = (points_cam - t) @ np.linalg.inv(R).T

        return points_world, colors

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 3: Point Cloud Birleştirme & Outlier Temizliği
    # ──────────────────────────────────────────────────────────────────────────
    def clean_point_cloud(self, points: np.ndarray, colors: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        KD-Tree ile istatistiksel aykırı değerleri (Statistical Outliers) ve
        uçan parazit noktaları temizler.
        """
        log.info(f"Nokta bulutu filtreleniyor: {len(points):,} nokta...")

        # 1. Scipy KD-Tree ile komşuluk mesafesi filtresi
        tree = cKDTree(points)
        distances, _ = tree.query(points, k=self.cfg.outlier_neighbors)
        mean_d = distances[:, 1:].mean(axis=1)
        threshold = mean_d.mean() + self.cfg.outlier_std_ratio * mean_d.std()
        valid_mask = mean_d < threshold

        points = points[valid_mask]
        colors = colors[valid_mask]
        log.info(f"İstatistiki filtre sonrası: {len(points):,} nokta kaldı.")

        # 2. Bounding Box percentiles (%0.5 - %99.5) ile aşırı uçuşan noktaları buda
        if len(points) > 0:
            lo = np.percentile(points, 0.5, axis=0)
            hi = np.percentile(points, 99.5, axis=0)
            margin = (hi - lo) * 0.05
            box_mask = np.all((points >= lo - margin) & (points <= hi + margin), axis=1)
            points = points[box_mask]
            colors = colors[box_mask]

        return points, colors

    # ──────────────────────────────────────────────────────────────────────────
    # ADIM 4: Poisson Yüzey Örme & Mesh Optimizasyonu
    # ──────────────────────────────────────────────────────────────────────────
    def reconstruct_mesh(self, points: np.ndarray, colors: np.ndarray) -> Optional[o3d.geometry.TriangleMesh]:
        """
        Filtrelenmiş nokta bulutundan Poisson Surface Reconstruction ile sürekli,
        renkli ve pürüzsüz 3D poligon mesh örer.
        """
        log.info("Yüzey normalleri hesaplanıyor...")
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        pcd.colors = o3d.utility.Vector3dVector(colors if colors.max() <= 1.0 else colors / 255.0)

        # Yüzey normallerini hesapla ve tutarlı hale getir
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.15, max_nn=30)
        )
        pcd.orient_normals_consistent_tangent_plane(10)

        log.info(f"Poisson Yüzey Örme başlıyor (Derinlik: {self.cfg.poisson_depth})...")
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            pcd, depth=self.cfg.poisson_depth
        )

        # Desteksiz/boş alandaki düşük yoğunluklu yüzeyleri kırp
        densities = np.asarray(densities)
        if len(densities) > 0:
            cutoff = np.quantile(densities, self.cfg.density_quantile)
            mesh.remove_vertices_by_mask(densities < cutoff)

        # Topolojik mesh temizliği
        mesh.remove_degenerate_triangles()
        mesh.remove_duplicated_triangles()
        mesh.remove_duplicated_vertices()
        mesh.remove_non_manifold_edges()

        log.info(f"✓ Renkli Mesh oluşturuldu: {len(mesh.vertices):,} köşe, {len(mesh.triangles):,} üçgen.")
        return mesh

    # ──────────────────────────────────────────────────────────────────────────
    # ANA ÇALIŞTIRICI: 4 Görselden GLB Üretimi
    # ──────────────────────────────────────────────────────────────────────────
    def process_4_views(self, image_paths: List[str], output_glb_path: str) -> Optional[str]:
        """
        4 fotoğrafı baştan sona işleyerek bir GLB 3D dosyası üretir.
        """
        start_time = time.time()
        log.info("=" * 60)
        log.info(f"4 AÇILI 3D REKONSTRÜKSİYON BAŞLATILDI ({len(image_paths)} Görsel)")
        log.info("=" * 60)

        # Girdi kontrolü
        if len(image_paths) < 1:
            log.error("İşlenecek fotoğraf bulunamadı!")
            return None

        for p in image_paths:
            if not os.path.exists(p):
                log.error(f"Fotoğraf dosyası bulunamadı: {p}")
                return None

        # 1. Modelleri yükle
        self.load_models()

        # 2. SAM Maskelerini çıkar
        log.info("Adım 1/4: SAM Araç Maskeleri Oluşturuluyor...")
        masks = []
        for i, img_path in enumerate(image_paths):
            bgr = cv2.imread(img_path)
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            mask = self.extract_car_mask(rgb)
            masks.append(mask)
            log.info(f"  [Görsel {i+1}/{len(image_paths)}] Araç maskelendi: {os.path.basename(img_path)}")

        # 3. Depth Anything 3 ile Derinlik & Kamera Pozlarını çıkar
        log.info("Adım 2/4: Depth Anything 3 Çoklu Açı Çıkarımı Yapılıyor...")
        torch.cuda.empty_cache()
        prediction = self.da3_model.inference(
            image=image_paths,
            infer_gs=True,
            process_res_method="upper_bound_resize"
        )

        # 4. 3D Dünya Koordinatlarına Geri İzdüşüm ve Füzyon
        log.info("Adım 3/4: 4 Görüş Noktası 3D Uzayda Birleştiriliyor...")
        all_points = []
        all_colors = []

        num_views = len(prediction.depth)
        for i in range(num_views):
            pts, cols = self.depth_to_world_points(
                depth_map=prediction.depth[i],
                rgb_image=prediction.processed_images[i],
                intrinsics=prediction.intrinsics[i],
                extrinsics=prediction.extrinsics[i],
                car_mask=masks[i] if i < len(masks) else np.ones_like(prediction.depth[i], dtype=np.uint8),
                conf_map=prediction.conf[i] if hasattr(prediction, "conf") else None,
                conf_thresh=self.cfg.conf_threshold
            )
            if len(pts) > 0:
                all_points.append(pts)
                all_colors.append(cols)
                log.info(f"  Açı {i+1}: {len(pts):,} nokta eklendi.")

        if not all_points:
            log.error("Hiçbir açıdan geçerli 3D nokta elde edilemedi!")
            return None

        merged_points = np.vstack(all_points)
        merged_colors = np.vstack(all_colors)
        log.info(f"Toplam Birleşik Nokta Sayısı: {len(merged_points):,}")

        # 5. Aykırı değerleri temizle
        clean_pts, clean_cols = self.clean_point_cloud(merged_points, merged_colors)

        # 6. Poisson Yüzey Örme
        log.info("Adım 4/4: Poisson 3D Mesh Oluşturuluyor...")
        mesh = self.reconstruct_mesh(clean_pts, clean_cols)
        if mesh is None:
            log.error("Mesh oluşturulamadı!")
            return None

        # 7. GLB olarak kaydet
        out_dir = os.path.dirname(output_glb_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        try:
            o3d.io.write_triangle_mesh(output_glb_path, mesh)
            log.info(f"✓ 3D Model başarıyla kaydedildi: {output_glb_path}")
        except Exception as e:
            log.warning(f"GLB doğrudan yazılamadı, GLTF deneniyor: {e}")
            alt_path = output_glb_path.replace(".glb", ".gltf")
            o3d.io.write_triangle_mesh(alt_path, mesh)
            output_glb_path = alt_path

        elapsed = time.time() - start_time
        file_size_mb = os.path.getsize(output_glb_path) / (1024 * 1024)
        log.info("=" * 60)
        log.info(f"3D PİPELİNE TAMAMLANDI! Süre: {elapsed:.2f} sn | Boyut: {file_size_mb:.2f} MB")
        log.info("=" * 60)

        return output_glb_path


# ──────────────────────────────────────────────────────────────────────────────
# CLI Arayüzü
# ──────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="4 Fotoğraftan 3D Araç Üretim Pipeline'ı")
    parser.add_argument(
        "--images", "-i", nargs="+", required=True,
        help="İşlenecek 4 fotoğrafın dosya yolları (Örn: -i on.jpg sag.jpg arka.jpg sol.jpg)"
    )
    parser.add_argument(
        "--output", "-o", default="araba_3d.glb",
        help="Çıktı GLB dosyasının yolu (Örn: -o cikti/model.glb)"
    )
    parser.add_argument(
        "--poisson_depth", type=int, default=9,
        help="Poisson detay seviyesi (Öntanımlı: 9)"
    )
    parser.add_argument(
        "--conf_thresh", type=float, default=0.65,
        help="Derinlik güven eşiği (Öntanımlı: 0.65)"
    )
    args = parser.parse_args()

    cfg = PipelineConfig(
        poisson_depth=args.poisson_depth,
        conf_threshold=args.conf_thresh
    )
    pipeline = FourView3DPipeline(config=cfg)
    pipeline.process_4_views(args.images, args.output)


def generate_3d_model(input_dir: str, output_dir: str, sam_predictor=None, da3_model=None) -> Optional[str]:
    """
    Klasördeki fotoğrafları toplayıp 3D GLB modelini üretir.
    servis.py ve dış modüller için doğrudan çağrılabilir fonksiyon.
    """
    import glob
    exts = ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.JPG", "*.PNG")
    images = []
    for ext in exts:
        images.extend(glob.glob(os.path.join(input_dir, ext)))
    images = sorted(images)

    if not images:
        log.error(f"Girdi klasöründe fotoğraf bulunamadı: {input_dir}")
        return None

    pipeline = FourView3DPipeline()
    if sam_predictor is not None:
        pipeline.sam_predictor = sam_predictor
    if da3_model is not None:
        if isinstance(da3_model, tuple):
            pipeline.da3_model = da3_model[0]
        else:
            pipeline.da3_model = da3_model

    glb_out = os.path.join(output_dir, "araba_modeli.glb")
    return pipeline.process_4_views(images, glb_out)


if __name__ == "__main__":
    main()
