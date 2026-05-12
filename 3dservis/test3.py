import os
import numpy as np
import torch
import open3d as o3d
from depth_anything_3.api import DepthAnything3

# -------------------------------
# PATHS
# -------------------------------
image_dir = r"C:\Users\Turkuaz\Desktop\segmentasyon\images"
output_dir = r"C:\Users\Turkuaz\Desktop\segmentasyon\output"

os.makedirs(output_dir, exist_ok=True)

output_ply = os.path.join(output_dir, "scene.ply")
output_glb = os.path.join(output_dir, "scene.glb")

# -------------------------------
# LOAD IMAGES
# -------------------------------
image_paths = [
    os.path.join(image_dir, f)
    for f in os.listdir(image_dir)
    if f.lower().endswith((".jpg", ".png", ".jpeg"))
]

image_paths.sort()

print(f"{len(image_paths)} images found")

# -------------------------------
# LOAD MODEL
# -------------------------------
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

model = DepthAnything3.from_pretrained("depth-anything/da3-base")
model = model.to(device)
model.eval()

# -------------------------------
# POINT CLOUD
# -------------------------------
all_points = []
all_colors = []

fx = fy = 1200  # approximate focal

# -------------------------------
# PROCESS IMAGES
# -------------------------------
for i, img_path in enumerate(image_paths):
    print(f"Processing {i+1}/{len(image_paths)}")

    with torch.no_grad():
        pred = model.inference(
            image=[img_path],
            process_res=512  # daha yüksek kalite
        )

    depth = pred.depth[0]
    img = pred.processed_images[0]

    # normalize depth
    depth = (depth - depth.min()) / (depth.max() - depth.min())

    h, w = depth.shape
    cx, cy = w / 2, h / 2

    # 🔥 daha dense sampling (daha kaliteli)
    step = 2

    for y in range(0, h, step):
        for x in range(0, w, step):

            z = depth[y, x]
            if z <= 0:
                continue

            X = (x - cx) * z / fx
            Y = (y - cy) * z / fy
            Z = z

            all_points.append([X, Y, Z])
            all_colors.append(img[y, x][:3] / 255.0)

    torch.cuda.empty_cache()

# -------------------------------
# CREATE POINT CLOUD
# -------------------------------
pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(np.array(all_points))
pcd.colors = o3d.utility.Vector3dVector(np.array(all_colors))

# 🔥 noise temizleme
pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)

# 🔥 downsample (denge)
pcd = pcd.voxel_down_sample(voxel_size=0.005)

# -------------------------------
# SAVE PLY
# -------------------------------
o3d.io.write_point_cloud(output_ply, pcd)
print("PLY saved:", output_ply)

# -------------------------------
# NORMAL ESTIMATION
# -------------------------------
pcd.estimate_normals(
    search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.01, max_nn=30)
)

# -------------------------------
# MESH (KALİTELİ)
# -------------------------------
print("Creating mesh...")

mesh, _ = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
    pcd, depth=10
)

mesh.compute_vertex_normals()

# 🔥 mesh temizleme
mesh = mesh.simplify_quadric_decimation(100000)

# -------------------------------
# SAVE GLB
# -------------------------------
o3d.io.write_triangle_mesh(output_glb, mesh)
print("GLB saved:", output_glb)

print("DONE 🚀")