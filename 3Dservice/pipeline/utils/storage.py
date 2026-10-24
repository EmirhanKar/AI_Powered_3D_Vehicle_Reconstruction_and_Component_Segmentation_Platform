"""
ModifAI 3D Servisi — Depolama Soyutlama Katmanı (Yerel Disk ve S3).

Mevcut Backend yerel disk depolaması (`uploads/images_3d/...`) kullanmaktadır.
Bu modül, `STORAGE_BACKEND` ayarına göre nihai GLB/USDZ dosyalarını ya yerel
`outputs/<job_id>/` dizinine kopyalar ya da AWS S3 / MinIO uyumlu bir kovaya
(bucket) yükler ve erişim referanslarını döndürür.
"""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Dict

from config import ServiceConfig
from pipeline.errors import StepError


class StorageManager:
    """Nihai 3B model çıktılarını yapılandırılan depolama ortamına kaydeden yönetici sınıf."""

    def __init__(self, config: ServiceConfig) -> None:
        self.config = config

    def publish_artifact(self, job_id: str, local_file: Path, step_name: str = "step_09_export") -> Dict[str, str]:
        """
        Üretilen bir çıktı dosyasını (ör. `car_model.glb`) hedef depolama alanına
        aktarır ve `{"storage_backend": ..., "uri": ..., "local_path": ...}` döndürür.
        """
        if not local_file.exists():
            raise StepError(
                step=step_name,
                code="EXPORT_FILE_MISSING",
                message=f"Dışa aktarılacak dosya bulunamadı: {local_file}",
            )

        if self.config.storage_backend == "local":
            dest_dir = self.config.outputs_dir / job_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / local_file.name
            shutil.copy2(local_file, dest_path)
            return {
                "storage_backend": "local",
                "uri": f"/outputs/{job_id}/{local_file.name}",
                "local_path": str(dest_path.resolve()),
            }

        if self.config.storage_backend == "s3":
            try:
                import boto3  # type: ignore

                s3_kwargs = {"region_name": self.config.s3_region}
                if self.config.s3_endpoint_url:
                    s3_kwargs["endpoint_url"] = self.config.s3_endpoint_url
                s3_client = boto3.client("s3", **s3_kwargs)
                object_key = f"jobs/{job_id}/{local_file.name}"
                s3_client.upload_file(str(local_file), self.config.s3_bucket_name, object_key)
                uri = f"s3://{self.config.s3_bucket_name}/{object_key}"
                return {
                    "storage_backend": "s3",
                    "uri": uri,
                    "local_path": str(local_file.resolve()),
                }
            except Exception as exc:
                raise StepError(
                    step=step_name,
                    code="STORAGE_UPLOAD_FAILED",
                    message=f"S3 depolama alanına yükleme başarısız oldu: {exc}",
                    hint="S3 kimlik bilgilerini ve S3_BUCKET_NAME ayarını kontrol edin.",
                    details={"bucket": self.config.s3_bucket_name, "error": str(exc)},
                ) from exc

        raise StepError(
            step=step_name,
            code="INVALID_STORAGE_BACKEND",
            message=f"Desteklenmeyen depolama tipi: {self.config.storage_backend}",
        )
