import os
import open3d as o3d
import numpy as np
from PIL import Image
import subprocess

# --- AYARLAR ---
colmap_path = r"C:\Users\Turkuaz\Desktop\segmentasyon\colmap\bin\colmap.exe"
image_folder = r"C:\Users\Turkuaz\Desktop\segmentasyon\images"
database_path = "database.db"
sparse_folder = "sparse"
dense_folder = "dense"
max_width = 1600  # mutlaka çift sayı

# --- Eski database varsa sil ---
if os.path.exists(database_path):
    os.remove(database_path)
    print("🗑️ Eski database silindi.")

# --- Fotoğrafları resize ve numaralandır ---
print("📷 Fotoğraflar resize ediliyor...")
image_files = sorted([f for f in os.listdir(image_folder) if f.lower().endswith((".jpg", ".jpeg", ".png"))])
for idx, f in enumerate(image_files, start=1):
    old_path = os.path.join(image_folder, f)
    img = Image.open(old_path)
    w_percent = max_width / float(img.size[0])
    h_size = int(img.size[1] * w_percent)
    h_size = h_size // 2 * 2  # çift sayı
    img = img.resize((max_width, h_size))
    new_name = f"{idx:02d}.jpeg"
    new_path = os.path.join(image_folder, new_name)
    img.save(new_path)
    img.close()
    if old_path != new_path:
        os.remove(old_path)
print("✅ Fotoğraflar hazır!")

# --- COLMAP helper ---
def run_colmap(cmd_list):
    print("💻 Running:", " ".join(cmd_list))
    subprocess.run(cmd_list, check=True)

# --- Sparse reconstruction ---
print("1️⃣ Feature extraction & matching")
run_colmap([colmap_path, "feature_extractor", "--database_path", database_path, "--image_path", image_folder])
run_colmap([colmap_path, "exhaustive_matcher", "--database_path", database_path])

print("2️⃣ Sparse reconstruction")
os.makedirs(sparse_folder, exist_ok=True)
run_colmap([colmap_path, "mapper", "--database_path", database_path, "--image_path", image_folder, "--output_path", sparse_folder])
sparse_subfolders = [f for f in os.listdir(sparse_folder) if os.path.isdir(os.path.join(sparse_folder, f))]
sparse_input = os.path.join(sparse_folder, sparse_subfolders[0])

# --- Dense reconstruction ---
print("3️⃣ Dense reconstruction")
os.makedirs(dense_folder, exist_ok=True)
run_colmap([colmap_path, "image_undistorter",
            "--image_path", image_folder,
            "--input_path", sparse_input,
            "--output_path", dense_folder,
            "--output_type", "COLMAP",
            "--max_image_size", str(max_width)])

# PatchMatch Stereo (Windows stabil parametreleri)
run_colmap([colmap_path, "patch_match_stereo",
            "--workspace_path", dense_folder,
            "--PatchMatchStereo.geom_consistency", "true",
            "--PatchMatchStereo.num_iterations", "3",
            "--PatchMatchStereo.window_radius", "3",
            "--PatchMatchStereo.num_threads", "0"])  # tüm thread’ler

# Stereo fusion
fused_ply = os.path.join(dense_folder, "fused.ply")
run_colmap([colmap_path, "stereo_fusion",
            "--workspace_path", dense_folder,
            "--output_path", fused_ply,
            "--StereoFusion.min_num_pixels", "1",
            "--StereoFusion.max_reproj_error", "5",
            "--StereoFusion.max_depth_error", "0.05"])

# --- Open3D Mesh ---
print("4️⃣ Mesh oluşturma")
pcd = o3d.io.read_point_cloud(fused_ply)
pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=10)
mesh.remove_vertices_by_mask(densities < np.quantile(densities, 0.01))
o3d.io.write_triangle_mesh("car_mesh.obj", mesh)
o3d.visualization.draw_geometries([mesh])
print("✅ Pipeline tamamlandı! Mesh 'car_mesh.obj' olarak kaydedildi.")