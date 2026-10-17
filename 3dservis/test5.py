import glob
import os
import time
import torch
import numpy as np
import cv2
import open3d as o3d
import matplotlib.pyplot as plt
from segment_anything import sam_model_registry, SamPredictor
from depth_anything_3.api import DepthAnything3

    
# ----------------------------
# VISUALIZATION 
# ----------------------------
def visualize_depth_and_confidence(images, depths, confidences, sample_idx=0):#sample_idx ne demek = 
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

def visualize_point_cloud_open3d(points, colors=None, window_name="Point Cloud"):
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

# ----------------------------
# MODEL LOAD 
# ----------------------------
def load_da3_model():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Kullanılan cihaz: {device}")
    torch.cuda.empty_cache()
    model = DepthAnything3.from_pretrained("depth-anything/DA3-LARGE")
    model = model.to(device)
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
            print(f" Mevcut: {os.path.basename(mask_path)}")
            mask_files.append(mask_path)
            continue
        image_bgr = cv2.imread(img_path)
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mask = get_car_mask(sam_predictor, image_rgb)
        cv2.imwrite(mask_path, mask * 255)
        print(f" Oluşturuldu: {os.path.basename(mask_path)}")
        mask_files.append(mask_path)
    return mask_files

# ----------------------------09u
# IMAGE LOADING
# ----------------------------
def load_images_from_folder(data_path, extensions=["*.jpg", "*.png", "*.jpeg", "*.jfif"]):
    image_files = []
    for ext in extensions:
        image_files.extend(sorted(glob.glob(os.path.join(data_path, ext))))
    print(f"Found {len(image_files)} images in {data_path}")
    return image_files


# ----------------------------
# DEPTH INFERENCE
# ----------------------------
def run_da3_inference(model, image_files):
    torch.cuda.empty_cache()
    prediction = model.inference(
        image=image_files,
        infer_gs=True,
        process_res_method="upper_bound_resize"
    )
    return prediction

# ----------------------------
# POINT CLOUD — maske ile
# ----------------------------
def depth_to_point_cloud(depth_map, rgb_image, intrinsics, extrinsics, car_mask, conf_map=None, conf_thresh=0.7):
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
    depth_map = depth_map[valid]
    rgb_image = rgb_image[valid]
    if len(u) == 0:
        return np.zeros((0, 3)), np.zeros((0, 3))
    x = (u - cx) * depth_map / fx
    y = (v - cy) * depth_map / fy
    z = depth_map
    points_cam = np.stack([x, y, z], axis=-1)
    R = extrinsics[:3, :3]
    t = extrinsics[:3, 3]
    points_world = (points_cam - t) @ np.linalg.inv(R).T
    colors = rgb_image.astype(np.float32) / 255.0
    return points_world, colors

# ----------------------------
# MERGE POINT CLOUD — maske ile
# ----------------------------
def merge_point_clouds(prediction, mask_files, conf_thresh=0.7):
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
        print(f" Foto {i+1}: {len(points)} nokta")
    merged_points = np.vstack(all_points)
    merged_colors = np.vstack(all_colors)
    print(f"Toplam: {len(merged_points)} nokta")
    return merged_points, merged_colors


# ----------------------------
# CLEAN POINT CLOUD
# ----------------------------
def clean_point_cloud_open3d(points_3d, colors_3d):
    """
    Scipy ile statistical outlier — abort yok, arabadan nokta silmez.
    Open3D remove_statistical_outlier 100k+ noktada C++ abort ediyor,
    bu yüzden scipy KD-tree kullanıyoruz. Voxel YOK, araba yoğunluğu korunur.
    """
    from scipy.spatial import cKDTree

    print(f" Temizlik başlıyor: {len(points_3d)} nokta")
    if colors_3d.max() > 1.0:
        colors_3d = colors_3d / 255.0

    # --- Scipy statistical outlier (std_ratio=5.0, orijinalin aynısı) ---
    print(" Scipy outlier hesaplanıyor (10-20 sn sürebilir)...")
    tree = cKDTree(points_3d)
    distances, _ = tree.query(points_3d, k=21)   # 20 komşu + kendisi
    mean_d = distances[:, 1:].mean(axis=1)        # kendisi hariç
    threshold = mean_d.mean() + 5.0 * mean_d.std()
    mask = mean_d < threshold
    points_3d = points_3d[mask]
    colors_3d  = colors_3d[mask]
    print(f" Statistical sonrası: {len(points_3d)} nokta")

    # --- Adaptif bbox: %0.5-%99.5 → sadece gerçek uçan noktalar gider ---
    if len(points_3d) > 0:
        lo = np.percentile(points_3d, 0.5, axis=0)
        hi = np.percentile(points_3d, 99.5, axis=0)
        margin = (hi - lo) * 0.05
        mask_b = np.all((points_3d >= lo - margin) & (points_3d <= hi + margin), axis=1)
        points_3d = points_3d[mask_b]
        colors_3d  = colors_3d[mask_b]
        print(f" Bbox sonrası: {len(points_3d)} nokta")

    return points_3d, colors_3d


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

    # 1. Normalleri hesapla (yüzey için şart)
    pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
    pcd.orient_normals_consistent_tangent_plane(10)

    # 2. Poisson Mesh
    print("-> Yüzey örülüyor (Poisson)...")
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=9)

    # 3. Gereksiz kısımları temizle
    print("-> Renkler mesh üzerine mühürleniyor...")
    densities = np.asarray(densities)
    mesh.remove_vertices_by_mask(densities < np.quantile(densities, 0.02))

    # Mesh'i temizle
    mesh.remove_degenerate_triangles()
    mesh.remove_duplicated_triangles()
    mesh.remove_duplicated_vertices()
    mesh.remove_non_manifold_edges()

    print("Renkli mesh hazır.")
    return mesh

# ----------------------------
# BACKEND ENTEGRASYONU
# ----------------------------
def fotograflari_indir(scan_id, scan_images, backend_url):
    """Backend'den fotoğrafları indir, klasör yolunu döndür."""
    import requests
    klasor = os.path.join("temp_scans", str(scan_id))
    os.makedirs(klasor, exist_ok=True)
    for i, img in enumerate(scan_images):
        url = img.get("image_url", "")
        if not url.startswith("http"):
            url = f"{backend_url}/{url}"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with open(os.path.join(klasor, f"{i:04d}.jpg"), "wb") as f:
            f.write(r.content)
    return klasor

def glb_yukle(scan_id, glb_path, backend_url, admin_key):
    """GLB dosyasını backend'e yükle."""
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

def generate_3d_model(input_dir, output_dir, sam_predictor, da3_model):
    """
    servis.py'den çağrılır.
    input_dir : fotoğrafların olduğu klasör
    output_dir: GLB çıktısının kaydedileceği klasör
    Döner     : glb_path (str) veya None
    """
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

    print("\n=== DA3 çıkarımı yapılıyor ===")
    prediction = run_da3_inference(model, image_files)

    print("\n=== Point cloud birleştiriliyor ===")
    points_3d, colors_3d = merge_point_clouds(prediction, mask_files, conf_thresh=0.7)

    if len(points_3d) == 0:
        print("Nokta bulunamadı!")
        return None

    pcd_raw = o3d.geometry.PointCloud()
    pcd_raw.points = o3d.utility.Vector3dVector(points_3d)
    pcd_raw.colors = o3d.utility.Vector3dVector(colors_3d / 255.0 if colors_3d.max() > 1 else colors_3d)
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
    if mesh is None:
        return None

    o3d.io.write_triangle_mesh(os.path.join(output_dir, "araba_mesh.ply"), mesh)

    glb_path = os.path.join(output_dir, "araba_modeli.glb")
    try:
        o3d.io.write_triangle_mesh(glb_path, mesh)
        print(f"🚀 GLB HAZIR: {glb_path}")
    except Exception as e:
        glb_path = os.path.join(output_dir, "araba_modeli.gltf")
        o3d.io.write_triangle_mesh(glb_path, mesh)
        print(f"🚀 GLTF HAZIR: {glb_path}")

    print(f"\n✓ İşlem tamamlandı — {len(clean_pts)} nokta işlendi.")
    return glb_path


# ----------------------------
# STANDALONE TEST (direkt çalıştırınca)
# ----------------------------
if __name__ == "__main__":
    paths = setup_paths()
    print("Paths hazır.")

    print("\n=== DA3 modeli yükleniyor ===")
    model, device = load_da3_model()

    print("\n=== SAM modeli yükleniyor ===")
    sam_predictor = load_sam_model(paths["sam_checkpoint"])

    print("\n=== Fotoğraflar yükleniyor ===")
    image_files = load_images_from_folder(paths["data"])

    print("\n=== Maskeler oluşturuluyor ===")
    mask_files = generate_masks(image_files, paths["masks"], sam_predictor)

    print("\n=== DA3 çıkarımı yapılıyor ===")
    prediction = run_da3_inference(model, image_files)

    visualize_depth_and_confidence(
        prediction.processed_images,
        prediction.depth,
        prediction.conf,
        sample_idx=0
    )

    print("\n=== Point cloud birleştiriliyor ===")
    points_3d, colors_3d = merge_point_clouds(prediction, mask_files, conf_thresh=0.7)

    pcd_raw = o3d.geometry.PointCloud()
    pcd_raw.points = o3d.utility.Vector3dVector(points_3d)
    pcd_raw.colors = o3d.utility.Vector3dVector(colors_3d / 255.0 if colors_3d.max() > 1 else colors_3d)
    o3d.io.write_point_cloud(os.path.join(paths["results"], "ham.ply"), pcd_raw)
    visualize_point_cloud_open3d(points_3d, colors_3d, window_name="Ham Point Cloud")

    print("\n=== Temizleniyor ===")
    try:
        clean_pts, clean_cols = clean_point_cloud_open3d(points_3d, colors_3d)
    except Exception as e:
        print("Open3D failed:", e)
        clean_pts, clean_cols = clean_point_cloud_scipy(points_3d, colors_3d)

    pcd_clean = o3d.geometry.PointCloud()
    pcd_clean.points = o3d.utility.Vector3dVector(clean_pts)
    pcd_clean.colors = o3d.utility.Vector3dVector(clean_cols)
    o3d.io.write_point_cloud(os.path.join(paths["results"], "temiz.ply"), pcd_clean)
    visualize_point_cloud_open3d(clean_pts, clean_cols, window_name="Temiz Point Cloud (Araba)")

    mesh = create_mesh(clean_pts, clean_cols)

    if mesh is not None:
        mesh_path = os.path.join(paths["results"], "araba_mesh.ply")
        o3d.io.write_triangle_mesh(mesh_path, mesh)
        print(f" Mesh (PLY) kaydedildi: {mesh_path}")

        mesh_path_glb = os.path.join(paths["results"], "araba_modeli.glb")
        try:
            o3d.io.write_triangle_mesh(mesh_path_glb, mesh)
            print(f" GLB hazır: {mesh_path_glb}")
        except Exception as e:
            mesh_path_gltf = os.path.join(paths["results"], "araba_modeli.gltf")
            o3d.io.write_triangle_mesh(mesh_path_gltf, mesh)
            print(f" GLTF hazır: {mesh_path_gltf}")

        o3d.visualization.draw_geometries([mesh],
                                    window_name="3D Araba Mesh Çıktısı",
                                    mesh_show_back_face=True)

    print(f"\n✓ Tamamlandı — {len(clean_pts)} nokta işlendi.")