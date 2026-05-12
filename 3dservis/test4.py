import glob
import os
import time
import torch
import numpy as np
import cv2
import open3d as o3d
from segment_anything import sam_model_registry, SamPredictor
from depth_anything_3.api import DepthAnything3


# ---------------------------
# YOLLAR
# ---------------------------
def setup_paths():
    paths = {
        "data":    r"C:\Users\Turkuaz\Desktop\segmentasyon\images",
        "results": r"C:\Users\Turkuaz\Desktop\segmentasyon\output",
        "masks":   r"C:\Users\Turkuaz\Desktop\segmentasyon\output\masks",
        "sam_checkpoint": r"C:\Users\Turkuaz\Desktop\segmentasyon\SAM\sam_vit_h_4b8939.pth"
    }
    os.makedirs(paths["results"], exist_ok=True)
    os.makedirs(paths["masks"],   exist_ok=True)
    return paths


# ---------------------------
# MODEL YÜKLEME
# ---------------------------
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
    print("SAM1 hazır.")
    return predictor



def load_images_from_folder(data_path, extensions=("*.jpg", "*.png", "*.jpeg", "*.jfif")):
    image_files = []
    for ext in extensions:
        image_files.extend(sorted(glob.glob(os.path.join(data_path, ext))))
    print(f"{len(image_files)} fotoğraf bulundu.")
    return image_files



# SAM1 İLE ARABA MASKESİ

def get_car_mask_sam1(predictor, image_rgb):
    h, w = image_rgb.shape[:2]

    input_points = np.array([
        [w // 2,       h // 2      ],
        [w // 2,       h // 3      ],
        [w // 2,       2 * h // 3  ],
        [w // 3,       h // 2      ],
        [2 * w // 3,   h // 2      ],
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
    best_mask = cv2.morphologyEx(best_mask, cv2.MORPH_OPEN,  kernel, iterations=2)

    return best_mask


# ---------------------------
# TÜM FOTOĞRAFLAR İÇİN MASKE
# ---------------------------
def generate_masks(image_files, masks_path, sam_predictor):
    print("Araba maskeleri oluşturuluyor...")
    mask_files = []

    for img_path in image_files:
        mask_path = os.path.join(
            masks_path,
            os.path.splitext(os.path.basename(img_path))[0] + "_mask.png"
        )

        if os.path.exists(mask_path):
            print(f"  Mevcut maske kullanılıyor: {os.path.basename(mask_path)}")
            mask_files.append(mask_path)
            continue

        image_bgr = cv2.imread(img_path)
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mask = get_car_mask_sam1(sam_predictor, image_rgb)
        cv2.imwrite(mask_path, mask * 255)
        print(f"  Maske oluşturuldu: {os.path.basename(img_path)}")
        mask_files.append(mask_path)

    return mask_files


# ---------------------------
# DA3 ÇIKARIMI
# ---------------------------
def run_da3_inference(model, image_files, process_res_method="upper_bound_resize"):
    torch.cuda.empty_cache()  # inference öncesi VRAM temizle
    prediction = model.inference(
        image=image_files,
        infer_gs=True,
        process_res_method="lower_bound_resize"  # daha düşük çözünürlük
    )
    return prediction
# ---------------------------
# DERİNLİKTEN POINT CLOUD — maske ile
# ---------------------------
def depth_to_point_cloud_masked(depth_map, rgb_image, intrinsics, extrinsics,
                                  car_mask, conf_map=None, conf_thresh=0.97):
    h, w = depth_map.shape
    fx, fy = intrinsics[0, 0], intrinsics[1, 1]
    cx, cy = intrinsics[0, 2], intrinsics[1, 2]

    if car_mask.shape != (h, w):
        car_mask = cv2.resize(car_mask, (w, h), interpolation=cv2.INTER_NEAREST)

    u, v = np.meshgrid(np.arange(w), np.arange(h))

    if conf_map is not None:
        if conf_map.shape != (h, w):
            conf_map = cv2.resize(conf_map.astype(np.float32), (w, h))
        combined_mask = (conf_map > conf_thresh) & (car_mask > 0)
    else:
        combined_mask = car_mask > 0

    u         = u[combined_mask]
    v         = v[combined_mask]
    depth_sel = depth_map[combined_mask]
    rgb_sel   = rgb_image[combined_mask]

    if len(u) == 0:
        return np.zeros((0, 3)), np.zeros((0, 3))

    valid = (depth_sel > 0.4) & (depth_sel < 1.8)
    u, v, depth_sel, rgb_sel = u[valid], v[valid], depth_sel[valid], rgb_sel[valid]

    if len(u) == 0:
        return np.zeros((0, 3)), np.zeros((0, 3))

    x = (u - cx) * depth_sel / fx
    y = (v - cy) * depth_sel / fy
    z = depth_sel
    points_cam = np.stack([x, y, z], axis=-1)

    R = extrinsics[:3, :3]
    t = extrinsics[:3, 3]
    points_world = (points_cam - t) @ np.linalg.inv(R).T

    colors = rgb_sel.astype(np.float32) / 255.0
    return points_world, colors


# ---------------------------
# MERGE
# ---------------------------
def merge_point_clouds(prediction, mask_files, conf_thresh=0.97):
    t = time.time()
    print("Point cloud'lar birleştiriliyor...")

    all_points = []
    all_colors = []

    for i in range(len(prediction.depth)):
        mask_img = cv2.imread(mask_files[i], cv2.IMREAD_GRAYSCALE)
        car_mask = (mask_img > 127).astype(np.uint8)

        pts, cols = depth_to_point_cloud_masked(
            prediction.depth[i],
            prediction.processed_images[i],
            prediction.intrinsics[i],
            prediction.extrinsics[i],
            car_mask,
            prediction.conf[i],
            conf_thresh
        )

        if len(pts) > 0:
            all_points.append(pts)
            all_colors.append(cols)
            print(f"  Fotoğraf {i+1}: {len(pts)} nokta")

    points_merged = np.concatenate(all_points, axis=0)
    colors_merged = np.concatenate(all_colors, axis=0)
    print(f"Birleştirme: {time.time()-t:.1f}s — toplam {len(points_merged)} nokta")
    return points_merged, colors_merged


# ---------------------------
# İNCE ICP HİZALAMA — kaymaları düzelt
# FIX: ön taraftaki kaymalar için eklendi
# ---------------------------
def refine_alignment_icp(points_3d, colors_3d):
    t = time.time()
    print("ICP hizalaması yapılıyor...")

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points_3d)
    pcd.colors = o3d.utility.Vector3dVector(colors_3d)

    # Voxel down-sample — ICP'yi hızlandırır
    pcd_down = pcd.voxel_down_sample(voxel_size=0.008)
    pcd_down.estimate_normals(
        o3d.geometry.KDTreeSearchParamHybrid(radius=0.02, max_nn=30)
    )
    pcd_down.orient_normals_consistent_tangent_plane(k=15)

    # Point cloud'u iki yarıya böl: ilk yarı referans, ikinci yarı hizalanacak
    n = len(pcd_down.points)
    half = n // 2
    source = pcd_down.select_by_index(list(range(half, n)))
    target = pcd_down.select_by_index(list(range(0, half)))

    reg = o3d.pipelines.registration.registration_icp(
        source, target,
        max_correspondence_distance=0.01,
        init=np.eye(4),
        estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPlane(),
        criteria=o3d.pipelines.registration.ICPConvergenceCriteria(
            max_iteration=50,
            relative_fitness=1e-6,
            relative_rmse=1e-6
        )
    )

    print(f"ICP fitness: {reg.fitness:.4f} — {time.time()-t:.1f}s")
    return np.asarray(pcd.points), np.asarray(pcd.colors)


# ---------------------------
# TEMİZLEME — düzeltilmiş parametreler
# FIX: DBSCAN eps küçültüldü, outlier daha sıkı, 2. tur temizlik eklendi
# ---------------------------
def clean_point_cloud(points_3d, colors_3d):
    t = time.time()
    print("Point cloud temizleniyor...")

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points_3d)
    pcd.colors = o3d.utility.Vector3dVector(colors_3d)

    # 1. Voxel down-sample
    pcd = pcd.voxel_down_sample(voxel_size=0.003)
    print(f"  Voxel sonrası: {len(pcd.points)}")

    # 2. Zemin kaldır
    _, inliers = pcd.segment_plane(
        distance_threshold=0.01, ransac_n=3, num_iterations=1000
    )
    pcd = pcd.select_by_index(inliers, invert=True)
    print(f"  Zemin sonrası: {len(pcd.points)}")

    # 3. Statistical outlier — 1. tur
    pcd, ind = pcd.remove_statistical_outlier(nb_neighbors=30, std_ratio=0.5)
    pcd = pcd.select_by_index(ind)

    # 4. Radius outlier — 1. tur
    pcd, ind = pcd.remove_radius_outlier(nb_points=20, radius=0.01)
    pcd = pcd.select_by_index(ind)

    # 5. DBSCAN — FIX: eps=0.02 (eskiden 0.05, çok büyüktü)
    #    Küçük eps = daha sıkı kümeleme = havadaki pikseller ayrışır
    print("  DBSCAN kümeleme...")
    labels = np.array(
        pcd.cluster_dbscan(eps=0.02, min_points=30, print_progress=False)
    )
    if labels.max() >= 0:
        largest = np.argmax(np.bincount(labels[labels >= 0]))
        pcd = pcd.select_by_index(np.where(labels == largest)[0])
        print(f"  DBSCAN sonrası: {len(pcd.points)}")

    # 6. FIX: 2. tur temizlik — DBSCAN sonrası kalan gürültü için
    pcd, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=0.4)
    pcd = pcd.select_by_index(ind)
    pcd, ind = pcd.remove_radius_outlier(nb_points=15, radius=0.008)
    pcd = pcd.select_by_index(ind)
    print(f"  2. tur temizlik sonrası: {len(pcd.points)}")

    # 7. Araba bbox
    bbox = o3d.geometry.AxisAlignedBoundingBox(
        min_bound=(-1.0, -0.5, -0.1),
        max_bound=( 1.0,  0.5,  2.0)
    )
    pcd = pcd.crop(bbox)

    print(f"Temizlik tamamlandı: {len(pcd.points)} nokta — {time.time()-t:.1f}s")
    return np.asarray(pcd.points), np.asarray(pcd.colors)


# ---------------------------
# NORMAL TAHMİNİ
# ---------------------------
def prepare_pcd_with_normals(points, colors):
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)
    pcd.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.01, max_nn=30))
    pcd.orient_normals_consistent_tangent_plane(k=15)
    return pcd


# ---------------------------
# MESH
# ---------------------------
def poisson_mesh(points, colors):
    t = time.time()
    print("Poisson mesh oluşturuluyor...")
    pcd = prepare_pcd_with_normals(points, colors)
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=9)
    mesh.remove_vertices_by_mask(densities < np.quantile(densities, 0.1))
    mesh = mesh.filter_smooth_taubin(number_of_iterations=10)
    print(f"Poisson mesh: {time.time()-t:.1f}s")
    return mesh


def ball_pivoting_mesh(points, colors):
    t = time.time()
    print("Ball pivoting mesh oluşturuluyor...")
    pcd = prepare_pcd_with_normals(points, colors)
    mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
        pcd, o3d.utility.DoubleVector([0.005, 0.01, 0.02])
    )
    mesh = mesh.filter_smooth_taubin(number_of_iterations=10)
    print(f"Ball pivoting: {time.time()-t:.1f}s")
    return mesh


# ---------------------------
# GÖRSELLEŞTİRME
# ---------------------------
def visualize_point_cloud_open3d(points, colors=None, window_name="Point Cloud"):
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    if colors is not None:
        pcd.colors = o3d.utility.Vector3dVector(colors)
    o3d.visualization.draw_geometries([pcd], window_name=window_name)


# ---------------------------
# KAYDETME
# ---------------------------
def save_results(points, colors, mesh_poisson, mesh_bp, results_path):
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)
    o3d.io.write_point_cloud(os.path.join(results_path, "point_cloud_clean.ply"), pcd)
    o3d.io.write_triangle_mesh(os.path.join(results_path, "mesh_poisson.ply"), mesh_poisson)
    o3d.io.write_triangle_mesh(os.path.join(results_path, "mesh_ball_pivot.ply"), mesh_bp)
    print(f"Kaydedildi: {results_path}")


# ---------------------------
# MAIN
# ---------------------------
if __name__ == "__main__":
    total_start = time.time()
    paths = setup_paths()

    print("\n=== [1/8] DA3 modeli yükleniyor ===")
    model, device = load_da3_model()

    print("\n=== [2/8] SAM1 modeli yükleniyor ===")
    sam_predictor = load_sam_model(paths["sam_checkpoint"])

    print("\n=== [3/8] Fotoğraflar yükleniyor ===")
    image_files = load_images_from_folder(paths["data"])

    print("\n=== [4/8] Araba maskeleri oluşturuluyor ===")
    mask_files = generate_masks(image_files, paths["masks"], sam_predictor)

    print("\n=== [5/8] DA3 çıkarımı (tam fotoğrafla) ===")
    prediction = run_da3_inference(model, image_files)

    print("\n=== [6/8] Point cloud birleştirme ===")
    points_3d, colors_3d = merge_point_clouds(prediction, mask_files, conf_thresh=0.97)
    visualize_point_cloud_open3d(points_3d, colors_3d, "Ham Point Cloud")

    print("\n=== [7/8] Temizleme + hizalama ===")
    # Önce ICP ile kaymaları düzelt
    points_3d, colors_3d = refine_alignment_icp(points_3d, colors_3d)
    # Sonra agresif temizlik
    clean_pts, clean_cols = clean_point_cloud(points_3d, colors_3d)
    visualize_point_cloud_open3d(clean_pts, clean_cols, "Temiz Point Cloud")

    print("\n=== [8/8] Mesh oluşturma ===")
    mesh_poisson = poisson_mesh(clean_pts, clean_cols)
    o3d.visualization.draw_geometries([mesh_poisson], window_name="Poisson Mesh")

    mesh_bp = ball_pivoting_mesh(clean_pts, clean_cols)
    o3d.visualization.draw_geometries([mesh_bp], window_name="Ball Pivoting Mesh")

    save_results(clean_pts, clean_cols, mesh_poisson, mesh_bp, paths["results"])
    print(f"\n✓ Toplam süre: {time.time()-total_start:.1f}s")