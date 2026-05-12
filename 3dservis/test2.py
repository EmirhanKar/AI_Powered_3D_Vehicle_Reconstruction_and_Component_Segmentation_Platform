import numpy as np

data = np.load(r"C:\Users\Turkuaz\Desktop\segmentasyon\output\gs_export\exports\mini_npz\results.npz")
print("Anahtarlar:", list(data.keys()))
for k in data.keys():
    print(f"  {k}: shape={data[k].shape}, dtype={data[k].dtype}")