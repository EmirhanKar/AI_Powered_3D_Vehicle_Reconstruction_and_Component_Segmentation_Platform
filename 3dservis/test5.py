import glob
import os
import sys
import torch
import numpy as np
import cv2
import open3d as o3d
from segment_anything import sam_model_registry, SamPredictor
from config import IMAGES_DIR, OUTPUT_DIR, SAM_CHECKPOINT

# ----------------------------
# DEPTH ANYTHING V2 — Import
# Depth-Anything-V2/ klasörü 3dservis/ altında olmalı
# ----------------------------
DEPTH_ANYTHING_V2_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Depth-Anything-V2")
if DEPTH_ANYTHING_V2_PATH not in sys.path:
    sys.path.insert(0, DEPTH_ANYTHING_V2_PATH)

from depth_anything_v2.dpt import DepthAnythingV2

# ----------------------------
# PATH SETUP
# ----------------------------
def setup_paths():
    paths = {
        "data": IMAGES_DIR,
        "results": OUTPUT_DIR,
        "masks": os.path.join(OUTPUT_DIR, "masks"),
        "sam_checkpoint": SAM_CHECKPOINT
    }
    os.makedirs(paths["results"], exist_ok=True)
    os.makedirs(paths["masks"], exist_ok=True)
    return paths

# ----------------------------
# MODEL LOAD
# ----------------------------
def load_da3_model():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Kullanılan cihaz: {device}")
    torch.cuda.empty_cache()

    model_configs = {
        "vits": {"encoder": "vits", "features": 64,  "out_channels": [48,  96,  192, 384]},
        "vitb": {"encoder": "vitb", "features": 128, "out_channels": [96,  192, 384, 768]},
        "vitl": {"encoder": "vitl", "features": 256, "out_channels": [256, 512, 1024, 1024]},
    }

    encoder = "vitl"  # vitl=en iyi, vitb=orta, vits=hızlı
    cfg = model_configs[encoder]

    model = DepthAnythingV2(**cfg)

    # Checkpoint: Depth-Anything-V2/checkpoints/depth_anything_v2_vitl.pth
    # İndirme linki:
    # https://huggingface.co/depth-anything/Depth-Anything-V2-Large/resolve/main/depth_anything_v2_vitl.pth
    checkpoint_path = os.path.join(DEPTH_ANYTHING_V2_PATH, "checkpoints", f"depth_anything_v2_{encoder}.pth")

    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(
            f"\n[HATA] Checkpoint bulunamadı: {checkpoint_path}\n"
            f"Şuradan indir:\n"
            f"https://huggingface.co/depth-anything/Depth-Anything-V2-Large/resolve/main/depth_anything_v2_vitl.pth\n"
            f"Kaydet: {checkpoint_path}\n"
        )

    model.load_state_dict(torch.load(checkpoint_path, map_location="cpu"))
    model = model.to(device).eval()
    print(f"Depth Anything V2 ({encoder}) yüklendi.")
    return model, device

def load_sam_model(checkpoint_path):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"SAM yükleniyor: {checkpoint_path}")
    sam = sam_model_registry["vit_h"](checkpoint=checkpoint_path)
    sam.to(device)
    predictor = SamPredictor(sam)
    print("SAM hazır.")
    return predictor

# ----------------------------
# DEPTH INFERENCE
# ----------------------------
def run_da3_inference(model, device, image_files):
    """
    Tüm görüntüler için DA V2 derinlik çıkarımı yapar.
    servis.py ile uyumlu Prediction nesnesi döner.
    """
    print(f"{len(image_files)} görüntü işleniyor...")
    depths = []
    processed_images = []
    confs = []
    intrinsics_list = []
    extrinsics_list = []

    for i, img_path in enumerate(image_files):
        img_bgr = cv2.imread(img_path)
        if img_bgr is None:
            print(f"  [UYARI] Okunamadı: {img_path}")
            continue

        h, w = img_bgr.shape[:2]

        # DA V2'nin kendi infer_image metodu — resize+normalize+forward+resize hepsini yapar
        with torch.no_grad():
            depth = model.infer_image(img_bgr)  # (H, W) numpy array

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        depths.append(depth)
        processed_images.append(img_rgb)

        # Confidence: derinlik gradyanından tahmin (DA V2 confidence üretmez)
        grad_x = np.abs(np.gradient(depth, axis=1))
        grad_y = np.abs(np.gradient(depth, axis=0))
        conf = 1.0 / (1.0 + grad_x + grad_y)
        confs.append(conf)

        # Pinhole kamera — HFOV=60 derece varsayımı
        fx = fy = w / (2 * np.tan(np.radians(30)))
        cx, cy = w / 2.0, h / 2.0
        K = np.array([[fx, 0, cx],
                      [0, fy, cy],
                      [0,  0,  1]], dtype=np.float64)
        intrinsics_list.append(K)
        extrinsics_list.append(np.eye(4, dtype=np.float64))

        print(f"  [{i+1}/{len(image_files)}] {os.path.basename(img_path)} tamamlandı.")

    class Prediction:
        pass

    pred = Prediction()
    pred.depth = depths
    pred.processed_images = processed_images
    pred.conf = confs
    pred.intrinsics = intrinsics_list
    pred.extrinsics = extrinsics_list
    return pred

# ----------------------------
# SAM MASK
# ----------------------------
def get_car_mask(predictor, image_rgb):
    h, w = image_rgb.shape[:2]
    input_points = np.array([
        [w // 2, h // 2],
        [w // 2, h // 3],
        [w // 2, 2 * h // 3],
        [w // 3, h // 2],
        [2 * w // 3, h // 2],
    ])
    input_labels = np.array([1, 1, 1, 1, 1])
    predictor.set_image(image_rgb)
    masks, scores, _ = predictor.predict(
        point_coords=input_points,
        point_labels=input_labels,
        multimask_output=True
    )
    best_mask = masks[np.argmax(scores)].astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    best_mask = cv2.morphologyEx(best_mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    best_mask = cv2.morphologyEx(best_mask, cv2.MORPH_OPEN, kernel, iterations=2)
    num_labels, labels_im = cv2.connectedComponents(best_mask)
    if num_labels > 1:
        sizes = np.bincount(labels_im.flatten())
        sizes[0] = 0
        best_mask = (labels_im == np.argmax(sizes)).astype(np.uint8)
    return best_mask

# ----------------------------
# MASK GENERATION
# ----------------------------
def generate_masks(image_files, masks_path, sam_predictor):
    print("Maskeler oluşturuluyor...")
    mask_files = []
    for img_path in image_files:
        mask_path = os.path.join(
            masks_path,
            os.path.splitext(os.path.basename(img_path))[0] + "_mask.png"
        )
        if os.path.exists(mask_path):
            print(f"  Mevcut: {os.path.basename(mask_path)}")
            mask_files.append(mask_path)
            continue
        image_bgr = cv2.imread(img_path)
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mask = get_car_mask(sam_predictor, image_rgb)
        cv2.imwrite(mask_path, mask * 255)
        print(f"  Oluşturuldu: {os.path.basename(mask_path)}")
        mask_files.append(mask_path)
    return mask_files

# ----------------------------
# IMAGE LOADING
# ----------------------------
def load_images_from_folder(data_path, extensions=["*.jpg", "*.png", "*.jpeg", "*.jfif"]):
    image_files = []
    for ext in extensions:
        image_files.extend(sorted(glob.glob(os.path.join(data_path, ext))))
    print(f"Found {len(image_files)} images in {data_path}")
    return image_files

# ----------------------------
# POINT CLOUD
# ----------------------------
def depth_to_point_cloud(depth_map, rgb_image, intrinsics, extrinsics, car_mask, conf_map=None, conf_thresh=0.5):
    h, w = depth_map.shape
    fx, fy = intrinsics[0, 0], intrinsics[1, 1]
    cx, cy = intrinsics[0, 2], intrinsics[1, 2]

    if car_mask.shape != (h, w):
        car_mask = cv2.resize(car_mask, (w, h), interpolation=cv2.INTER_NEAREST)

    u, v = np.meshgrid(np.arange(w), np.arange(h))
    valid = car_mask > 0

    if conf_map is not None:
        if conf_map.shape != (h, w):
            conf_map = cv2.resize(conf_map.astype(np.float32), (w, h))
        valid = valid & (conf_map > conf_thresh)

    u = u[valid]; v = v[valid]
    d = depth_map[valid]
    rgb = rgb_image[valid]

    if len(u) == 0:
        return np.zeros((0, 3)), np.zeros((0, 3))

    x = (u - cx) * d / fx
    y = (v - cy) * d / fy
    z = d
    points_cam = np.stack([x, y, z], axis=-1)
    R = extrinsics[:3, :3]
    t = extrinsics[:3, 3]
    points_world = (points_cam - t) @ np.linalg.inv(R).T
    colors = rgb.astype(np.float32) / 255.0
    return points_world, colors

# ----------------------------
# MERGE POINT CLOUD
# ----------------------------
def merge_point_clouds(prediction, mask_files, conf_thresh=0.5):
    all_points = []
    all_colors = []
    for i in range(len(prediction.depth)):
        mask_img = cv2.imread(mask_files[i], cv2.IMREAD_GRAYSCALE)
        car_mask = (mask_img > 127).astype(np.uint8)
        points, colors = depth_to_point_cloud(
            prediction.depth[i],
            prediction.processed_images[i],
            prediction.intrinsics[i],
            prediction.extrinsics[i],
            car_mask,
            prediction.conf[i],
            conf_thresh
        )
        if len(points) > 0:
            all_points.append(points)
            all_colors.append(colors)
        print(f"  Foto {i+1}: {len(points)} nokta")

    if not all_points:
        return np.zeros((0, 3)), np.zeros((0, 3))

    return np.vstack(all_points), np.vstack(all_colors)

# ----------------------------
# CLEAN POINT CLOUD
# ----------------------------
def clean_point_cloud_open3d(points_3d, colors_3d):
    print(f"  Temizlik başlıyor: {len(points_3d)} nokta")
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points_3d)
    pcd.colors = o3d.utility.Vector3dVector(colors_3d if colors_3d.max() <= 1.0 else colors_3d / 255.0)

    pcd, ind = pcd.remove_statistical_outlier(nb_neighbors=50, std_ratio=5.0)
    pcd = pcd.select_by_index(ind)
    print(f"  Statistical sonrası: {len(pcd.points)}")

    pts = np.asarray(pcd.points)
    cx, cy, cz = np.median(pts[:, 0]), np.median(pts[:, 1]), np.median(pts[:, 2])
    bbox = o3d.geometry.AxisAlignedBoundingBox(
        min_bound=(cx - 1.2, cy - 0.8, cz - 0.5),
        max_bound=(cx + 1.2, cy + 0.8, cz + 2.0)
    )
    pcd = pcd.crop(bbox)
    print(f"  Bbox sonrası: {len(pcd.points)}")
    return np.asarray(pcd.points), np.asarray(pcd.colors)

def clean_point_cloud_scipy(points_3d, colors_3d, nb_neighbors=20, std_ratio=2.0):
    from scipy.spatial import cKDTree
    tree = cKDTree(points_3d)
    distances, _ = tree.query(points_3d, k=nb_neighbors)
    mean_distances = np.mean(distances[:, 1:], axis=1)
    threshold = np.mean(mean_distances) + std_ratio * np.std(mean_distances)
    mask = mean_distances < threshold
    return points_3d[mask], colors_3d[mask]

# ----------------------------
# MESH GENERATION
# ----------------------------
def create_mesh(points, colors):
    print("\n=== Renkli Mesh Oluşturuluyor ===")
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors if colors.max() <= 1.0 else colors / 255.0)

    pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
    pcd.orient_normals_consistent_tangent_plane(10)

    print("-> Yüzey örülüyor (Poisson)...")
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=9)

    densities = np.asarray(densities)
    mesh.remove_vertices_by_mask(densities < np.quantile(densities, 0.02))
    mesh.remove_degenerate_triangles()
    mesh.remove_duplicated_triangles()
    mesh.remove_duplicated_vertices()
    mesh.remove_non_manifold_edges()

    print("✅ Renkli mesh hazır.")
    return mesh

# ----------------------------
# ANA FONKSİYON
# ----------------------------
def generate_3d_model(input_dir, output_dir, sam_predictor, da3_model):
    if isinstance(da3_model, tuple):
        model, device = da3_model
    else:
        model = da3_model
        device = next(model.parameters()).device

    print("\n=== Fotoğraflar yükleniyor ===")
    image_files = load_images_from_folder(input_dir)
    if not image_files:
        print("Hiç fotoğraf bulunamadı!")
        return None

    masks_path = os.path.join(output_dir, "masks")
    os.makedirs(masks_path, exist_ok=True)

    print("\n=== Maskeler oluşturuluyor ===")
    mask_files = generate_masks(image_files, masks_path, sam_predictor)

    print("\n=== DA V2 Derinlik çıkarımı yapılıyor ===")
    prediction = run_da3_inference(model, device, image_files)

    print("\n=== Point cloud birleştiriliyor ===")
    points_3d, colors_3d = merge_point_clouds(prediction, mask_files, conf_thresh=0.5)

    if len(points_3d) == 0:
        print("Nokta bulunamadı, çıkılıyor.")
        return None

    pcd_raw = o3d.geometry.PointCloud()
    pcd_raw.points = o3d.utility.Vector3dVector(points_3d)
    pcd_raw.colors = o3d.utility.Vector3dVector(colors_3d)
    o3d.io.write_point_cloud(os.path.join(output_dir, "ham.ply"), pcd_raw)

    print("\n=== Temizleniyor ===")
    try:
        clean_pts, clean_cols = clean_point_cloud_open3d(points_3d, colors_3d)
    except Exception as e:
        print("Open3D failed:", e)
        clean_pts, clean_cols = clean_point_cloud_scipy(points_3d, colors_3d)

    pcd_clean = o3d.geometry.PointCloud()
    pcd_clean.points = o3d.utility.Vector3dVector(clean_pts)
    pcd_clean.colors = o3d.utility.Vector3dVector(clean_cols)
    o3d.io.write_point_cloud(os.path.join(output_dir, "temiz.ply"), pcd_clean)

    mesh = create_mesh(clean_pts, clean_cols)

    final_glb_path = None
    if mesh is not None:
        o3d.io.write_triangle_mesh(os.path.join(output_dir, "araba_mesh.ply"), mesh)
        print(f"✅ Mesh (PLY) kaydedildi.")

        mesh_path_glb = os.path.join(output_dir, "araba_modeli.glb")
        try:
            o3d.io.write_triangle_mesh(mesh_path_glb, mesh)
            print(f"🚀 GLB HAZIR: {mesh_path_glb}")
            final_glb_path = mesh_path_glb
        except Exception as e:
            mesh_path_gltf = os.path.join(output_dir, "araba_modeli.gltf")
            o3d.io.write_triangle_mesh(mesh_path_gltf, mesh)
            print(f"🚀 GLTF HAZIR: {mesh_path_gltf}")
            final_glb_path = mesh_path_gltf

    print(f"\n✓ İşlem tamamlandı — {len(clean_pts)} nokta işlendi.")
    return final_glb_path


if __name__ == "__main__":
    paths = setup_paths()
    print("Paths hazır.")

    print("\n=== DA V2 modeli yükleniyor ===")
    da3_model, device = load_da3_model()

    print("\n=== SAM modeli yükleniyor ===")
    sam_predictor = load_sam_model(paths["sam_checkpoint"])

    generate_3d_model(paths["data"], paths["results"], sam_predictor, (da3_model, device))