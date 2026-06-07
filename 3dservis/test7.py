import os
import sys
import glob
import time
import torch
import numpy as np
import cv2
import subprocess
import shutil
import open3d as o3d
import matplotlib.pyplot as plt
from segment_anything import sam_model_registry, SamPredictor

# === KÜTÜPHANE YOLU ===
sys.path.insert(0, r'D:\MODIFIAI\3dservis\Depth-Anything-3\src')
from depth_anything_3.api import DepthAnything3

# ----------------------------
# 1. VİDEODAN ANAHTAR KARE VE MASKELERİN AYIKLANMASI
# ----------------------------
def extract_keyframes_from_video(video_path, output_data_dir, target_frame_count=24):
    print(f"\n=== Video İşleme Başladı: {os.path.basename(video_path)} ===")
    if not os.path.exists(video_path):
        print(f"❌ Hata: Video dosyası bulunamadı -> {video_path}")
        return False

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    # Eski verileri temizle
    for ef in glob.glob(os.path.join(output_data_dir, "*.png")):
        try: os.remove(ef)
        except: pass

    step = max(1, total_frames // target_frame_count)
    saved_count = 0
    frame_idx = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break
            
        if frame_idx % step == 0 and saved_count < target_frame_count:
            out_name = f"frame_{saved_count:04d}.png"
            cv2.imwrite(os.path.join(output_data_dir, out_name), frame)
            saved_count += 1
        frame_idx += 1

    cap.release()
    print(f"-> [OK] Videodan {saved_count} adet anahtar kare 'data' klasörüne kaydedildi.\n")
    return True

# ----------------------------
# 2. SAM İLE MASKE ÜRETİMİ VE COLMAP FORMATINA UYARLANMASI
# ----------------------------
def get_car_mask(predictor, image_rgb):
    h, w = image_rgb.shape[:2]
    input_points = np.array([[w//2, h//2], [w//2, h//3], [w//2, 2*h//3], [w//3, h//2], [2*w//3, h//2]])
    input_labels = np.array([1, 1, 1, 1, 1])
    
    predictor.set_image(image_rgb)
    masks, scores, _ = predictor.predict(point_coords=input_points, point_labels=input_labels, multimask_output=True)
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

def generate_masks(image_files, masks_path, sam_predictor):
    print("=== SAM Maske Üretimi Başladı ===")
    mask_files = []
    for img_path in image_files:
        base_name = os.path.splitext(os.path.basename(img_path))[0]
        # ÖNEMLİ: COLMAP maskeyi bulabilmek için resimle birebir aynı isimde + '.png.msk' uzantılı isteyebilir 
        # ya da doğrudan görüntünün adı ile maske adı eşleşmelidir. Klasör yapısıyla besleyeceğiz.
        mask_out_path = os.path.join(masks_path, f"{base_name}.png.png") # COLMAP mask klasör eşleşme kuralı
        
        img_bgr = cv2.imread(img_path)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        mask = get_car_mask(sam_predictor, img_rgb)
        
        # COLMAP siyah-beyaz (0-255) maske bekler
        cv2.imwrite(mask_out_path, mask * 255)
        mask_files.append(mask_out_path)
    print("-> [OK] Maskeler COLMAP ve kırpma işlemleri için hazırlandı.\n")
    return mask_files

# ----------------------------
# 3. MASKELENMİŞ COLMAP POZ HESAPLAMA (SIFT Sıkışmalarını Önlemek İçin)
# ----------------------------
def run_colmap_for_extrinsics(data_dir, masks_dir, output_dir):
    print("=== COLMAP Maskeli Kamera Pozu Hesaplama Başladı ===")
    colmap_path = r"D:\MODIFIAI\3dservis\colmap\bin\colmap.exe"
    database_path = os.path.join(output_dir, "database.db")
    sparse_path = os.path.join(output_dir, "sparse")
    
    if os.path.exists(sparse_path):
        try: shutil.rmtree(sparse_path)
        except: pass
    os.makedirs(sparse_path, exist_ok=True)
    
    if os.path.exists(database_path):
        for _ in range(5):
            try: os.remove(database_path); break
            except: time.sleep(0.5)

    try:
        # 1. Feature Extractor + Mask Entegrasyonu (Arka planı ve yansımaları ezerek SIFT'i kurtarır)
        print("-> [COLMAP] Özellikler maskeli olarak çıkarılıyor...")
        subprocess.run([
            colmap_path, "feature_extractor",
            "--database_path", database_path,
            "--image_path", data_dir,
            "--ImageReader.mask_path", masks_dir, # Maske klasörü doğrudan bağlandı
            "--ImageReader.single_camera", "1",
            "--ImageReader.camera_model", "OPENCV"
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 2. Exhaustive Matcher
        print("-> [COLMAP] Özellik eşleştirme yapılıyor...")
        subprocess.run([colmap_path, "exhaustive_matcher", "--database_path", database_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. Mapper
        print("-> [COLMAP] Kamera pozları (Sparse Rekonstrüksiyon) hesaplanıyor...")
        subprocess.run([
            colmap_path, "mapper",
            "--database_path", database_path,
            "--image_path", data_dir,
            "--output_path", sparse_path,
            "--Mapper.num_threads", "4",
            "--Mapper.init_min_tri_angle", "4",
            "--Mapper.multiple_models", "0"
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 0 alt klasörünü üst dizine taşıma
        sparse_0 = os.path.join(sparse_path, "0")
        if os.path.exists(sparse_0):
            for f in os.listdir(sparse_0):
                shutil.copy2(os.path.join(sparse_0, f), os.path.join(sparse_path, f))
        
        # Metin formatına dönüştür
        subprocess.run([
            colmap_path, "model_converter",
            "--input_path", sparse_path,
            "--output_path", sparse_path,
            "--output_type", "TXT"
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print("-> [OK] COLMAP Poz Hesaplama Başarıyla Tamamlandı.\n")
        return True
    except Exception as e:
        print(f"❌ COLMAP Hatası: {e}. Geometri yetersiz veya maskeleme uyuşmazlığı var.")
        return False

# ----------------------------
# 4. PARSERS FOR EXTRINSICS & INTRINSICS
# ----------------------------
def read_colmap_extrinsics_and_intrinsics(sparse_dir, image_files):
    images_txt = os.path.join(sparse_dir, "images.txt")
    cameras_txt = os.path.join(sparse_dir, "cameras.txt")
    
    intrinsics_dict = {}
    if os.path.exists(cameras_txt):
        with open(cameras_txt, "r") as f:
            for line in f:
                if line.startswith("#") or not line.strip(): continue
                elems = line.split()
                cam_id = int(elems[0])
                f_val, cx, cy = float(elems[4]), float(elems[5]), float(elems[6])
                K = np.eye(3)
                K[0, 0], K[1, 1], K[0, 2], K[1, 2] = f_val, f_val, cx, cy
                intrinsics_dict[cam_id] = K

    extrinsics_map = {}
    if os.path.exists(images_txt):
        with open(images_txt, "r") as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if line.startswith("#") or not line: continue
            elems = line.split()
            if len(elems) >= 10 and elems[9].endswith((".png", ".jpg", ".jpeg")):
                qw, qx, qy, qz = map(float, elems[1:5])
                tx, ty, tz = map(float, elems[5:8])
                img_name = elems[9]
                
                # Quaternion to Rotation Matrix
                r00 = 1 - 2*(qy**2 + qz**2); r01 = 2*(qx*qy - qw*qz); r02 = 2*(qx*qz + qw*qy)
                r10 = 2*(qx*qy + qw*qz); r11 = 1 - 2*(qx**2 + qz**2); r12 = 2*(qy*qz - qw*qx)
                r20 = 2*(qx*qz - qw*qy); r21 = 2*(qy*qz + qw*qx); r22 = 1 - 2*(qx**2 + qy**2)
                
                R = np.array([[r00, r01, r02], [r10, r11, r12], [r20, r21, r22]])
                T = np.eye(4)
                T[:3, :3], T[:3, 3] = R, [tx, ty, tz]
                extrinsics_map[img_name] = T

    final_extrinsics, final_intrinsics = [], []
    default_K = np.array([[500, 0, 424], [0, 500, 239], [0, 0, 1]])
    
    for img_path in image_files:
        name = os.path.basename(img_path)
        if name in extrinsics_map:
            final_extrinsics.append(extrinsics_map[name])
            final_intrinsics.append(intrinsics_dict.get(1, default_K))
        else:
            final_extrinsics.append(np.eye(4))
            final_intrinsics.append(default_K)
            
    return final_extrinsics, final_intrinsics

# ----------------------------
# 5. DERİNLİK + GEOMETRİ BİRLEŞTİRME (DÜZELTİLMİŞ NORMAL YÖNLENDİRMESİ)
# ----------------------------
def depth_to_point_cloud(depth_map, rgb_image, intrinsics, extrinsics, car_mask):
    h, w = depth_map.shape
    fx, fy = intrinsics[0, 0], intrinsics[1, 1]
    cx, cy = intrinsics[0, 2], intrinsics[1, 2]
    
    if car_mask.shape != (h, w):
        car_mask = cv2.resize(car_mask, (w, h), interpolation=cv2.INTER_NEAREST)
        
    u, v = np.meshgrid(np.arange(w), np.arange(h))
    valid = (car_mask > 0) & (depth_map > 1e-3)

    u, v = u[valid], v[valid]
    depths = depth_map[valid]
    colors = rgb_image[valid].astype(np.float32) / 255.0

    if len(u) == 0:
        return None

    x = (u - cx) * depths / fx
    y = -(v - cy) * depths / fy  # Open3D koordinat sistemi düzeltmesi
    z = depths
    points_cam = np.stack([x, y, z], axis=-1)

    # Kamera koordinatlarından Dünya koordinatlarına geçiş
    R = extrinsics[:3, :3]
    t = extrinsics[:3, 3]
    points_world = (points_cam - t) @ np.linalg.inv(R).T

    # Kamera konumunu Dünya koordinatlarında hesapla (Normaller için kritik)
    camera_center_world = -np.linalg.inv(R) @ t

    # Open3D PointCloud objesi oluşturup local normal yönlendirmesi yapıyoruz
    pcd_frame = o3d.geometry.PointCloud()
    pcd_frame.points = o3d.utility.Vector3dVector(points_world)
    pcd_frame.colors = o3d.utility.Vector3dVector(colors)
    
    # Her kareyi kendi kamerasına bakacak şekilde yönlendiriyoruz (Ters mesh oluşumunu engeller)
    pcd_frame.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
    pcd_frame.orient_normals_towards_camera_location(camera_location=camera_center_world)

    return pcd_frame

def merge_point_clouds(prediction, mask_files, image_files):
    print("=== Nokta Bulutları Global Alanda Birleştiriliyor ===")
    merged_pcd = o3d.geometry.PointCloud()
    
    for i in range(len(prediction.depth)):
        mask_img = cv2.imread(mask_files[i], cv2.IMREAD_GRAYSCALE)
        if mask_img is None: continue
        car_mask = (mask_img > 127).astype(np.uint8)
        
        pcd_frame = depth_to_point_cloud(
            prediction.depth[i],
            prediction.processed_images[i],
            prediction.intrinsics[i],
            prediction.extrinsics[i],
            car_mask
        )
        if pcd_frame is not None:
            # KRİTİK: Kareyi eklemeden önce 1cm'lik voxellere bölerek nokta sayısını hafiflet
            pcd_frame = pcd_frame.voxel_down_sample(voxel_size=0.01)
            merged_pcd += pcd_frame
            
    print(f"-> Bellek Dostu Birleştirme Sonrası Nokta Sayısı: {len(merged_pcd.points)}")
    return merged_pcd

# ----------------------------
# 6. AGRESİF FİLTRELEME VE PÜRÜZSÜZ TAUBIN MESHİ
# ----------------------------
def clean_and_mesh(pcd):
    print("\n=== Nokta Bulutu Temizliği ve Kararlı BPA Yüzey Örme ===")
    
    # 1. Voxel Downsample (Zaten 104k noktadayız, burası kararlı)
    pcd = pcd.voxel_down_sample(voxel_size=0.018) 
    print(f"-> Nokta sayısı: {len(pcd.points)}")
    
    # 2. İnce Outlier Temizliği
    pcd, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=1.5)
    pcd = pcd.select_by_index(ind)
    
    # Normalleri hesapla ve dışa doğru zorla
    pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.15, max_nn=30))
    
    # 3. Ball Pivoting Algorithm (BPA) — Poisson gibi RAM'i patlatmaz!
    print("-> Kararlı yüzey örülüyor (Ball Pivoting Algorithm)...")
    
    # Noktalar arası ortalama mesafeyi hesaplayıp top yarıçaplarını dinamik belirliyoruz
    distances = pcd.compute_nearest_neighbor_distance()
    avg_dist = np.mean(distances)
    radii = [avg_dist, avg_dist * 2, avg_dist * 4, avg_dist * 8]
    
    # Mesh oluşturma
    mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
        pcd, o3d.utility.DoubleVector(radii)
    )
    
    # 4. Geometrik Temizlik ve Delik Kapatma
    print("-> Mesh geometrisi temizleniyor...")
    mesh.remove_degenerate_triangles()
    mesh.remove_duplicated_triangles()
    mesh.remove_duplicated_vertices()
    mesh.remove_non_manifold_edges()
    mesh = mesh.remove_unreferenced_vertices()

    # Uçuşan bağımsız küçük mesh parçalarını yok et
    triangle_clusters, cluster_n_triangles, _ = mesh.cluster_connected_triangles()
    if len(cluster_n_triangles) > 0:
        largest_cluster_idx = cluster_n_triangles.argmax()
        mesh.remove_triangles_by_mask(triangle_clusters != largest_cluster_idx)
        mesh = mesh.remove_unreferenced_vertices()

    # 5. Taubin Yumuşatması (Kaportayı pürüzsüzleştirir)
    print("-> Kaporta yüzeyine Taubin yumuşatması uygulanıyor...")
    mesh = mesh.filter_smooth_taubin(number_of_iterations=15, lambda_filter=0.5, mu=-0.53)
    mesh.compute_vertex_normals()
    
    return mesh

# ----------------------------
# MAIN EXECUTION PIPELINE
# ----------------------------
if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in locals() else os.getcwd()
    
    local_paths = {
        "video": os.path.join(base_dir, "toyota_360_video.mp4"),
        "data": os.path.join(base_dir, "data"),
        "masks": os.path.join(base_dir, "masks"),
        "results": os.path.join(base_dir, "results"),
        "sam_checkpoint": r"D:\MODIFIAI\3dservis\SAM\sam_vit_h_4b8939.pth"
    }

    os.makedirs(local_paths["data"], exist_ok=True)
    os.makedirs(local_paths["masks"], exist_ok=True)
    os.makedirs(local_paths["results"], exist_ok=True)

    # Step 1: Video Karelerini Çıkar
    if extract_keyframes_from_video(local_paths["video"], local_paths["data"], target_frame_count=24):
        image_files = sorted(glob.glob(os.path.join(local_paths["data"], "*.png")))
        
        # Step 2: SAM ile Maskeleri Üret
        print("\n=== SAM Modeli Yükleniyor ===")
        sam_predictor = load_sam_model(local_paths["sam_checkpoint"]) if 'load_sam_model' in globals() else sam_model_registry["vit_h"](checkpoint=local_paths["sam_checkpoint"]).to("cuda")
        sam_predictor = SamPredictor(sam_predictor) if not isinstance(sam_predictor, SamPredictor) else sam_predictor
        mask_files = generate_masks(image_files, local_paths["masks"], sam_predictor)
        
        # Step 3: COLMAP Adımını Maskeli Koştur (Kritik İyileştirme)
        if not run_colmap_for_extrinsics(local_paths["data"], local_paths["masks"], local_paths["results"]):
            print("❌ COLMAP adımında yeterli eşleşme bulunamadı. İşlem durduruldu.")
            sys.exit()

        # Step 4: Depth Anything V3 Inferences
        print("\n=== DA3METRIC-LARGE Yükleniyor ve İnference Koşuyor ===")
        model = DepthAnything3.from_pretrained("depth-anything/DA3METRIC-LARGE").to("cuda")
        prediction = model.inference(image=image_files, process_res=504, process_res_method="lower_bound_resize", infer_gs=False)

        # Step 5: COLMAP Matrislerini Ez (Override)
        sparse_out_dir = os.path.join(local_paths["results"], "sparse")
        colmap_ext, colmap_int = read_colmap_extrinsics_and_intrinsics(sparse_out_dir, image_files)
        prediction.extrinsics = colmap_ext
        prediction.intrinsics = colmap_int
        
        # Step 6: Birleştir ve Mesh Oluştur
        merged_pcd = merge_point_clouds(prediction, mask_files, image_files)
        
        if len(merged_pcd.points) > 0:
            o3d.io.write_point_cloud(os.path.join(local_paths["results"], "temiz_bulut.ply"), merged_pcd)
            
            final_mesh = clean_and_mesh(merged_pcd)
            mesh_out_path = os.path.join(local_paths["results"], "araba_modeli_final.glb")
            o3d.io.write_triangle_mesh(mesh_out_path, final_mesh)
            
            print(f"\n🎉 [BAŞARILI] MODIF-AI 3D Model Çıktısı Hazır: {mesh_out_path}")
            o3d.visualization.draw_geometries([final_mesh], window_name="MODIF-AI Final Mesh", mesh_show_back_face=True)