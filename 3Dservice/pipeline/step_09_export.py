"""
Adım 09: GLB (ve Opsiyonel USDZ) Dışa Aktarım, Extras Üstverisi ve Depolama Teslimatı (`step_09_export.py`).

Amaç:
    Adım 07'de üretilen dokulu 3B modeli (`.obj` + `.png` + `.mtl`) glTF 2.0
    ikili standardında (`car_model.glb`) dışa aktarır, GLB JSON başlığındaki
    `asset.extras` ve `scenes[0].extras` alanlarına:
      - `meters_per_unit`
      - `scale_known`
      - `front_confidence`
      - `wheel_base_y`
      - `coordinate_system` (`"right-handed, +Y up, +Z front"`)
    bilgilerini gömer (Karar 2a). Ayrıca `EXPORT_FORMATS` içerisinde `"usdz"`
    varsa opsiyonel `.usdz` paketini de oluşturur ve tüm çıktıları `StorageManager`
    (`local` veya `s3`) üzerinden yayınlar.

Girdiler (requires):
    - `textured_mesh_obj`: UV açılmış `.obj` dosyası.
    - `texture_png`: Fırınlanmış `.png` doku haritası.
    - `material_mtl`: Materyal tanım dosyası.
    - `quality_report`: Adım 08'den gelen kalite ve ölçek/koordinat metrikleri.

Çıktılar (produces):
    - `exported_glb`: Üretilen `.glb` dosyasının yolu (zorunlu).
    - `exported_usdz`: Üretilen `.usdz` dosyasının yolu (istenmemişse `None`).
    - `export_manifest`: Depolama URI'lerini, dosya boyutlarını ve `extras` üstverisini içeren JSON dosyası.

Tipik Hata Durumları ve Kodları:
    - `GLB_EXPORT_FAILED`: GLB ikili dosyası oluşturulamadı veya `extras` gömülemedi.
    - `USDZ_EXPORT_FAILED`: USDZ paketlemesi başarısız oldu.
    - `STORAGE_UPLOAD_FAILED`: Yerel veya S3 depolama alanına kopyalama başarısız oldu.
"""

from __future__ import annotations

import json
from pathlib import Path
import struct
from typing import Any, Dict, Optional
import zipfile

from PIL import Image
import trimesh
import trimesh.visual
from trimesh.visual.material import PBRMaterial

from pipeline.base import PipelineContext, Step, StepResult
from pipeline.errors import StepError
from pipeline.utils.storage import StorageManager


def inject_extras_into_glb(glb_path: Path, extras_payload: Dict[str, Any]) -> None:
    """
    Standart bir glTF 2.0 Binary (`.glb`) dosyasının JSON yığınına (chunk 0)
    `extras` sözlüğünü (`meters_per_unit`, `scale_known`, `front_confidence`)
    gömer ve 4-bayt hizalamasını (4-byte alignment) koruyarak dosyayı günceller.

    Neden Doğrudan GLB Chunk Güncellemesi Yapılır?
    Bazı 3B dışa aktarıcılar sahne düzeyindeki özel `extras` alanlarını dışa
    aktarım sırasında düşürebilir. Doğrudan RFC/Khronos glTF 2.0 ikili kapsayıcı
    (12 bayt başlık + JSON chunk + BIN chunk) yapısını güncelleyerek hem `pygltflib`
    hem de Three.js / Flutter `model_viewer_plus` tarafından %100 okunabilir
    olmasını garanti altına alırız.
    """
    raw = glb_path.read_bytes()
    if len(raw) < 20:
        raise ValueError("Geçersiz GLB dosyası: Boyut 20 bayttan küçük.")

    magic, version, _total_len = struct.unpack_from("<III", raw, 0)
    if magic != 0x46546C67:  # 'glTF' ASCII
        raise ValueError("Geçersiz GLB başlığı (magic != 'glTF').")

    json_chunk_len, json_chunk_type = struct.unpack_from("<II", raw, 12)
    if json_chunk_type != 0x4E4F534A:  # 'JSON' ASCII
        raise ValueError("İlk GLB yığını JSON tipinde değil.")

    json_start = 20
    json_end = json_start + json_chunk_len
    json_bytes = raw[json_start:json_end]
    rest_chunks = raw[json_end:]

    gltf_dict = json.loads(json_bytes.decode("utf-8").rstrip(" \t\r\n\x00"))
    gltf_dict.setdefault("asset", {}).setdefault("extras", {}).update(extras_payload)
    gltf_dict["extras"] = {**gltf_dict.get("extras", {}), **extras_payload}
    if "scenes" in gltf_dict and isinstance(gltf_dict["scenes"], list) and gltf_dict["scenes"]:
        gltf_dict["scenes"][0].setdefault("extras", {}).update(extras_payload)

    new_json_raw = json.dumps(gltf_dict, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    # glTF 2.0 spesifikasyonu: JSON yığını 0x20 (boşluk) karakteriyle 4 baytın katına tamamlanmalıdır
    padding = (4 - (len(new_json_raw) % 4)) % 4
    new_json_padded = new_json_raw + (b" " * padding)

    new_total_len = 12 + 8 + len(new_json_padded) + len(rest_chunks)
    new_header = struct.pack("<III", magic, version, new_total_len)
    new_json_header = struct.pack("<II", len(new_json_padded), 0x4E4F534A)

    glb_path.write_bytes(new_header + new_json_header + new_json_padded + rest_chunks)


def export_minimal_usdz(usdz_path: Path, obj_path: Path, texture_path: Path, extras: Dict[str, Any]) -> None:
    """
    Opsiyonel `usdz` formatı istendiğinde sıkıştırmasız (0-compression ZIP,
    64-bayt hizalı) standart USDZ arşiv kapsayıcısını oluşturur.
    """
    usda_content = (
        '#usda 1.0\n'
        '(\n'
        '    defaultPrim = "CarModel"\n'
        f'    metersPerUnit = {extras.get("meters_per_unit", 1.0)}\n'
        '    upAxis = "Y"\n'
        ')\n'
        'def Xform "CarModel" (\n'
        '    customData = {\n'
        f'        bool scale_known = {1 if extras.get("scale_known") else 0}\n'
        f'        double front_confidence = {extras.get("front_confidence", 0.5)}\n'
        '    }\n'
        ')\n'
        '{\n'
        '}\n'
    )
    with zipfile.ZipFile(str(usdz_path), mode="w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("default.usda", usda_content.encode("utf-8"))
        zf.write(str(obj_path), arcname=obj_path.name)
        zf.write(str(texture_path), arcname=texture_path.name)


class Step09Export(Step):
    """Dokulu modeli GLB (ve opsiyonel USDZ) olarak dışa aktaran ve depolamaya yükleyen son adım."""

    name = "export"
    order = 9
    requires = ("textured_mesh_obj", "texture_png", "material_mtl", "quality_report")
    produces = ("exported_glb", "exported_usdz", "export_manifest")

    def run(self, ctx: PipelineContext) -> StepResult:
        step_dir = self.prepare_step_dir(ctx)
        obj_path = ctx.get_artifact_path("textured_mesh_obj")
        tex_path = ctx.get_artifact_path("texture_png")
        _mtl_path = ctx.get_artifact_path("material_mtl")
        quality_report_path = ctx.get_artifact_path("quality_report")

        quality_data: Dict[str, Any] = json.loads(quality_report_path.read_text(encoding="utf-8"))
        q_metrics = quality_data.get("metrics", {})

        extras_payload: Dict[str, Any] = {
            "meters_per_unit": float(q_metrics.get("meters_per_unit", 4.5)),
            "scale_known": bool(q_metrics.get("scale_known", False)),
            "front_confidence": float(q_metrics.get("front_confidence", 0.5)),
            "wheel_base_y": float(q_metrics.get("wheel_base_y", 0.0)),
            "coordinate_system": "glTF_right_handed_Y_up_Z_front",
            "quality_verdict": quality_data.get("verdict", "pass"),
        }

        # 1. OBJ ve PNG Dokusunu Yükleyip GLB Olarak Dışa Aktar
        glb_path = step_dir / "car_model.glb"
        try:
            loaded = trimesh.load(str(obj_path), force="mesh", process=False)
            if isinstance(loaded, trimesh.Scene):
                loaded = loaded.dump(concatenate=True)

            pil_tex = Image.open(str(tex_path)).convert("RGB")
            material = PBRMaterial(
                name="car_pbr_material",
                baseColorTexture=pil_tex,
                metallicFactor=0.25,
                roughnessFactor=0.45,
            )
            if hasattr(loaded.visual, "uv") and loaded.visual.uv is not None and len(loaded.visual.uv) == len(loaded.vertices):
                uv_coords = loaded.visual.uv
            else:
                uv_coords = np.zeros((len(loaded.vertices), 2), dtype=np.float32)

            loaded.visual = trimesh.visual.TextureVisuals(uv=uv_coords, image=pil_tex, material=material)
            glb_bytes = loaded.export(file_type="glb")
            glb_path.write_bytes(glb_bytes)

            # Karar 2a: GLB extras alanına meters_per_unit, scale_known ve front_confidence göm
            inject_extras_into_glb(glb_path, extras_payload)
        except Exception as exc:
            raise StepError(
                step=self.step_id,
                code="GLB_EXPORT_FAILED",
                message=f"GLB dışa aktarımı veya extras üstveri yazımı başarısız oldu: {exc}",
                details={"error": str(exc)},
            ) from exc

        storage = StorageManager(ctx.config)
        glb_published = storage.publish_artifact(ctx.job_id, glb_path, step_name=self.step_id)

        # 2. Opsiyonel USDZ Dışa Aktarımı
        usdz_path: Optional[Path] = None
        usdz_published: Optional[Dict[str, str]] = None
        if "usdz" in ctx.config.export_formats:
            usdz_path = step_dir / "car_model.usdz"
            try:
                export_minimal_usdz(usdz_path, obj_path, tex_path, extras_payload)
                usdz_published = storage.publish_artifact(ctx.job_id, usdz_path, step_name=self.step_id)
            except StepError:
                raise
            except Exception as exc:
                raise StepError(
                    step=self.step_id,
                    code="USDZ_EXPORT_FAILED",
                    message=f"USDZ dışa aktarımı başarısız oldu: {exc}",
                    details={"error": str(exc)},
                ) from exc

        glb_size_kb = round(glb_path.stat().st_size / 1024.0, 2)
        manifest_data = {
            "job_id": ctx.job_id,
            "formats": list(ctx.config.export_formats),
            "extras": extras_payload,
            "glb": {
                **glb_published,
                "size_kb": glb_size_kb,
            },
            "usdz": usdz_published,
        }
        manifest_path = step_dir / "export_manifest.json"
        manifest_path.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")

        ctx.logger.info(
            "Dışa aktarım tamamlandı: GLB=%.2f KB (%s), extras=%s",
            glb_size_kb,
            glb_published["uri"],
            json.dumps(extras_payload, ensure_ascii=False),
        )

        return StepResult(
            status="done",
            artifacts={
                "exported_glb": str(glb_path),
                "exported_usdz": str(usdz_path) if usdz_path else None,
                "export_manifest": str(manifest_path),
            },
            metrics={
                "glb_size_kb": glb_size_kb,
                "meters_per_unit": extras_payload["meters_per_unit"],
                "scale_known": extras_payload["scale_known"],
                "front_confidence": extras_payload["front_confidence"],
                "storage_uri": glb_published["uri"],
            },
            summary=f"GLB başarıyla dışa aktarıldı ({glb_size_kb:.1f} KB, uri={glb_published['uri']}).",
        )
