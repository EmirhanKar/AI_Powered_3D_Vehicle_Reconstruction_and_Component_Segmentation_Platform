"""
meshy_service.py
────────────────
Meshy AI API entegrasyon servisi.

Desteklenen özellikler:
  • Image-to-3D  (tek/çoklu görsel → 3D model)
  • Text-to-3D   (metin prompt → 3D model)
  • AI Texturing  (mevcut modele yeni texture)
  • Smart Remesh  (mesh topoloji optimizasyonu)
  • Task durumu takibi (polling + SSE streaming)
  • Kredi/bakiye sorgulama
  • Model dosyası indirme

Kullanım:
    from app.services.meshy_service import MeshyService

    meshy = MeshyService()  # .env'den API key alır
    task_id = await meshy.image_to_3d(image_url="https://...")
    result  = await meshy.wait_for_task(task_id)
"""

import os
import asyncio
import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("meshy_service")


# ─── SABITLER ──────────────────────────────────────────────────────────────────

MESHY_BASE_URL = os.getenv("MESHY_BASE_URL", "https://api.meshy.ai")
MESHY_API_KEY = os.getenv("MESHY_API_KEY", "")
MESHY_TEST_API_KEY = "msy_dummy_api_key_for_test_mode_12345678"

# Varsayılan olarak test modunda çalış (geliştirme sırasında kredi harcamaz)
MESHY_MODE = os.getenv("MESHY_MODE", "test")  # "live" | "test"


class TaskStatus(str, Enum):
    """Meshy API task durumları."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class MeshyModel(str, Enum):
    """Meshy AI uretim modelleri."""
    MESHY_6 = "meshy-6"         # En yuksek kalite, 20 kredi (ONERILEN)
    MESHY_4 = "meshy-4"         # Deprecated — meshy-6 kullanin
    DEFAULT = "meshy-6"


class OutputFormat(str, Enum):
    """Desteklenen 3D çıktı formatları."""
    GLB = "glb"
    FBX = "fbx"
    OBJ = "obj"
    USDZ = "usdz"
    STL = "stl"
    BLEND = "blend"


@dataclass
class MeshyTaskResult:
    """Meshy API task sonucu."""
    task_id: str
    status: TaskStatus
    progress: int = 0
    model_urls: Dict[str, str] = field(default_factory=dict)
    thumbnail_url: Optional[str] = None
    texture_urls: List[Dict[str, str]] = field(default_factory=list)
    video_url: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    finished_at: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class MeshyAPIError(Exception):
    """Meshy API hata sınıfı."""
    def __init__(self, status_code: int, message: str, details: Any = None):
        self.status_code = status_code
        self.message = message
        self.details = details
        super().__init__(f"Meshy API Hatası [{status_code}]: {message}")


class MeshyService:
    """
    Meshy AI API istemcisi.

    Tüm API çağrıları async/await ile yapılır.
    httpx.AsyncClient her çağrıda oluşturulup kapatılır (bağlantı havuzu yok)
    veya `async with MeshyService() as meshy:` şeklinde context manager olarak kullanılabilir.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self._api_key = api_key or (MESHY_TEST_API_KEY if MESHY_MODE == "test" else MESHY_API_KEY)
        self._base_url = base_url or MESHY_BASE_URL
        self._client: Optional[httpx.AsyncClient] = None

        if not self._api_key:
            log.warning(
                "⚠️  MESHY_API_KEY tanımlanmamış! "
                "Test modunda çalışmak için .env'ye MESHY_MODE=test ekleyin "
                "veya MESHY_API_KEY=msy_... tanımlayın."
            )

    # ── Context Manager ────────────────────────────────────────────────────

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers(),
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()
            self._client = None

    # ── Dahili Yardımcılar ─────────────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Context manager dışında kullanılırsa geçici client oluşturur."""
        if self._client:
            return self._client
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers(),
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict] = None,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Genel HTTP istek metodu. Hata yönetimi ve retry mantığı dahildir.
        """
        client = await self._get_client()
        owns_client = client != self._client

        try:
            headers = None
            # Dosya yükleme için Content-Type'ı kaldır (multipart otomatik ayarlanır)
            if files:
                headers = {
                    "Authorization": f"Bearer {self._api_key}",
                }

            response = await client.request(
                method=method,
                url=endpoint,
                json=json,
                data=data,
                files=files,
                params=params,
                headers=headers,
            )

            if response.status_code == 429:
                # Rate limit — biraz bekle ve tekrar dene
                retry_after = int(response.headers.get("Retry-After", "5"))
                log.warning(f"⏳ Rate limit aşıldı. {retry_after}sn beklenecek...")
                await asyncio.sleep(retry_after)
                response = await client.request(
                    method=method,
                    url=endpoint,
                    json=json,
                    data=data,
                    files=files,
                    params=params,
                    headers=headers,
                )

            if response.status_code >= 400:
                error_body = response.text
                try:
                    error_json = response.json()
                    error_body = error_json.get("message", error_body)
                except Exception:
                    pass
                raise MeshyAPIError(response.status_code, error_body)

            # 204 No Content gibi durumlar
            if response.status_code == 204:
                return {}

            return response.json()

        finally:
            if owns_client:
                await client.aclose()

    def _parse_task_result(self, data: Dict[str, Any]) -> MeshyTaskResult:
        """API yanıtını MeshyTaskResult objesine dönüştürür."""
        return MeshyTaskResult(
            task_id=data.get("id", ""),
            status=TaskStatus(data.get("status", "PENDING")),
            progress=data.get("progress", 0),
            model_urls=data.get("model_urls", {}),
            thumbnail_url=data.get("thumbnail_url"),
            texture_urls=data.get("texture_urls", []),
            video_url=data.get("video_url"),
            error=data.get("task_error", {}).get("message") if isinstance(data.get("task_error"), dict) else data.get("task_error"),
            created_at=data.get("created_at"),
            finished_at=data.get("finished_at"),
            raw=data,
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  IMAGE-TO-3D
    # ═══════════════════════════════════════════════════════════════════════

    async def image_to_3d(
        self,
        image_url: str,
        mode: str = "preview",
        model: MeshyModel = MeshyModel.MESHY_6,
        topology: str = "quad",
        target_polycount: int = 30000,
        should_remesh: bool = True,
        output_format: OutputFormat = OutputFormat.GLB,
    ) -> str:
        """
        Tek bir görselden 3D model üretir.

        Args:
            image_url: Görsel URL'i (public erişilebilir olmalı)
            mode: Üretim modu ("preview" hızlı önizleme, "refine" yüksek kalite)
            model: Kullanılacak model (meshy-4 veya meshy-6)
            topology: Mesh topolojisi ("quad" veya "triangle")
            target_polycount: Hedef polygon sayısı
            should_remesh: Otomatik remesh uygulansın mı
            output_format: Çıktı formatı (glb, fbx, obj, usdz, stl)

        Returns:
            task_id: Oluşturulan görevin ID'si
        """
        payload = {
            "image_url": image_url,
            "mode": mode,
            "ai_model": model.value,
            "topology": topology,
            "target_polycount": target_polycount,
            "should_remesh": should_remesh,
        }

        log.info(f"Image-to-3D baslatiliyor -> model={model.value}, mode={mode}")
        result = await self._request("POST", "/openapi/v2/image-to-3d", json=payload)

        task_id = result.get("result", result.get("id", ""))
        log.info(f"Task olusturuldu: {task_id}")
        return task_id

    async def multi_image_to_3d(
        self,
        image_urls: List[str],
        model: MeshyModel = MeshyModel.MESHY_6,
        topology: str = "quad",
        target_polycount: int = 30000,
        output_format: OutputFormat = OutputFormat.GLB,
    ) -> str:
        """
        Birden fazla görüntüden 3D model üretir (daha iyi yapısal doğruluk).

        Args:
            image_urls: Görsel URL listesi (2-8 adet, public erişilebilir)
            model: Kullanılacak model
            topology: Mesh topolojisi
            target_polycount: Hedef polygon sayısı
            output_format: Çıktı formatı

        Returns:
            task_id: Oluşturulan görevin ID'si
        """
        payload = {
            "image_urls": image_urls,
            "ai_model": model.value,
            "topology": topology,
            "target_polycount": target_polycount,
        }

        log.info(f"🖼️  Multi-Image-to-3D başlatılıyor → {len(image_urls)} görsel, model={model.value}")
        result = await self._request("POST", "/openapi/v2/multi-image-to-3d", json=payload)

        task_id = result.get("result", result.get("id", ""))
        log.info(f"✅ Task oluşturuldu: {task_id}")
        return task_id

    # ═══════════════════════════════════════════════════════════════════════
    #  TEXT-TO-3D
    # ═══════════════════════════════════════════════════════════════════════

    async def text_to_3d(
        self,
        prompt: str,
        mode: str = "preview",
        model: MeshyModel = MeshyModel.MESHY_6,
        art_style: str = "realistic",
        negative_prompt: str = "",
        topology: str = "quad",
        target_polycount: int = 30000,
    ) -> str:
        """
        Metin açıklamasından 3D model üretir.

        Args:
            prompt: 3D model açıklaması (İngilizce önerilir)
            mode: Üretim modu ("preview" hızlı önizleme, "refine" yüksek kalite)
            model: Kullanılacak model
            art_style: Sanat stili ("realistic", "cartoon", "low-poly", "sculpture")
            negative_prompt: Olmasını istemediğiniz özellikler
            topology: Mesh topolojisi
            target_polycount: Hedef polygon sayısı

        Returns:
            task_id: Oluşturulan görevin ID'si
        """
        payload = {
            "mode": mode,
            "prompt": prompt,
            "ai_model": model.value,
            "art_style": art_style,
            "negative_prompt": negative_prompt,
            "topology": topology,
            "target_polycount": target_polycount,
        }

        log.info(f"Text-to-3D baslatiliyor -> '{prompt[:50]}...' model={model.value}")
        result = await self._request("POST", "/openapi/v2/text-to-3d", json=payload)

        task_id = result.get("result", result.get("id", ""))
        log.info(f"Task olusturuldu: {task_id}")
        return task_id

    # ═══════════════════════════════════════════════════════════════════════
    #  AI TEXTURING
    # ═══════════════════════════════════════════════════════════════════════

    async def texture_3d(
        self,
        model_url: str,
        prompt: str = "",
        art_style: str = "realistic",
        negative_prompt: str = "",
        resolution: str = "2048",
    ) -> str:
        """
        Mevcut bir 3D modele AI ile yeni texture/materyal uygular.

        Args:
            model_url: 3D model dosyasının URL'i (GLB/FBX/OBJ)
            prompt: Texture açıklaması ("metallic red car paint", "carbon fiber")
            art_style: Sanat stili
            negative_prompt: İstenmeyen özellikler
            resolution: Texture çözünürlüğü ("1024", "2048", "4096")

        Returns:
            task_id: Oluşturulan görevin ID'si
        """
        payload = {
            "model_url": model_url,
            "prompt": prompt,
            "art_style": art_style,
            "negative_prompt": negative_prompt,
            "resolution": resolution,
        }

        log.info(f"🎨 AI Texturing başlatılıyor → \"{prompt[:50]}\"")
        result = await self._request("POST", "/openapi/v1/text-to-texture", json=payload)

        task_id = result.get("result", result.get("id", ""))
        log.info(f"✅ Texture task oluşturuldu: {task_id}")
        return task_id

    # ═══════════════════════════════════════════════════════════════════════
    #  REMESH
    # ═══════════════════════════════════════════════════════════════════════

    async def remesh(
        self,
        model_url: str,
        target_polycount: int = 10000,
        topology: str = "quad",
    ) -> str:
        """
        3D modelin mesh topolojisini optimize eder.

        Args:
            model_url: 3D model dosyasının URL'i
            target_polycount: Hedef polygon sayısı
            topology: Mesh topolojisi ("quad" veya "triangle")

        Returns:
            task_id: Oluşturulan görevin ID'si
        """
        payload = {
            "model_url": model_url,
            "target_polycount": target_polycount,
            "topology": topology,
        }

        log.info(f"🔧 Remesh başlatılıyor → polycount={target_polycount}")
        result = await self._request("POST", "/openapi/v1/remesh", json=payload)

        task_id = result.get("result", result.get("id", ""))
        log.info(f"✅ Remesh task oluşturuldu: {task_id}")
        return task_id

    # ═══════════════════════════════════════════════════════════════════════
    #  TASK YÖNETİMİ
    # ═══════════════════════════════════════════════════════════════════════

    async def get_task_status(self, task_id: str, task_type: str = "image-to-3d") -> MeshyTaskResult:
        """
        Bir görevin mevcut durumunu sorgular.

        Args:
            task_id: Görev ID'si
            task_type: Görev türü ("image-to-3d", "text-to-3d", "text-to-texture", "remesh")

        Returns:
            MeshyTaskResult: Görev durumu ve sonuçları
        """
        endpoint_map = {
            "image-to-3d": "/openapi/v2/image-to-3d",
            "multi-image-to-3d": "/openapi/v2/multi-image-to-3d",
            "text-to-3d": "/openapi/v2/text-to-3d",
            "text-to-texture": "/openapi/v1/text-to-texture",
            "remesh": "/openapi/v1/remesh",
        }

        base_endpoint = endpoint_map.get(task_type, "/openapi/v2/image-to-3d")
        endpoint = f"{base_endpoint}/{task_id}"

        data = await self._request("GET", endpoint)
        return self._parse_task_result(data)

    async def wait_for_task(
        self,
        task_id: str,
        task_type: str = "image-to-3d",
        poll_interval: float = 5.0,
        max_wait: float = 600.0,
        progress_callback=None,
    ) -> MeshyTaskResult:
        """
        Bir görevin tamamlanmasını bekler (polling).

        Args:
            task_id: Görev ID'si
            task_type: Görev türü
            poll_interval: Kontrol aralığı (saniye)
            max_wait: Maksimum bekleme süresi (saniye)
            progress_callback: İlerleme geri çağrısı (async fonksiyon)
                               callback(task_id, progress, status) şeklinde çağrılır

        Returns:
            MeshyTaskResult: Tamamlanmış görev sonucu

        Raises:
            MeshyAPIError: Görev başarısız olursa veya zaman aşımı olursa
        """
        elapsed = 0.0

        log.info(f"⏳ Task bekleniyor: {task_id} (max {max_wait}sn)")

        while elapsed < max_wait:
            result = await self.get_task_status(task_id, task_type)

            if progress_callback:
                try:
                    await progress_callback(task_id, result.progress, result.status)
                except Exception as cb_err:
                    log.warning(f"Progress callback hatası: {cb_err}")

            if result.status == TaskStatus.SUCCEEDED:
                log.info(f"✅ Task tamamlandı: {task_id}")
                return result

            if result.status == TaskStatus.FAILED:
                error_msg = result.error or "Bilinmeyen hata"
                log.error(f"❌ Task başarısız: {task_id} — {error_msg}")
                raise MeshyAPIError(500, f"Task başarısız oldu: {error_msg}")

            if result.status == TaskStatus.EXPIRED:
                log.error(f"⏰ Task süresi doldu: {task_id}")
                raise MeshyAPIError(408, "Task süresi doldu")

            log.debug(
                f"   {task_id}: %{result.progress} "
                f"({result.status.value}) [{elapsed:.0f}/{max_wait:.0f}sn]"
            )

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise MeshyAPIError(408, f"Zaman aşımı ({max_wait}sn): Task hâlâ {result.status.value}")

    # ═══════════════════════════════════════════════════════════════════════
    #  MODEL İNDİRME
    # ═══════════════════════════════════════════════════════════════════════

    async def download_model(
        self,
        model_url: str,
        save_path: str,
    ) -> str:
        """
        Üretilen 3D modeli indirir ve diske kaydeder.

        Args:
            model_url: İndirilecek modelin URL'i
            save_path: Kaydedilecek dosya yolu

        Returns:
            save_path: Kaydedilen dosyanın yolu
        """
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        async with httpx.AsyncClient(timeout=120.0) as dl_client:
            response = await dl_client.get(model_url)
            response.raise_for_status()

            with open(save_path, "wb") as f:
                f.write(response.content)

        file_size_mb = os.path.getsize(save_path) / (1024 * 1024)
        log.info(f"📥 Model indirildi: {save_path} ({file_size_mb:.1f} MB)")
        return save_path

    async def download_thumbnail(
        self,
        thumbnail_url: str,
        save_path: str,
    ) -> str:
        """Thumbnail görselini indirir."""
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        async with httpx.AsyncClient(timeout=30.0) as dl_client:
            response = await dl_client.get(thumbnail_url)
            response.raise_for_status()

            with open(save_path, "wb") as f:
                f.write(response.content)

        log.info(f"📥 Thumbnail indirildi: {save_path}")
        return save_path

    # ═══════════════════════════════════════════════════════════════════════
    #  KREDİ / BAKİYE
    # ═══════════════════════════════════════════════════════════════════════

    async def get_balance(self) -> Dict[str, Any]:
        """
        Meshy hesap bakiyesi ve kredi bilgisini sorgular.

        Returns:
            {
                "total_credits": int,
                "used_credits": int,
                "remaining_credits": int,
                "plan": str,
            }
        """
        try:
            data = await self._request("GET", "/openapi/v1/balance")
            log.info(f"💰 Bakiye: {data}")
            return data
        except MeshyAPIError as e:
            log.warning(f"Bakiye sorgulanamadı: {e}")
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════════════════
    #  TASK LİSTELEME
    # ═══════════════════════════════════════════════════════════════════════

    async def list_tasks(
        self,
        task_type: str = "image-to-3d",
        page: int = 1,
        page_size: int = 10,
    ) -> List[MeshyTaskResult]:
        """
        Belirli türdeki görevleri listeler.

        Args:
            task_type: Görev türü
            page: Sayfa numarası
            page_size: Sayfa başına görev sayısı

        Returns:
            Task listesi
        """
        endpoint_map = {
            "image-to-3d": "/openapi/v2/image-to-3d",
            "text-to-3d": "/openapi/v2/text-to-3d",
            "text-to-texture": "/openapi/v1/text-to-texture",
        }

        endpoint = endpoint_map.get(task_type, "/openapi/v2/image-to-3d")
        params = {"page": page, "pageSize": page_size}

        data = await self._request("GET", endpoint, params=params)

        # API yanıtı liste veya pagination obje olabilir
        if isinstance(data, list):
            return [self._parse_task_result(item) for item in data]
        elif isinstance(data, dict) and "data" in data:
            return [self._parse_task_result(item) for item in data["data"]]
        return []

    # ═══════════════════════════════════════════════════════════════════════
    #  YÜKSEK SEVİYE KOLAYLIK FONKSİYONLARI
    # ═══════════════════════════════════════════════════════════════════════

    async def generate_3d_from_image(
        self,
        image_url: str,
        save_dir: str,
        model: MeshyModel = MeshyModel.MESHY_6,
        output_format: OutputFormat = OutputFormat.GLB,
        progress_callback=None,
    ) -> Dict[str, str]:
        """
        Tek çağrıda görsel → 3D model üretimi + indirme.

        Kullanımı kolay, tüm süreci kapsar:
        1. Task oluşturur
        2. Tamamlanmasını bekler
        3. GLB dosyasını indirir

        Args:
            image_url: Görsel URL'i (public erişilebilir)
            save_dir: Modelin kaydedileceği dizin
            model: Meshy model seçimi
            output_format: Çıktı formatı
            progress_callback: İlerleme callback'i

        Returns:
            {
                "task_id": str,
                "model_path": str,      # İndirilen GLB dosyasının yolu
                "thumbnail_path": str,   # Thumbnail dosyasının yolu
                "model_urls": dict,      # Tüm format URL'leri
            }
        """
        # 1. Task oluştur
        task_id = await self.image_to_3d(
            image_url=image_url,
            model=model,
            output_format=output_format,
        )

        # 2. Tamamlanmasını bekle
        result = await self.wait_for_task(
            task_id=task_id,
            task_type="image-to-3d",
            progress_callback=progress_callback,
        )

        # 3. Model dosyasını indir
        os.makedirs(save_dir, exist_ok=True)

        format_key = output_format.value
        model_url = result.model_urls.get(format_key, "")

        if not model_url:
            # Herhangi bir format URL'i al
            for fmt, url in result.model_urls.items():
                model_url = url
                format_key = fmt
                break

        output = {
            "task_id": task_id,
            "model_path": "",
            "thumbnail_path": "",
            "model_urls": result.model_urls,
        }

        if model_url:
            model_path = os.path.join(save_dir, f"model_{task_id}.{format_key}")
            await self.download_model(model_url, model_path)
            output["model_path"] = model_path

        if result.thumbnail_url:
            thumb_path = os.path.join(save_dir, f"thumb_{task_id}.png")
            await self.download_thumbnail(result.thumbnail_url, thumb_path)
            output["thumbnail_path"] = thumb_path

        return output

    async def generate_3d_from_text(
        self,
        prompt: str,
        save_dir: str,
        model: MeshyModel = MeshyModel.MESHY_6,
        art_style: str = "realistic",
        progress_callback=None,
    ) -> Dict[str, str]:
        """
        Tek çağrıda metin → 3D model üretimi + indirme.

        Args:
            prompt: 3D model açıklaması
            save_dir: Modelin kaydedileceği dizin
            model: Meshy model seçimi
            art_style: Sanat stili
            progress_callback: İlerleme callback'i

        Returns:
            generate_3d_from_image ile aynı formatta sonuç
        """
        # 1. Task oluştur
        task_id = await self.text_to_3d(
            prompt=prompt,
            model=model,
            art_style=art_style,
        )

        # 2. Tamamlanmasını bekle
        result = await self.wait_for_task(
            task_id=task_id,
            task_type="text-to-3d",
            progress_callback=progress_callback,
        )

        # 3. Model dosyasını indir
        os.makedirs(save_dir, exist_ok=True)

        output = {
            "task_id": task_id,
            "model_path": "",
            "thumbnail_path": "",
            "model_urls": result.model_urls,
        }

        glb_url = result.model_urls.get("glb", "")
        if glb_url:
            model_path = os.path.join(save_dir, f"model_{task_id}.glb")
            await self.download_model(glb_url, model_path)
            output["model_path"] = model_path

        if result.thumbnail_url:
            thumb_path = os.path.join(save_dir, f"thumb_{task_id}.png")
            await self.download_thumbnail(result.thumbnail_url, thumb_path)
            output["thumbnail_path"] = thumb_path

        return output

    # ═══════════════════════════════════════════════════════════════════════
    #  SAĞLIK KONTROLÜ
    # ═══════════════════════════════════════════════════════════════════════

    async def health_check(self) -> Dict[str, Any]:
        """
        Meshy API bağlantısını ve API key geçerliliğini test eder.

        Returns:
            {
                "status": "ok" | "error",
                "mode": "live" | "test",
                "api_key_valid": bool,
                "message": str,
            }
        """
        is_test = self._api_key == MESHY_TEST_API_KEY

        try:
            balance = await self.get_balance()
            has_error = "error" in balance

            return {
                "status": "ok" if not has_error else "warning",
                "mode": "test" if is_test else "live",
                "api_key_valid": not has_error,
                "balance": balance if not has_error else None,
                "message": "Meshy AI bağlantısı aktif ✅" if not has_error else f"Bakiye alınamadı: {balance.get('error')}",
            }
        except Exception as e:
            return {
                "status": "error",
                "mode": "test" if is_test else "live",
                "api_key_valid": False,
                "message": f"Meshy AI bağlantı hatası: {str(e)}",
            }


# ═══════════════════════════════════════════════════════════════════════════
#  MODÜL SEVİYESİ SINGLETON
# ═══════════════════════════════════════════════════════════════════════════

# Uygulama genelinde tek bir MeshyService instance'ı kullanılabilir:
#   from app.services.meshy_service import meshy_client
#   result = await meshy_client.image_to_3d(...)

meshy_client = MeshyService()
