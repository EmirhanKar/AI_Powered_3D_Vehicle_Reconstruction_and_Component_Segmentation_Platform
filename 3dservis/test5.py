"""
test5.py
──────────────────────────────────────────────────────────────────────────────
4 Fotoğraftan 3 Boyutlu Araç Rekonstrüksiyon Motoru (Local 3D AI Pipeline)
MODIF-AI 3D Servis - Emirhan Kar & Ekibi

İş Akışı:
1. Girdi Fotoğraflarının Yüklenmesi (Ön, Sağ Yan, Arka, Sol Yan)
2. SAM ile Arka Plan Temizleme & Hassas Araç Maskesi Üretimi
3. Depth Anything 3 (DA3-Large) ile Metrik Derinlik ve Kamera Poz Kestirimi (PnP / Extrinsics)
4. 2D Derinlik Haritalarından 3D Dünya Koordinatlarına Geri İzdüşüm (Back-projection & Fusion)
5. KD-Tree İstatistiki Outlier Filtreleme, Zemin Temizliği ve Bounding Box Budama
6. Normal Kestirimi ve Poisson Surface Reconstruction ile Su Geçirmez (Watertight) 3D Mesh
7. Düşük Yoğunluklu Yüzeylerin Budanması, Topolojik Ağ Onarımı ve Merkezleme
8. Renkli GLB (glTF Binary) Formatında Dışa Aktarma
──────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import glob
import time
import logging
from typing import List, Tuple, Optional, Dict

import cv2
import numpy as np
import torch
import open3d as o3d
from scipy.spatial import cKDTree
import matplotlib.pyplot as plt

from config import (
    BASE_DIR,
    SAM_CHECKPOINT,
    DATA_DIR,
    MASKS_DIR,
    RESULTS_DIR,
    OUTPUT_DIR,
    POISSON_DEPTH,
    CONF_THRESH,
    OUTLIER_NB_NEIGHBORS,
    OUTLIER_STD_RATIO,
    DENSITY_QUANTILE,
)

# Depth Anything 3 kütüphanesi
from depth_anything_3.api import DepthAnything3
from segment_anything import sam_model_registry, SamPredictor

log = logging.getLogger("test5")


def setup_paths() -> Dict[str, str]:
    """Test çalıştırmaları ve servis için temel yolları döndürür."""
    return {
        "base": BASE_DIR,
        "data": DATA_DIR,
        "masks": MASKS_DIR,
        "results": RESULTS_DIR,
        "output": OUTPUT_DIR,
        "sam_checkpoint": SAM_CHECKPOINT,
    }


# ----------------------------
# GÖRSELLEŞTİRME YARDIMCILARI
# ----------------------------
def visualize_depth_and_confidence(images, depths, confidences, sample_idx=0):
    """Derinlik ve güven haritalarını yan yana çizer."""
    try:
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        axes[0].imshow(images[sample_idx])
        axes[0].set_title("RGB Image")
        axes[0].axis("off")
        axes[1].imshow(depths[sample_idx], cmap="turbo")
        axes[1].set_title("Depth Map")
        axes[1].axis("off")
        axes[2].imshow(confidences[sample_idx], cmap="viridis")
        axes[2].set_title("Confidence Map")
        axes[2].axis("off")
        plt.tight_layout()
        plt.show()
    except Exception as e:
        print(f"Görselleştirme atlandı (GUI yok): {e}")


def visualize_point_cloud_open3d(points, colors=None, window_name="Point Cloud"):
    """Open3D penceresinde nokta bulutunu görüntüler."""
    try:
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        if colors is not None:
            if colors.max() > 1.0:
                colors = colors / 255.0
            pcd.colors = o3d.utility.Vector3dVector(colors)
        vis = o3d.visualization.Visualizer()
        vis.create_window(window_name=window_name, width=1280, height=720)
        vis.add_geometry(pcd)
        vis.run()
        vis.destroy_window()
    except Exception as e:
        print(f"Pencere açılamadı: {e}")


# ----------------------------
# MODEL YÜKLEME
# ----------------------------
def load_da3_model():
    """Depth Anything 3 modelini belleğe yükler."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Depth Anything 3 yükleniyor... Kullanılan cihaz: {device}")
    torch.cuda.empty_cache()
    model = DepthAnything3.from_pretrained("depth-anything/DA3-LARGE")
    model = model.to(device)
    print("✓ Depth Anything 3 hazır.")
    return model, device


def load_sam_model(checkpoint_path=None):
    """SAM modelini belleğe yükler."""
    ckpt = checkpoint_path or SAM_CHECKPOINT
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"SAM yükleniyor: {ckpt} ({device})")
    sam = sam_model_registry["vit_h"](checkpoint=ckpt)
    sam.to(device)
    predictor = SamPredictor(sam)
    print("✓ SAM hazır.")
    return predictor


# ----------------------------
# SAM MASKE ÜRETİMİ
# ----------------------------
def get_car_mask(predictor, image_rgb):
    """Görseldeki aracı arka plandan ayıran ikili maske üretir."""
    h, w = image_rgb.shape[:2]
    input_points = np.array([
        [w // 2, h // 2],          # Merkez
        [w // 2, int(h * 0.35)],   # Üst tavan / kaput
        [w // 2, int(h * 0.65)],   # Alt tampon / gövde
        [int(w * 0.30), h // 2],   # Sol kapı / çamurluk
        [int(w * 0.70), h // 2],   # Sağ kapı / çamurluk
    ], dtype=np.float32)
    input_labels = np.array([1, 1, 1, 1, 1], dtype=np.int32)

    predictor.set_image(image_rgb)
    masks, scores, _ = predictor.predict(
        point_coords=input_points,
        point_labels=input_labels,
        multimask_output=True
    )
    best_mask = masks[np.argmax(scores)].astype(np.uint8)

    # Morfolojik temizleme
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    best_mask = cv2.morphologyEx(best_mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    best_mask = cv2.morphologyEx(best_mask, cv2.MORPH_OPEN, kernel, iterations=2)

    # En büyük bağlı bileşen (araç)
    num_labels, labels_im = cv2.connectedComponents(best_mask)
    if num_labels > 1:
        sizes = np.bincount(labels_im.flatten())
        sizes[0] = 0
        best_mask = (labels_im == np.argmax(sizes)).astype(np.uint8)

    return best_mask


def generate_masks(image_files, masks_path, sam_predictor):
    """Tüm fotoğraflar için SAM maskeleri üretir veya mevcudu yükler."""
    print("Maskeler kontrol ediliyor / oluşturuluyor...")
    os.makedirs(masks_path, exist_ok=True)
    mask_files = []

    for img_path in image_files:
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        mask_path = os.path.join(masks_path, f"{base_name}_mask.png")

        if os.path.exists(mask_path):
            print(f"  Mevcut maske: {os.path.basename(mask_path)}")
            mask_files.append(mask_path)
            continue

        image_bgr = cv2.imread(img_path)
        if image_bgr is None:
            print(f"❌ Görsel okunamadı: {img_path}")
            continue

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mask = get_car_mask(sam_predictor, image_rgb)
        cv2.imwrite(mask_path, mask * 255)
        print(f"  Oluşturuldu: {os.path.basename(mask_path)}")
        mask_files.append(mask_path)

    return mask_files


# ----------------------------
# GÖRSEL YÜKLEME
# ----------------------------
def load_images_from_folder(data_path, extensions=None):
    """Klasördeki görselleri alfabetik sırayla listeler."""
    if extensions is None:
        extensions = ["*.jpg", "*.png", "*.jpeg", "*.jfif", "*.JPG", "*.PNG"]
    image_files = []
    for ext in extensions:
        image_files.extend(glob.glob(os.path.join(data_path, ext)))
    image_files = sorted(list(set(image_files)))
    print(f"Klasörde {len(image_files)} görsel bulundu: {data_path}")
    return image_files


# ----------------------------
# DERİNLİK VE POZ ÇIKARIMI
# ----------------------------
def run_da3_inference(model, image_files):
    """Depth Anything 3 ile derinlik, iç ve dış kamera matrislerini hesaplar."""
    torch.cuda.empty_cache()
    print("Depth Anything 3 çoklu açı çıkarımı yapıyor...")
    prediction = model.inference(
        image=image_files,
        infer_gs=True,
        process_res_method="upper_bound_resize"
    )
    return prediction


# ----------------------------
# GERİ İZDÜŞÜM & NOKTA BULUTU BİRLEŞTİRME
# ----------------------------
def depth_to_point_cloud(
    depth_map: np.ndarray,
    rgb_image: np.ndarray,
    intrinsics: np.ndarray,
    extrinsics: np.ndarray,
    car_mask: np.ndarray,
    conf_map: Optional[np.ndarray] = None,
    conf_thresh: float = CONF_THRESH
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Pinhole kamera formülüyle 2D derinlik ve renk haritasından
    3D Dünya koordinatlarını ve kamera merkezini hesaplar.
    """
    h, w = depth_map.shape
    fx, fy = intrinsics[0, 0], intrinsics[1, 1]
    cx, cy = intrinsics[0, 2], intrinsics[1, 2]

    if car_mask.shape != (h, w):
        car_mask = cv2.resize(car_mask, (w, h), interpolation=cv2.INTER_NEAREST)

    valid = car_mask > 0

    if conf_map is not None:
        if conf_map.shape != (h, w):
            conf_map = cv2.resize(conf_map.astype(np.float32), (w, h))
        valid = valid & (conf_map > conf_thresh)

    u, v = np.meshgrid(np.arange(w), np.arange(h))
    u = u[valid]
    v = v[valid]
    z = depth_map[valid]
    colors = rgb_image[valid].astype(np.float32) / 255.0

    if len(u) == 0:
        return np.zeros((0, 3)), np.zeros((0, 3)), np.zeros(3)

    # Kamera koordinat sistemi: X=(u-cx)*Z/fx, Y=(v-cy)*Z/fy, Z=d
    x = (u - cx) * z / fx
    y = (v - cy) * z / fy
    points_cam = np.stack([x, y, z], axis=-1)

    # Dünya koordinat sistemi dönüşümü: P_world = R^(-1) * (P_cam - t)
    R = extrinsics[:3, :3]
    t = extrinsics[:3, 3]
    points_world = (points_cam - t) @ np.linalg.inv(R).T

    # Kamera merkezi dünya koordinatlarında: C = -R^T * t
    cam_center = -R.T @ t

    return points_world, colors, cam_center


def merge_point_clouds(prediction, mask_files, conf_thresh=CONF_THRESH):
    """Tüm kamera açılarından gelen noktaları tek bir bulutta birleştirir."""
    all_points = []
    all_colors = []
    camera_centers = []

    num_views = len(prediction.depth)
    for i in range(num_views):
        mask_img = cv2.imread(mask_files[i], cv2.IMREAD_GRAYSCALE)
        car_mask = (mask_img > 127).astype(np.uint8) if mask_img is not None else np.ones_like(prediction.depth[i], dtype=np.uint8)

        conf_data = prediction.conf[i] if hasattr(prediction, "conf") and prediction.conf is not None else None

        points, colors, cam_center = depth_to_point_cloud(
            depth_map=prediction.depth[i],
            rgb_image=prediction.processed_images[i],
            intrinsics=prediction.intrinsics[i],
            extrinsics=prediction.extrinsics[i],
            car_mask=car_mask,
            conf_map=conf_data,
            conf_thresh=conf_thresh
        )

        if len(points) > 0:
            all_points.append(points)
            all_colors.append(colors)
            camera_centers.append(cam_center)

        print(f"  Fotoğraf {i+1}: {len(points):,} nokta eklendi.")

    if not all_points:
        return np.zeros((0, 3)), np.zeros((0, 3))

    merged_points = np.vstack(all_points)
    merged_colors = np.vstack(all_colors)
    print(f"Toplam Birleşik Nokta Sayısı: {len(merged_points):,}")
    return merged_points, merged_colors


# ----------------------------
# NOKTA BULUTU TEMİZLEME
# ----------------------------
def clean_point_cloud_open3d(points_3d, colors_3d):
    """
    SciPy cKDTree ile istatistiksel aykırı değerleri temizler.
    Voxel downsampling yapmaz, aracın yoğunluk ve detayını korur.
    """
    print(f"Filtreleme başlıyor: {len(points_3d):,} nokta...")
    if colors_3d.max() > 1.0:
        colors_3d = colors_3d / 255.0

    # 1. Scipy statistical outlier (k=OUTLIER_NB_NEIGHBORS, std=OUTLIER_STD_RATIO)
    tree = cKDTree(points_3d)
    distances, _ = tree.query(points_3d, k=OUTLIER_NB_NEIGHBORS)
    mean_d = distances[:, 1:].mean(axis=1)
    threshold = mean_d.mean() + OUTLIER_STD_RATIO * mean_d.std()
    mask = mean_d < threshold

    points_3d = points_3d[mask]
    colors_3d = colors_3d[mask]
    print(f"  Statistical filtre sonrası: {len(points_3d):,} nokta kaldı.")

    # 2. Adaptif persentil sınırlayıcı kutu (%0.5 - %99.5) ile aşırı uçuşan noktaları buda
    if len(points_3d) > 0:
        lo = np.percentile(points_3d, 0.5, axis=0)
        hi = np.percentile(points_3d, 99.5, axis=0)
        margin = (hi - lo) * 0.05
        mask_b = np.all((points_3d >= lo - margin) & (points_3d <= hi + margin), axis=1)
        points_3d = points_3d[mask_b]
        colors_3d = colors_3d[mask_b]
        print(f"  Bounding box sonrası: {len(points_3d):,} nokta.")

    return points_3d, colors_3d


def clean_point_cloud_scipy(points_3d, colors_3d, nb_neighbors=20, std_ratio=2.0):
    """Yedek KD-Tree outlier filtresi."""
    tree = cKDTree(points_3d)
    distances, _ = tree.query(points_3d, k=nb_neighbors)
    mean_distances = np.mean(distances[:, 1:], axis=1)
    threshold = np.mean(mean_distances) + std_ratio * np.std(mean_distances)
    mask = mean_distances < threshold
    return points_3d[mask], colors_3d[mask]


# ----------------------------
# POISSON MESH ÜRETİMİ & İYİLEŞTİRME
# ----------------------------
def create_mesh(points, colors):
    """
    Nokta bulutundan Poisson Surface Reconstruction ile su geçirmez (watertight),
    renkli ve topolojik olarak temiz 3D mesh üretir.
    """
    print("\n=== Renkli Watertight Mesh Oluşturuluyor ===")
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors if colors.max() <= 1.0 else colors / 255.0)

    # 1. Normalleri kestir ve teğet düzlemlere göre tutarlı yönlendir
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.15, max_nn=30)
    )
    pcd.orient_normals_consistent_tangent_plane(15)

    # 2. Poisson Yüzey Örme
    print(f"-> Poisson yüzey örülüyor (Derinlik: {POISSON_DEPTH})...")
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=POISSON_DEPTH
    )

    # 3. Boş havadaki düşük yoğunluklu sahte poligonları buda
    densities = np.asarray(densities)
    if len(densities) > 0:
        cutoff = np.quantile(densities, DENSITY_QUANTILE)
        mesh.remove_vertices_by_mask(densities < cutoff)

    # 4. Topolojik Ağ Onarımı
    mesh.remove_degenerate_triangles()
    mesh.remove_duplicated_triangles()
    mesh.remove_duplicated_vertices()
    mesh.remove_non_manifold_edges()

    # 5. Modeli Merkezleme (Köken [0,0,0] üzerine taşıma)
    bbox = mesh.get_axis_aligned_bounding_box()
    center = bbox.get_center()
    mesh.translate(-center)

    # 6. Köşe Renklerini Nokta Bulutundan Hassas Olarak İnterpole Et
    tree = cKDTree(points)
    mesh_verts = np.asarray(mesh.vertices) + center
    _, idxs = tree.query(mesh_verts, k=1)
    mesh.vertex_colors = o3d.utility.Vector3dVector(colors[idxs])

    print(f"✓ Renkli Watertight Mesh hazır: {len(mesh.vertices):,} köşe, {len(mesh.triangles):,} üçgen.")
    return mesh


# ----------------------------
# BACKEND İÇİN GLB YÜKLEME
# ----------------------------
def glb_yukle(scan_id, glb_path, backend_url, admin_key):
    """GLB dosyasını backend'e aktarır."""
    import requests
    ext = os.path.splitext(glb_path)[1].lower()
    content_type = "model/gltf-binary" if ext == ".glb" else "model/gltf+json"
    with open(glb_path, "rb") as f:
        r = requests.post(
            f"{backend_url}/scans/complete/3d/{scan_id}",
            files={"model_file": (os.path.basename(glb_path), f, content_type)},
            headers={"X-Admin-Key": admin_key},
            timeout=300
        )
    r.raise_for_status()
    print(f"✓ GLB backend'e yüklendi → scan_id={scan_id}")
    return True


# ----------------------------
# ANA SERVİS ENTEGRASYON FONKSİYONU (servis.py için imza korunmuştur)
# ----------------------------
def generate_3d_model(input_dir, output_dir, sam_predictor, da3_model) -> Optional[str]:
    """
    servis.py tarafından çağrılan ana üretim fonksiyonu.
    Girdi: input_dir (araç fotoğrafları klasörü), output_dir (çıktı dizini)
    Döner: glb_path (str) veya None
    """
    if isinstance(da3_model, tuple):
        model, device = da3_model
    else:
        model = da3_model
        device = next(model.parameters()).device

    print(f"\n=== 3D Araç Rekonstrüksiyonu Başlıyor ({input_dir}) ===")
    image_files = load_images_from_folder(input_dir)
    if not image_files:
        print("❌ Klasörde fotoğraf bulunamadı!")
        return None

    masks_path = os.path.join(output_dir, "masks")
    os.makedirs(masks_path, exist_ok=True)

    # 1. SAM Maskeleri
    mask_files = generate_masks(image_files, masks_path, sam_predictor)

    # 2. DA3 Çıkarımı
    prediction = run_da3_inference(model, image_files)

    # 3. 3D Birleştirme
    points_3d, colors_3d = merge_point_clouds(prediction, mask_files, conf_thresh=CONF_THRESH)
    if len(points_3d) == 0:
        print("❌ Geçerli 3D nokta elde edilemedi!")
        return None

    # Ham nokta bulutunu kaydet
    pcd_raw = o3d.geometry.PointCloud()
    pcd_raw.points = o3d.utility.Vector3dVector(points_3d)
    pcd_raw.colors = o3d.utility.Vector3dVector(colors_3d / 255.0 if colors_3d.max() > 1 else colors_3d)
    o3d.io.write_point_cloud(os.path.join(output_dir, "ham.ply"), pcd_raw)

    # 4. Filtreleme ve Temizleme
    try:
        clean_pts, clean_cols = clean_point_cloud_open3d(points_3d, colors_3d)
    except Exception as e:
        print(f"Open3D temizleme uyarısı: {e}, SciPy deneniyor...")
        clean_pts, clean_cols = clean_point_cloud_scipy(points_3d, colors_3d)

    pcd_clean = o3d.geometry.PointCloud()
    pcd_clean.points = o3d.utility.Vector3dVector(clean_pts)
    pcd_clean.colors = o3d.utility.Vector3dVector(clean_cols)
    o3d.io.write_point_cloud(os.path.join(output_dir, "temiz.ply"), pcd_clean)

    # 5. Poisson Mesh Üretimi
    mesh = create_mesh(clean_pts, clean_cols)
    if mesh is None:
        return None

    o3d.io.write_triangle_mesh(os.path.join(output_dir, "araba_mesh.ply"), mesh)

    # 6. GLB Dışa Aktarımı
    glb_path = os.path.join(output_dir, "araba_modeli.glb")
    try:
        o3d.io.write_triangle_mesh(glb_path, mesh)
        print(f"🚀 GLB BAŞARIYLA ÜRETİLDİ: {glb_path}")
    except Exception as e:
        print(f"GLB doğrudan yazılamadı: {e}, GLTF olarak kaydediliyor...")
        glb_path = os.path.join(output_dir, "araba_modeli.gltf")
        o3d.io.write_triangle_mesh(glb_path, mesh)
        print(f"🚀 GLTF BAŞARIYLA ÜRETİLDİ: {glb_path}")

    return glb_path


# ----------------------------
# STANDALONE TEST (python test5.py)
# ----------------------------
if __name__ == "__main__":
    paths = setup_paths()
    print("Test Yolları Hazırlandı.")

    print("\n=== DA3 Modeli Yükleniyor ===")
    model, device = load_da3_model()

    print("\n=== SAM Modeli Yükleniyor ===")
    sam_predictor = load_sam_model(paths["sam_checkpoint"])

    test_input = paths["data"]
    image_files = load_images_from_folder(test_input)

    if not image_files:
        print(f"❌ {test_input} klasöründe görsel bulunamadı.")
    else:
        out_glb = generate_3d_model(
            input_dir=test_input,
            output_dir=paths["results"],
            sam_predictor=sam_predictor,
            da3_model=(model, device)
        )
        print(f"\n✓ İşlem Tamamlandı. Model: {out_glb}")