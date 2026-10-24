"""
ModifAI 3D Servisi — İş ve Adım Bağlamlı Günlükleme (Logging) Yardımcıları.

Her iş (job) için `jobs/<job_id>/logs/step_NN.log` dosyasına ayrı bir günlük
tutulur. Gece 02:00'de hata ayıklarken hangi satırın hangi işe ve hangi adıma
ait olduğunun tek bakışta anlaşılması için her log satırı zorunlu olarak
`[job_id=...][step=...]` önekini taşır.
"""

from __future__ import annotations

import logging
from pathlib import Path
import sys
from typing import Optional


class JobStepContextFilter(logging.Filter):
    """Her log kaydına `job_id` ve `step_name` alanlarını enjekte eden filtre."""

    def __init__(self, job_id: str, step_name: str) -> None:
        super().__init__()
        self.job_id = job_id
        self.step_name = step_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.job_id = self.job_id
        record.step_name = self.step_name
        return True


def setup_step_logger(
    job_id: str,
    step_order: int,
    step_name: str,
    job_dir: Path,
    log_level: str = "INFO",
) -> logging.Logger:
    """
    Belirli bir iş ve adım için hem konsola hem de `jobs/<job_id>/logs/step_NN.log`
    dosyasına yazan izole bir `Logger` oluşturur.
    """
    logs_dir = job_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"step_{step_order:02d}.log"

    logger_name = f"3dservice.{job_id}.step_{step_order:02d}_{step_name}"
    logger = logging.getLogger(logger_name)
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    # Önceki çalıştırmalardan kalan dosya tanıtıcılarını (file handlers) kapat ve temizle.
    # Windows üzerinde açık kalan dosya tanıtıcıları klasör silinmesini engelleyebilir.
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [job=%(job_id)s] [step=step_%(step_name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ctx_filter = JobStepContextFilter(job_id=job_id, step_name=f"{step_order:02d}_{step_name}")

    # 1. Dosya işleyicisi (step_NN.log) — yeniden çalıştırmada üzerine yazar (mode='w')
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(ctx_filter)
    logger.addHandler(file_handler)

    # 2. Konsol işleyicisi (stdout)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(ctx_filter)
    logger.addHandler(stream_handler)

    return logger


def close_logger_handlers(logger: Optional[logging.Logger]) -> None:
    """Açık dosya tanıtıcılarını güvenli bir şekilde kapatır."""
    if logger is None:
        return
    for handler in list(logger.handlers):
        try:
            handler.flush()
            handler.close()
        except Exception as exc:
            # Log kapatma hataları ana akışı bozmamalıdır
            _ = exc
        logger.removeHandler(handler)
