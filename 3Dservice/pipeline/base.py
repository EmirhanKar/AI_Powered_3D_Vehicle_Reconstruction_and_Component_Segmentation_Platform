"""
ModifAI 3D Servisi — Adım Sözleşmesi (Step Contract) ve Bağlam (Context) Sınıfları.

Bu modül, her adımın uymak zorunda olduğu sözleşmeyi (`Step`), adım çıktısını
(`StepResult`) ve adımlar arası veri taşıyan `PipelineContext` yapısını tanımlar.

Mimari Kurallar:
1. Bir adım yalnızca `requires` listesinde beyan ettiği artefaktları okuyabilir.
2. Bir adım yalnızca kendi klasörüne (`jobs/<job_id>/<NN_stepname>/`) dosya yazabilir.
3. Orkestratör, adım çalışmadan önce `requires` anahtarlarının mevcut olduğunu ve
   adım bittikten sonra `produces` anahtarlarının eksiksiz üretildiğini doğrular.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import logging
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Tuple

from config import ServiceConfig
from pipeline.errors import StepError


@dataclass
class StepResult:
    """
    Bir pipeline adımının çalışması tamamlandığında döndürdüğü sonuç nesnesi.

    Alanlar:
        status: Adım durumu ('done' veya 'skipped'). Başarısızlık durumunda `StepError` fırlatılır.
        artifacts: Bu adımın ürettiği (`produces` ile eşleşen) artefakt anahtarları ve dosya/veri yolları.
        metrics: Süreçte ölçülen sayısal/metinsel metrikler (ör. PSNR, kayıt oranı, yüz sayısı).
        summary: Günlük (log) ve durum dosyası için kısa Türkçe özet mesaj.
    """

    status: str = "done"
    artifacts: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""


@dataclass
class PipelineContext:
    """
    Tek bir işin (job) çalışma zamanı bağlamını temsil eder.

    Adımlar doğrudan birbirlerinin iç değişkenlerine erişmez; yalnızca bu bağlam
    üzerinden izin verilen artefaktları (`get_artifact`) okur ve kendi çalışma
    dizinlerini (`step_dir`) alırlar.
    """

    job_id: str
    job_dir: Path
    config: ServiceConfig
    artifacts: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    current_step_name: str = ""
    current_allowed_requires: Tuple[str, ...] = ()
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("3dservice"))

    def get_step_dir(self, order: int, name: str) -> Path:
        """
        Adıma özel izole klasör yolunu (`jobs/<job_id>/<NN_name>/`) döndürür.
        Klasör adı başında 2 haneli sıra numarası taşıdığı için dosya gezgininde
        kronolojik sırayla listelenir.
        """
        folder_name = f"{order:02d}_{name}"
        return self.job_dir / folder_name

    def get_artifact(self, key: str) -> Any:
        """
        Önceki adımların ürettiği bir artefaktı döndürür.
        Gizli bağımlılıkları (hidden coupling) önlemek için, eğer adım kendi
        `requires` listesinde bildirmemişse erişimi reddeder.
        """
        if self.current_allowed_requires and key not in self.current_allowed_requires:
            raise StepError(
                step=self.current_step_name or "unknown_step",
                code="UNDECLARED_ARTIFACT_ACCESS",
                message=(
                    f"'{self.current_step_name}' adımı, 'requires' listesinde beyan etmediği "
                    f"'{key}' artefaktına erişmeye çalıştı."
                ),
                hint="Sistem hatası: Adım sözleşmesi ihlal edildi.",
                details={"requested_key": key, "declared_requires": list(self.current_allowed_requires)},
            )

        if key not in self.artifacts:
            raise StepError(
                step=self.current_step_name or "unknown_step",
                code="MISSING_REQUIRED_ARTIFACT",
                message=f"Gerekli '{key}' artefaktı iş bağlamında (context) bulunamadı.",
                hint="Önceki adımların başarıyla tamamlandığından emin olun.",
                details={"missing_key": key, "available_keys": sorted(self.artifacts.keys())},
            )
        return self.artifacts[key]

    def get_artifact_path(self, key: str) -> Path:
        """Artefakt değerini `pathlib.Path` nesnesi olarak döndürür."""
        val = self.get_artifact(key)
        return Path(val)


class Step(ABC):
    """
    Tüm pipeline adımlarının (00..09) miras aldığı soyut taban sınıf.

    Alt sınıflar `name`, `order`, `requires`, `produces` sınıf özelliklerini
    ve `run(ctx, step_dir)` metodunu tanımlamak zorundadır.
    """

    name: str = ""
    order: int = -1
    requires: Tuple[str, ...] = ()
    produces: Tuple[str, ...] = ()

    @property
    def step_id(self) -> str:
        """Örnek: `step_04_estimate_poses`."""
        return f"step_{self.order:02d}_{self.name}"

    @property
    def folder_name(self) -> str:
        """Örnek: `04_estimate_poses`."""
        return f"{self.order:02d}_{self.name}"

    def prepare_step_dir(self, ctx: PipelineContext) -> Path:
        """
        İdempotent çalışma garantisi: Bir adım yeniden çalıştırıldığında (re-run),
        yalnızca kendi klasörünü (`jobs/<job_id>/<NN_stepname>/`) tamamen siler ve
        sıfırdan oluşturur. Diğer adımların klasörlerine dokunmaz.
        """
        step_dir = ctx.get_step_dir(self.order, self.name)
        if step_dir.exists():
            shutil.rmtree(step_dir)
        step_dir.mkdir(parents=True, exist_ok=True)
        return step_dir

    @abstractmethod
    def run(self, ctx: PipelineContext) -> StepResult:
        """
        Adımın asıl iş mantığını çalıştırır.
        Başarısızlık durumunda `StepError` fırlatmalıdır.
        """
        raise NotImplementedError
