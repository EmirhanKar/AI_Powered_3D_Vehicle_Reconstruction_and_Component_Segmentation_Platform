import cv2, glob, numpy as np

image_files = sorted(glob.glob(r"C:\Users\Turkuaz\Desktop\segmentasyon\images\*"))

orb = cv2.ORB_create(2000)
bf  = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

for i in range(len(image_files)-1):
    img1 = cv2.imread(image_files[i],   cv2.IMREAD_GRAYSCALE)
    img2 = cv2.imread(image_files[i+1], cv2.IMREAD_GRAYSCALE)
    k1, d1 = orb.detectAndCompute(img1, None)
    k2, d2 = orb.detectAndCompute(img2, None)
    matches = bf.match(d1, d2)
    good = [m for m in matches if m.distance < 50]
    print(f"Foto {i+1}↔{i+2}: {len(good)} iyi eşleşme")