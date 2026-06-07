import os
import sys

# === KÜTÜPHANE YOLU BURAYA EKLENDİ ===
# Python'a Depth Anything 3 kaynak kodlarının nerede olduğunu söylüyoruz
sys.path.insert(0, r'D:\MODIFIAI\3dservis\Depth-Anything-3\src')

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

# ============================================================
# DA3-BASE (Apache 2.0 — Ticari Kullanıma Uygun)
# ============================================================

# ----------------------------
# VISUALIZATION
# ----------------------------
def visualize_depth_and_confidence(images, depths, confidences, sample_idx=0):
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
    model = DepthAnything3.from_pretrained("depth-anything/DA3-BASE")
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
    
    erosion_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    best_mask = cv2.erode(best_mask, erosion_kernel, iterations=1)
    
    num_labels, labels_im = cv2.connectedComponents(best_mask)
    if num_labels > 1:
        sizes = np.bincount(labels_im.flatten())
        sizes[0] = 0
        best_mask = (labels_im == np.argmax(sizes)).astype(np.uint8)
    return best_mask

# ----------------------------
# UNICODE PATH HELPERS
# ----------------------------
def cv2_imread_unicode(path, flags=cv2.IMREAD_COLOR):
    try:
        return cv2.imdecode(np.fromfile(path, dtype=np.uint8), flags)
    except Exception as e:
        print(f"Error reading unicode path {path}: {e}")
        return None

def cv2_imwrite_unicode(path, img, params=None):
    try:
        ext = os.path.splitext(path)[1]
        result, nparr = cv2.imencode(ext, img, params)
        if result:
            nparr.tofile(path)
            return True
        return False
    except Exception as e:
        print(f"Error writing unicode path {path}: {e}")
        return False

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
        image_bgr = cv2_imread_unicode(img_path)
        if image_bgr is None:
            continue
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mask = get_car_mask(sam_predictor, image_rgb)
        cv2_imwrite_unicode(mask_path, mask * 255)
        print(f" Oluşturuldu: {os.path.basename(mask_path)}")
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
# DEPTH INFERENCE
# ----------------------------
def run_da3_inference(model, image_files):
    torch.cuda.empty_cache()
    prediction = model.inference(
        image=image_files,
        process_res=504,
        process_res_method="lower_bound_resize"
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
    
    car_depths = depth_map[car_mask > 0]
    if len(car_depths) > 0:
        depth_upper_bound = np.percentile(car_depths, 90) * 1.2
        valid = (car_mask > 0) & (depth_map < depth_upper_bound)
    else:
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
# MERGE POINT CLOUD
# ----------------------------
def merge_point_clouds(prediction, mask_files, conf_thresh=0.85):
    all_points = []
    all_colors = []
    for i in range(len(prediction.depth)):
        mask_img = cv2_imread_unicode(mask_files[i], cv2.IMREAD_GRAYSCALE)
        if mask_img is None:
            continue
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
    if not all_points:
        return np.zeros((0, 3)), np.zeros((0, 3))
    merged_points = np.vstack(all_points)
    merged_colors = np.vstack(all_colors)
    print(f"Toplam: {len(merged_points)} nokta")
    return merged_points, merged_colors

# ----------------------------
# CLEAN POINT CLOUD
# ----------------------------
def clean_point_cloud_open3d(points_3d, colors_3d):
    from scipy.spatial import cKDTree
    
    print(f" Temizlik basliyor: {len(points_3d)} nokta")
    if colors_3d.max() > 1.0:
        colors_3d = colors_3d / 255.0
        
    pcd_init = o3d.geometry.PointCloud()
    pcd_init.points = o3d.utility.Vector3dVector(points_3d)
    pcd_init.colors = o3d.utility.Vector3dVector(colors_3d)
    
    pcd_down = pcd_init.voxel_down_sample(voxel_size=0.015)
    points_3d = np.asarray(pcd_down.points)
    colors_3d = np.asarray(pcd_down.colors)
    print(f" Voxel Downsample sonrasi: {len(points_3d)} nokta")

    print(" Scipy 1. tur outlier hesaplaniyor...")
    tree = cKDTree(points_3d)
    distances, _ = tree.query(points_3d, k=21)
    mean_d = distances[:, 1:].mean(axis=1)
    threshold = mean_d.mean() + 5.0 * mean_d.std()
    mask = mean_d < threshold
    points_3d = points_3d[mask]
    colors_3d  = colors_3d[mask]

    if len(points_3d) > 0:
        lo = np.percentile(points_3d, 0.5, axis=0)
        hi = np.percentile(points_3d, 99.5, axis=0)
        margin = (hi - lo) * 0.05
        mask_b = np.all((points_3d >= lo - margin) & (points_3d <= hi + margin), axis=1)
        points_3d = points_3d[mask_b]
        colors_3d  = colors_3d[mask_b]

    if len(points_3d) > 100:
        pcd_tmp = o3d.geometry.PointCloud()
        pcd_tmp.points = o3d.utility.Vector3dVector(points_3d)
        pcd_tmp.colors = o3d.utility.Vector3dVector(colors_3d)
        cl, ind = pcd_tmp.remove_radius_outlier(nb_points=28, radius=0.18)
        points_3d = points_3d[ind]
        colors_3d  = colors_3d[ind]
        print(f" Radius Outlier sonrasi: {len(points_3d)} nokta ✓")

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
    print("\n=== Renkli Mesh Olusturuluyor ===")
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors if colors.max() <= 1.0 else colors / 255.0)
    
    # Normal tahmini parametreleri iyileştirildi
    pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.20, max_nn=40))
    
    # === İYİLEŞTİRME: Sabit düzlem yerine normalleri merkeze doğru yönlendirerek balonlaşma önlendi ===
    # === DOĞRU VE GÜVENLİ KISIM ===
    araba_merkezi = pcd.get_center()
    pcd.orient_normals_towards_camera_location(camera_location=araba_merkezi)
    
    print("-> Yuzey oruluyor (Poisson depth=8)...")
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson (pcd, depth=9, width=0 , scale=1.1 , linear_fit=False)
    
    print("-> Dusuk yogunluklu bolgeler temizleniyor...")
    densities = np.asarray(densities)
    mesh.remove_vertices_by_mask(densities < np.quantile(densities, 0.05))
    mesh.remove_degenerate_triangles()
    mesh.remove_duplicated_triangles()
    mesh.remove_duplicated_vertices()
    mesh.remove_non_manifold_edges()
    mesh = mesh.remove_unreferenced_vertices()

    print("-> Kucuk fragment'lar temizleniyor...")
    triangle_clusters, cluster_n_triangles, _ = mesh.cluster_connected_triangles()
    triangle_clusters = np.asarray(triangle_clusters)
    cluster_n_triangles = np.asarray(cluster_n_triangles)
    if len(cluster_n_triangles) > 0:
        largest_cluster_idx = cluster_n_triangles.argmax()
        triangles_to_remove = triangle_clusters != largest_cluster_idx
        mesh.remove_triangles_by_mask(triangles_to_remove)
        mesh = mesh.remove_unreferenced_vertices()

    max_triangles = 500000
    if len(mesh.triangles) > max_triangles:
        print(f"-> Mesh sadelestiriliyor...")
        mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=max_triangles)
        mesh = mesh.remove_unreferenced_vertices()

    print("-> Taubin yumusatma uygulaniyor...")
    mesh = mesh.filter_smooth_taubin(number_of_iterations=4)
    mesh = mesh.remove_unreferenced_vertices()

    mesh.compute_vertex_normals()
    print("Renkli mesh hazir.")
    return mesh

# ----------------------------
# MAIN GENERATE FUNCTION
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

    print("\n=== DA3-BASE çıkarımı yapılıyor ===")
    prediction = run_da3_inference(model, image_files)

    print("\n=== Point cloud birleştiriliyor ===")
    points_3d, colors_3d = merge_point_clouds(prediction, mask_files, conf_thresh=0.5)

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
        import trimesh
        vertices = np.asarray(mesh.vertices)
        faces = np.asarray(mesh.triangles)
        vertex_colors = np.asarray(mesh.vertex_colors)
        
        if len(vertex_colors) > 0:
            colors_uint8 = (vertex_colors * 255.0).astype(np.uint8)
            tri_mesh = trimesh.Trimesh(vertices=vertices, faces=faces, vertex_colors=colors_uint8)
        else:
            tri_mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
            
        trimesh.smoothing.filter_laplacian(tri_mesh, lamb=0.5, iterations=4)
        tri_mesh.export(glb_path)
        print(f"[OK] GLB HAZIR: {glb_path}")
    except Exception as e:
        print(f"Trimesh export failed: {e}")
        o3d.io.write_triangle_mesh(glb_path, mesh)
    return glb_path

# ----------------------------
# STANDALONE TEST
# ----------------------------
# ----------------------------
# STANDALONE TEST (Sadece dosyayı direkt çalıştırırsan çalışır)
# ----------------------------
if __name__ == "__main__":
    # Sabit yerel klasör yollarını doğrudan burada tanımlıyoruz, 
    # böylece dışarıda setup_paths fonksiyonu aramasına gerek kalmıyor.
    base_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
    
    local_paths = {
        "data": os.path.join(base_dir, "data"),
        "masks": os.path.join(base_dir, "masks"),
        "results": os.path.join(base_dir, "results"),
        "sam_checkpoint": r"D:\MODIFIAI\3dservis\SAM\sam_vit_h_4b8939.pth" # Senin bilgisayarındaki gerçek SAM yolu
    }

    # Klasörlerin varlığını kontrol et/oluştur
    os.makedirs(local_paths["data"], exist_ok=True)
    os.makedirs(local_paths["masks"], exist_ok=True)
    os.makedirs(local_paths["results"], exist_ok=True)

    print("Yerel test yolları hazır.")

    print("\n=== DA3-BASE modeli yükleniyor ===")
    model, device = load_da3_model()

    print("\n=== SAM modeli yükleniyor ===")
    sam_predictor = load_sam_model(local_paths["sam_checkpoint"])

    print("\n=== Fotoğraflar yükleniyor ===")
    image_files = load_images_from_folder(local_paths["data"])

    if len(image_files) == 0:
        print(f"Lütfen yerel test için '{local_paths['data']}' klasörüne birkaç araba fotoğrafı ekleyin!")
    else:
        mask_files = generate_masks(image_files, local_paths["masks"], sam_predictor)
        prediction = run_da3_inference(model, image_files)

        visualize_depth_and_confidence(
            prediction.processed_images,
            prediction.depth,
            prediction.conf,
            sample_idx=0
        )

        print("\n=== Point cloud birleştiriliyor ===")
        points_3d, colors_3d = merge_point_clouds(prediction, mask_files, conf_thresh=0.5)

        if len(points_3d) > 0:
            pcd_raw = o3d.geometry.PointCloud()
            pcd_raw.points = o3d.utility.Vector3dVector(points_3d)
            pcd_raw.colors = o3d.utility.Vector3dVector(colors_3d / 255.0 if colors_3d.max() > 1 else colors_3d)
            o3d.io.write_point_cloud(os.path.join(local_paths["results"], "ham.ply"), pcd_raw)

            print("\n=== Temizleniyor ===")
            clean_pts, clean_cols = clean_point_cloud_open3d(points_3d, colors_3d)

            mesh = create_mesh(clean_pts, clean_cols)
            if mesh is not None:
                mesh_path_glb = os.path.join(local_paths["results"], "araba_modeli.glb")
                o3d.io.write_triangle_mesh(mesh_path_glb, mesh)
                print(f"[OK] Yerel test bitti. Model: {mesh_path_glb}")
                o3d.visualization.draw_geometries([mesh], window_name="3D Çıktı", mesh_show_back_face=True)