"""
tripo_service.py
────────────────
Tripo3D AI API entegrasyon servisi.

Desteklenen özellikler:
  • Image-to-3D  (tek görsel → 3D model)
  • Multi-Image-to-3D (çoklu görsel → 3D model)
  • Text-to-3D   (metin prompt → 3D model)
  • Task durumu takibi (polling)
  • Model dosyası indirme
  • Bakiye sorgulama
  • Dosya yükleme (multipart → file_token)

Kullanım:
    from app.services.tripo_service import TripoService

    tripo = TripoService()  # .env'den API key alır
    task_id = await tripo.image_to_3d(image_url="https://...")
    result  = await tripo.wait_for_task(task_id)

ÖNEMLİ: Tripo3D model indirme URL'leri ~5 dakikada expire olur.
         wait_for_task tamamlandıktan sonra hemen indirme yapılmalıdır!
"""

import os
import asyncio
import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

import httpx
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("tripo_service")


# ─── SABITLER ──────────────────────────────────────────────────────────────────

TRIPO_BASE_URL = os.getenv("TRIPO_BASE_URL", "https://api.tripo3d.ai/v2/openapi")
TRIPO_API_KEY = os.getenv("TRIPO_API_KEY", "")

# Varsayılan olarak test modunda çalış (geliştirme sırasında kredi harcamaz)
TRIPO_MODE = os.getenv("TRIPO_MODE", "test")  # "live" | "test"


class TaskStatus(str, Enum):
    """Tripo3D API task durumları."""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    BANNED = "banned"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class OutputFormat(str, Enum):
    """Desteklenen 3D çıktı formatları."""
    GLB = "glb"
    FBX = "fbx"
    OBJ = "obj"
    USDZ = "usdz"
    STL = "stl"


@dataclass
class TripoTaskResult:
    """Tripo3D API task sonucu."""
    task_id: str
    status: TaskStatus
    progress: int = 0
    model_url: Optional[str] = None
    rendered_image_url: Optional[str] = None
    error: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class TripoAPIError(Exception):
    """Tripo3D API hata sınıfı."""
    def __init__(self, code: int, message: str, suggestion: str = ""):
        self.code = code
        self.message = message
        self.suggestion = suggestion
        super().__init__(f"Tripo3D API Hatası [{code}]: {message}")


class TripoService:
    """
    Tripo3D AI API istemcisi.

    Tüm API çağrıları async/await ile yapılır.
    httpx.AsyncClient her çağrıda oluşturulup kapatılır
    veya `async with TripoService() as tripo:` şeklinde context manager olarak kullanılabilir.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self._api_key = api_key or TRIPO_API_KEY
        self._base_url = (base_url or TRIPO_BASE_URL).rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

        if not self._api_key:
            log.warning(
                "⚠️  TRIPO_API_KEY tanımlanmamış! "
                ".env dosyasına TRIPO_API_KEY=tsk_... ekleyin."
            )

    # ── Context Manager ────────────────────────────────────────────────────

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
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
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Context manager dışında kullanılırsa geçici client oluşturur."""
        if self._client:
            return self._client
        return httpx.AsyncClient(
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
        Tripo3D yanıt formatı: {"code": 0, "data": {...}}
        code=0 başarılı demektir.
        """
        client = await self._get_client()
        owns_client = client != self._client

        url = f"{self._base_url}{endpoint}"

        try:
            headers = None
            # Dosya yükleme için Content-Type'ı kaldır (multipart otomatik ayarlanır)
            if files:
                headers = {
                    "Authorization": f"Bearer {self._api_key}",
                }

            response = await client.request(
                method=method,
                url=url,
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
                    url=url,
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
                raise TripoAPIError(response.status_code, error_body)

            # 204 No Content gibi durumlar
            if response.status_code == 204:
                return {}

            result = response.json()

            # Tripo3D yanıt formatı: {"code": 0, "data": {...}}
            if isinstance(result, dict) and "code" in result:
                if result["code"] != 0:
                    raise TripoAPIError(
                        code=result["code"],
                        message=result.get("message", "Bilinmeyen hata"),
                        suggestion=result.get("suggestion", ""),
                    )
                return result.get("data", result)

            return result

        finally:
            if owns_client:
                await client.aclose()

    def _parse_task_result(self, data: Dict[str, Any]) -> TripoTaskResult:
        """API yanıtını TripoTaskResult objesine dönüştürür."""
        output = data.get("output", {}) or {}
        result_obj = data.get("result", {}) or {}
        
        # Model URL bulma
        model_url = None
        if isinstance(output, dict):
            model_url = output.get("model") or output.get("pbr_model")
            
        if not model_url and isinstance(result_obj, dict):
            pbr_model = result_obj.get("pbr_model")
            if isinstance(pbr_model, dict):
                model_url = pbr_model.get("url")
            elif isinstance(pbr_model, str):
                model_url = pbr_model
                
            if not model_url:
                model_val = result_obj.get("model")
                if isinstance(model_val, dict):
                    model_url = model_val.get("url")
                elif isinstance(model_val, str):
                    model_url = model_val
                    
        # Rendered image URL bulma
        rendered_image_url = None
        if isinstance(output, dict):
            rendered_image_url = output.get("rendered_image")
            
        if not rendered_image_url and isinstance(result_obj, dict):
            img_val = result_obj.get("rendered_image")
            if isinstance(img_val, dict):
                rendered_image_url = img_val.get("url")
            elif isinstance(img_val, str):
                rendered_image_url = img_val

        return TripoTaskResult(
            task_id=data.get("task_id", ""),
            status=TaskStatus(data.get("status", "queued")),
            progress=data.get("progress", 0),
            model_url=model_url,
            rendered_image_url=rendered_image_url,
            error=data.get("task_error", {}).get("message") if isinstance(data.get("task_error"), dict) else data.get("task_error"),
            raw=data,
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  DOSYA YÜKLEME
    # ═══════════════════════════════════════════════════════════════════════

    async def upload_image(self, file_path: str) -> str:
        """
        Yerel bir görsel dosyasını Tripo3D'ye yükler.

        Args:
            file_path: Yüklenecek dosyanın yerel yolu

        Returns:
            file_token: Tripo3D API'de dosyaya referans veren token
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")

        with open(file_path, "rb") as f:
            file_data = f.read()

        filename = os.path.basename(file_path)

        # Mime type belirleme
        ext = filename.lower().split(".")[-1]
        if ext in ("jpg", "jpeg"):
            mime_type = "image/jpeg"
        elif ext == "png":
            mime_type = "image/png"
        elif ext == "webp":
            mime_type = "image/webp"
        else:
            mime_type = "image/jpeg"

        result = await self._request(
            "POST",
            "/upload/sts",
            files={"file": (filename, file_data, mime_type)},
        )

        file_token = result.get("image_token", "")
        log.info(f"📤 Dosya yüklendi: {filename} → token={file_token[:20]}...")
        return file_token

    # ═══════════════════════════════════════════════════════════════════════
    #  IMAGE-TO-3D
    # ═══════════════════════════════════════════════════════════════════════

    async def image_to_3d(
        self,
        image_url: Optional[str] = None,
        file_token: Optional[str] = None,
        model_version: str = "default",
    ) -> str:
        """
        Tek bir görselden 3D model üretir.

        Args:
            image_url: Görsel URL'i (public erişilebilir olmalı)
            file_token: upload_image() ile alınan dosya token'ı
            model_version: Model versiyonu

        Returns:
            task_id: Oluşturulan görevin ID'si
        """
        if not image_url and not file_token:
            raise ValueError("image_url veya file_token gereklidir.")

        payload: Dict[str, Any] = {
            "type": "image_to_model",
        }

        if file_token:
            payload["file"] = {"type": "png", "file_token": file_token}
        elif image_url:
            payload["file"] = {"type": "png", "url": image_url}

        if model_version != "default":
            payload["model_version"] = model_version

        log.info(f"Image-to-3D başlatılıyor → model_version={model_version}")
        result = await self._request("POST", "/task", json=payload)

        task_id = result.get("task_id", "")
        log.info(f"✅ Task oluşturuldu: {task_id}")
        return task_id

    async def multi_image_to_3d(
        self,
        image_urls: Optional[List[str]] = None,
        file_tokens: Optional[List[str]] = None,
        model_version: str = "default",
    ) -> str:
        """
        Birden fazla görüntüden 3D model üretir (daha iyi yapısal doğruluk).

        Args:
            image_urls: Görsel URL listesi (public erişilebilir)
            file_tokens: upload_image() ile alınan dosya token'ları
            model_version: Model versiyonu

        Returns:
            task_id: Oluşturulan görevin ID'si
        """
        payload: Dict[str, Any] = {
            "type": "multiview_to_model",
        }

        # Tripo multiview task accepts up to 4 images: [front, right, left, back] (angles: 0, 90, 180, 270)
        # So we slice the inputs to exactly 4 items.
        if file_tokens:
            file_tokens = file_tokens[:4]
            payload["files"] = [
                {"type": "png", "file_token": token} for token in file_tokens
            ]
        elif image_urls:
            image_urls = image_urls[:4]
            payload["files"] = [
                {"type": "png", "url": url} for url in image_urls
            ]
        else:
            raise ValueError("image_urls veya file_tokens gereklidir.")

        if model_version != "default":
            payload["model_version"] = model_version

        count = len(file_tokens or image_urls or [])
        log.info(f"🖼️  Multi-Image-to-3D başlatılıyor → {count} görsel (maks 4)")
        result = await self._request("POST", "/task", json=payload)

        task_id = result.get("task_id", "")
        log.info(f"✅ Task oluşturuldu: {task_id}")
        return task_id

    # ═══════════════════════════════════════════════════════════════════════
    #  TEXT-TO-3D
    # ═══════════════════════════════════════════════════════════════════════

    async def text_to_3d(
        self,
        prompt: str,
        model_version: str = "default",
    ) -> str:
        """
        Metin açıklamasından 3D model üretir.

        Args:
            prompt: 3D model açıklaması (İngilizce önerilir)
            model_version: Model versiyonu

        Returns:
            task_id: Oluşturulan görevin ID'si
        """
        payload: Dict[str, Any] = {
            "type": "text_to_model",
            "prompt": prompt,
        }

        if model_version != "default":
            payload["model_version"] = model_version

        log.info(f"Text-to-3D başlatılıyor → '{prompt[:50]}...'")
        result = await self._request("POST", "/task", json=payload)

        task_id = result.get("task_id", "")
        log.info(f"✅ Task oluşturuldu: {task_id}")
        return task_id

    # ═══════════════════════════════════════════════════════════════════════
    #  TASK YÖNETİMİ
    # ═══════════════════════════════════════════════════════════════════════

    async def get_task_status(self, task_id: str) -> TripoTaskResult:
        """
        Bir görevin mevcut durumunu sorgular.

        Args:
            task_id: Görev ID'si

        Returns:
            TripoTaskResult: Görev durumu ve sonuçları
        """
        data = await self._request("GET", f"/task/{task_id}")
        return self._parse_task_result(data)

    async def wait_for_task(
        self,
        task_id: str,
        poll_interval: float = 5.0,
        max_wait: float = 600.0,
        progress_callback=None,
    ) -> TripoTaskResult:
        """
        Bir görevin tamamlanmasını bekler (polling).

        Args:
            task_id: Görev ID'si
            poll_interval: Kontrol aralığı (saniye)
            max_wait: Maksimum bekleme süresi (saniye)
            progress_callback: İlerleme geri çağrısı (async fonksiyon)
                               callback(task_id, progress, status) şeklinde çağrılır

        Returns:
            TripoTaskResult: Tamamlanmış görev sonucu

        Raises:
            TripoAPIError: Görev başarısız olursa veya zaman aşımı olursa
        """
        elapsed = 0.0

        log.info(f"⏳ Task bekleniyor: {task_id} (max {max_wait}sn)")

        result = None
        while elapsed < max_wait:
            result = await self.get_task_status(task_id)

            if progress_callback:
                try:
                    await progress_callback(task_id, result.progress, result.status)
                except Exception as cb_err:
                    log.warning(f"Progress callback hatası: {cb_err}")

            if result.status == TaskStatus.SUCCESS:
                log.info(f"✅ Task tamamlandı: {task_id}")
                return result

            if result.status == TaskStatus.FAILED:
                error_msg = result.error or "Bilinmeyen hata"
                log.error(f"❌ Task başarısız: {task_id} — {error_msg}")
                raise TripoAPIError(500, f"Task başarısız oldu: {error_msg}")

            if result.status == TaskStatus.BANNED:
                log.error(f"🚫 Task yasaklandı: {task_id}")
                raise TripoAPIError(403, "Task yasaklandı (banned)")

            if result.status == TaskStatus.EXPIRED:
                log.error(f"⏰ Task süresi doldu: {task_id}")
                raise TripoAPIError(408, "Task süresi doldu")

            if result.status == TaskStatus.CANCELLED:
                log.error(f"🚫 Task iptal edildi: {task_id}")
                raise TripoAPIError(499, "Task iptal edildi")

            log.debug(
                f"   {task_id}: %{result.progress} "
                f"({result.status.value}) [{elapsed:.0f}/{max_wait:.0f}sn]"
            )

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        final_status = result.status.value if result else "unknown"
        raise TripoAPIError(408, f"Zaman aşımı ({max_wait}sn): Task hâlâ {final_status}")

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

        ÖNEMLİ: Tripo3D model URL'leri ~5 dakikada expire olur.
        wait_for_task tamamlandıktan hemen sonra çağrılmalıdır.

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

    # ═══════════════════════════════════════════════════════════════════════
    #  KREDİ / BAKİYE
    # ═══════════════════════════════════════════════════════════════════════

    async def get_balance(self) -> Dict[str, Any]:
        """
        Tripo3D hesap bakiyesi ve kredi bilgisini sorgular.

        Returns:
            {
                "balance": int,
                "frozen": int,
                ...
            }
        """
        try:
            data = await self._request("GET", "/user/balance")
            log.info(f"💰 Bakiye: {data}")
            return data
        except TripoAPIError as e:
            log.warning(f"Bakiye sorgulanamadı: {e}")
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════════════════
    #  SAĞLIK KONTROLÜ
    # ═══════════════════════════════════════════════════════════════════════

    async def health_check(self) -> Dict[str, Any]:
        """
        Tripo3D API bağlantısını ve API key geçerliliğini test eder.

        Returns:
            {
                "status": "ok" | "error",
                "mode": "live" | "test",
                "api_key_valid": bool,
                "message": str,
            }
        """
        is_test = TRIPO_MODE == "test"

        if not self._api_key:
            return {
                "status": "error",
                "mode": "test" if is_test else "live",
                "api_key_valid": False,
                "message": "TRIPO_API_KEY tanımlanmamış!",
            }

        try:
            balance = await self.get_balance()
            has_error = "error" in balance

            return {
                "status": "ok" if not has_error else "warning",
                "mode": "test" if is_test else "live",
                "api_key_valid": not has_error,
                "balance": balance if not has_error else None,
                "message": "Tripo3D AI bağlantısı aktif ✅" if not has_error else f"Bakiye alınamadı: {balance.get('error')}",
            }
        except Exception as e:
            return {
                "status": "error",
                "mode": "test" if is_test else "live",
                "api_key_valid": False,
                "message": f"Tripo3D AI bağlantı hatası: {str(e)}",
            }

    async def texture_model(
        self,
        original_model_task_id: str,
        prompt: str,
        texture_format: str = "standard",
        model_version: str = "default",
    ) -> str:
        """
        Mevcut bir 3D modeli metin açıklamasına göre kaplar (texture/edit).

        Args:
            original_model_task_id: Kaynak modelin task ID'si
            prompt: Kaplama/stil açıklaması (İngilizce)
            texture_format: "standard" veya "HD"
            model_version: Model versiyonu

        Returns:
            task_id: Oluşturulan görevin ID'si
        """
        payload: Dict[str, Any] = {
            "type": "texture_model",
            "original_model_task_id": original_model_task_id,
            "texture": texture_format,
            "text": prompt,
        }

        if model_version != "default":
            payload["model_version"] = model_version

        log.info(f"Texture-Model başlatılıyor → original_task={original_model_task_id}, prompt='{prompt[:50]}...'")
        result = await self._request("POST", "/task", json=payload)

        task_id = result.get("task_id", "")
        log.info(f"✅ Texture Task oluşturuldu: {task_id}")
        return task_id


# ═══════════════════════════════════════════════════════════════════════════
#  MODÜL SEVİYESİ SINGLETON
# ═══════════════════════════════════════════════════════════════════════════

tripo_client = TripoService()


# ═══════════════════════════════════════════════════════════════════════════
#  PROMPT YARDIMCILARI VE ARKA PLAN İŞ HATTI (PIPELINE)
# ═══════════════════════════════════════════════════════════════════════════

COLOR_NAMES = {
    "#ffffff": "white",
    "#000000": "black",
    "#ff0000": "red",
    "#00ff00": "green",
    "#0000ff": "blue",
    "#ffff00": "yellow",
    "#808080": "grey",
    "#c0c0c0": "silver",
    "#ffa500": "orange",
    "#800080": "purple",
    "#ffc0cb": "pink",
    "#a52a2a": "brown",
    "#ffd700": "gold",
}

def get_color_name(hex_code: str) -> str:
    if not hex_code:
        return ""
    hex_clean = hex_code.strip().lower()
    return COLOR_NAMES.get(hex_clean, hex_clean)

def build_modification_prompt(car_name: str, jant_name: Optional[str], color_name: Optional[str], paint_location: Optional[str]) -> str:
    prompt_parts = []
    if car_name:
        prompt_parts.append(f"A 3D model of a {car_name}")
    else:
        prompt_parts.append("A 3D model of a car")
        
    if color_name:
        loc = paint_location or "body"
        if loc == "tum_kaporta" or loc == "all body":
            loc_eng = "entire body"
        elif loc == "on_tampon" or loc == "front bumper":
            loc_eng = "front bumper"
        else:
            loc_eng = loc
        prompt_parts.append(f"with {color_name} color painted on the {loc_eng}")
        
    if jant_name:
        prompt_parts.append(f"fitted with sporty {jant_name} custom wheels/rims")
        
    prompt_parts.append("highly detailed, photorealistic textures, PBR materials")
    return ", ".join(prompt_parts)


async def run_tripo_3d_pipeline(scan_id: int, mode: str = "draft"):
    """
    Arka planda Tripo3D 2 aşamalı iş hattını yönetir.
    - 3D model rekonstrüksiyonu (Draft için tek görsel, Premium için 8 görsel)
    - Tekstürleme (kullanıcının seçtiği jant/renk seçeneklerine göre prompt)
    - GLB modelinin indirilmesi ve DB güncellenmesi
    """
    import uuid
    import httpx
    
    # Dairesel importları önlemek için yerel importlar
    from app.database.db import AsyncSessionLocal
    from app.database.models import Scans, Processed3D, Modification
    from sqlalchemy import select, update
    from sqlalchemy.orm import selectinload
    
    log.info(f"🚀 Tripo3D Pipeline Başlatıldı → scan_id={scan_id}, mod={mode}")
    
    try:
        # 1. DB'den scan ve resimleri al
        async with AsyncSessionLocal() as db:
            scan_res = await db.execute(
                select(Scans)
                .where(Scans.scan_id == scan_id)
                .options(selectinload(Scans.images))
            )
            scan = scan_res.scalar_one_or_none()
            if not scan:
                log.error(f"Scan {scan_id} bulunamadı!")
                return
                
            if not scan.images:
                log.error(f"Scan {scan_id} için görsel bulunamadı!")
                await db.execute(
                    update(Scans).where(Scans.scan_id == scan_id).values(status="failed")
                )
                await db.commit()
                return

            # Scan durumunu güncelle
            await db.execute(
                update(Scans).where(Scans.scan_id == scan_id).values(status="running")
            )
            await db.commit()

            # Görselleri Tripo'ya yükle (Yerel dosya varsa doğrudan yükle, yoksa public URL kullan)
            file_tokens = []
            image_urls = []
            
            # Tripo multiview task accepts up to 4 images
            images_to_process = scan.images[:4] if mode == "premium" else [scan.images[0]]
            
            for img in images_to_process:
                local_path = img.image_url
                if local_path and not local_path.startswith("http"):
                    local_path = os.path.normpath(local_path)
                    
                if local_path and os.path.exists(local_path):
                    log.info(f"Scan {scan_id}: Görsel Tripo'ya yükleniyor → {local_path}")
                    try:
                        token = await tripo_client.upload_image(local_path)
                        file_tokens.append(token)
                    except Exception as upload_err:
                        log.warning(f"Görsel yüklenemedi, URL kullanılacak: {upload_err}")
                        backend_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
                        img_url = f"{backend_url}/{img.image_url.replace(chr(92), '/')}"
                        image_urls.append(img_url)
                else:
                    backend_url = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
                    img_url = img.image_url
                    if img_url and not img_url.startswith("http"):
                        img_url = f"{backend_url}/{img_url.replace(chr(92), '/')}"
                    if img_url:
                        image_urls.append(img_url)

            car_name = scan.car_name
            
        # 2. Rekonstrüksiyon Görevi Oluştur (İlk aşama)
        recon_task_id = None
        
        if mode == "draft":
            log.info(f"Scan {scan_id}: Draft için image_to_3d başlatılıyor.")
            if file_tokens:
                recon_task_id = await tripo_client.image_to_3d(file_token=file_tokens[0])
            else:
                recon_task_id = await tripo_client.image_to_3d(image_url=image_urls[0])
        else:
            log.info(f"Scan {scan_id}: Premium için multi_image_to_3d başlatılıyor.")
            if file_tokens:
                recon_task_id = await tripo_client.multi_image_to_3d(file_tokens=file_tokens)
            else:
                recon_task_id = await tripo_client.multi_image_to_3d(image_urls=image_urls)
            
        # DB'ye rekonstrüksiyon task ID'sini hemen kaydet ki sorgulanabilsin
        async with AsyncSessionLocal() as db:
            proc_res = await db.execute(
                select(Processed3D).where(Processed3D.scan_id == scan_id)
            )
            proc = proc_res.scalar_one_or_none()
            if proc:
                proc.tripo_reconstruction_task_id = recon_task_id
                proc.quality = mode
            else:
                proc = Processed3D(
                    scan_id=scan_id,
                    tripo_reconstruction_task_id=recon_task_id,
                    quality=mode
                )
                db.add(proc)
            await db.commit()

        # 3. Rekonstrüksiyonun bitmesini bekle
        recon_result = await tripo_client.wait_for_task(recon_task_id, poll_interval=5.0)
        
        if recon_result.status.value != "success":
            raise Exception(f"Rekonstrüksiyon başarısız oldu: {recon_result.error}")
            
        # 4. Modifikasyonları kontrol et ve gerekirse tekstürlemeyi (Texture-Model) başlat
        jant_name = None
        color_name = None
        paint_location = None
        
        async with AsyncSessionLocal() as db:
            mod_res = await db.execute(
                select(Modification)
                .where(Modification.scan_id == scan_id)
                .options(selectinload(Modification.jant), selectinload(Modification.colors))
            )
            mod = mod_res.scalar_one_or_none()
            if mod:
                if mod.jant:
                    jant_name = mod.jant.model_name
                if mod.colors:
                    color_name = get_color_name(mod.colors.color_code)
                paint_location = mod.paint_location
                
        # Eğer modifikasyon varsa tekstürleme yap, yoksa rekonstrüksiyon modelini kullan
        final_model_url = recon_result.model_url
        final_thumb_url = recon_result.rendered_image_url
        texture_task_id = None
        
        if jant_name or color_name:
            prompt = build_modification_prompt(car_name, jant_name, color_name, paint_location)
            log.info(f"Scan {scan_id}: Modifikasyon algılandı. Tekstürleme başlatılıyor: {prompt}")
            
            texture_task_id = await tripo_client.texture_model(
                original_model_task_id=recon_task_id,
                prompt=prompt
            )
            
            texture_result = await tripo_client.wait_for_task(texture_task_id, poll_interval=5.0)
            if texture_result.status.value != "success":
                raise Exception(f"Tekstürleme başarısız oldu: {texture_result.error}")
                
            final_model_url = texture_result.model_url
            if texture_result.rendered_image_url:
                final_thumb_url = texture_result.rendered_image_url
                
            # DB'ye tekstürleme task ID'sini kaydet
            async with AsyncSessionLocal() as db:
                proc_res = await db.execute(
                    select(Processed3D).where(Processed3D.scan_id == scan_id)
                )
                proc = proc_res.scalar_one_or_none()
                if proc:
                    proc.tripo_texture_task_id = texture_task_id
                await db.commit()
                
        # 5. Dosyayı indir
        upload_dir = os.path.join("uploads", "images_3d", f"scan_{scan_id}")
        os.makedirs(upload_dir, exist_ok=True)
        
        model_filename = f"model_{uuid.uuid4()}.glb"
        model_path = os.path.join(upload_dir, model_filename).replace("\\", "/")
        
        await tripo_client.download_model(final_model_url, model_path)
        
        # Küçük resmi indir (eğer varsa)
        local_thumb_path = None
        if final_thumb_url:
            thumb_dir = os.path.join("uploads", "thumbnails")
            os.makedirs(thumb_dir, exist_ok=True)
            thumb_filename = f"thumb_{scan_id}.png"
            local_thumb_path = os.path.join(thumb_dir, thumb_filename).replace("\\", "/")
            
            async with httpx.AsyncClient(timeout=30.0) as dl_client:
                response = await dl_client.get(final_thumb_url)
                response.raise_for_status()
                with open(local_thumb_path, "wb") as f:
                    f.write(response.content)
                    
        # 6. DB'yi Başarıyla Güncelle
        async with AsyncSessionLocal() as db:
            proc_res = await db.execute(
                select(Processed3D).where(Processed3D.scan_id == scan_id)
            )
            proc = proc_res.scalar_one_or_none()
            if proc:
                proc.model_url = model_path
                if local_thumb_path:
                    proc.thumbnail_url = local_thumb_path
            else:
                proc = Processed3D(
                    scan_id=scan_id,
                    model_url=model_path,
                    thumbnail_url=local_thumb_path or "",
                    quality=mode
                )
                db.add(proc)
                
            await db.execute(
                update(Scans).where(Scans.scan_id == scan_id).values(status="completed")
            )
            await db.commit()
            
        log.info(f"✅ Scan {scan_id} ({mode}): Tripo3D modeli başarıyla kaydedildi → {model_path}")
        
    except Exception as e:
        log.error(f"❌ Scan {scan_id} Pipeline Hatası: {e}", exc_info=True)
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Scans).where(Scans.scan_id == scan_id).values(status="failed")
            )
            await db.commit()


async def run_tripo_texturing_only(scan_id: int, recon_task_id: str, modification_id: int):
    """
    Arka planda sadece tekstürleme işlemini (texture_model) çalıştırır.
    Zaten rekonstrüksiyonu tamamlanmış bir modele yeni modifikasyonlar giydirmek için kullanılır.
    """
    import uuid
    import httpx
    
    from app.database.db import AsyncSessionLocal
    from app.database.models import Scans, Processed3D, Modification
    from sqlalchemy import select, update
    from sqlalchemy.orm import selectinload
    
    log.info(f"🚀 Tripo3D Texturing Only Başlatıldı → scan_id={scan_id}, recon_task_id={recon_task_id}")
    
    try:
        # Scan durumunu running yap
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Scans).where(Scans.scan_id == scan_id).values(status="running")
            )
            await db.commit()
            
            scan_res = await db.execute(select(Scans).where(Scans.scan_id == scan_id))
            scan = scan_res.scalar_one_or_none()
            car_name = scan.car_name if scan else ""
            
        # Modifikasyon seçeneklerini al
        jant_name = None
        color_name = None
        paint_location = None
        
        async with AsyncSessionLocal() as db:
            mod_res = await db.execute(
                select(Modification)
                .where(Modification.modification_id == modification_id)
                .options(selectinload(Modification.jant), selectinload(Modification.colors))
            )
            mod = mod_res.scalar_one_or_none()
            if mod:
                if mod.jant:
                    jant_name = mod.jant.model_name
                if mod.colors:
                    color_name = get_color_name(mod.colors.color_code)
                paint_location = mod.paint_location
                
        if not jant_name and not color_name:
            log.warning(f"Scan {scan_id}: Güncellenecek modifikasyon bulunamadı. İşlem sonlandırılıyor.")
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(Scans).where(Scans.scan_id == scan_id).values(status="completed")
                )
                await db.commit()
            return
            
        # Prompt oluştur ve tekstürle
        prompt = build_modification_prompt(car_name, jant_name, color_name, paint_location)
        log.info(f"Scan {scan_id}: Yeni modifikasyon giydiriliyor: {prompt}")
        
        texture_task_id = await tripo_client.texture_model(
            original_model_task_id=recon_task_id,
            prompt=prompt
        )
        
        texture_result = await tripo_client.wait_for_task(texture_task_id, poll_interval=5.0)
        if texture_result.status.value != "success":
            raise Exception(f"Tekstürleme başarısız oldu: {texture_result.error}")
            
        final_model_url = texture_result.model_url
        final_thumb_url = texture_result.rendered_image_url
        
        # Dosyayı indir
        upload_dir = os.path.join("uploads", "images_3d", f"scan_{scan_id}")
        os.makedirs(upload_dir, exist_ok=True)
        
        model_filename = f"model_{uuid.uuid4()}.glb"
        model_path = os.path.join(upload_dir, model_filename).replace("\\", "/")
        
        await tripo_client.download_model(final_model_url, model_path)
        
        # Küçük resmi indir
        local_thumb_path = None
        if final_thumb_url:
            thumb_dir = os.path.join("uploads", "thumbnails")
            os.makedirs(thumb_dir, exist_ok=True)
            thumb_filename = f"thumb_{scan_id}.png"
            local_thumb_path = os.path.join(thumb_dir, thumb_filename).replace("\\", "/")
            
            async with httpx.AsyncClient(timeout=30.0) as dl_client:
                response = await dl_client.get(final_thumb_url)
                response.raise_for_status()
                with open(local_thumb_path, "wb") as f:
                    f.write(response.content)
                    
        # DB güncelle
        async with AsyncSessionLocal() as db:
            proc_res = await db.execute(
                select(Processed3D).where(Processed3D.scan_id == scan_id)
            )
            proc = proc_res.scalar_one_or_none()
            if proc:
                proc.model_url = model_path
                proc.tripo_texture_task_id = texture_task_id
                if local_thumb_path:
                    proc.thumbnail_url = local_thumb_path
            else:
                proc = Processed3D(
                    scan_id=scan_id,
                    model_url=model_path,
                    thumbnail_url=local_thumb_path or "",
                    tripo_texture_task_id=texture_task_id
                )
                db.add(proc)
                
            await db.execute(
                update(Scans).where(Scans.scan_id == scan_id).values(status="completed")
            )
            await db.commit()
            
        log.info(f"✅ Scan {scan_id}: Yeni tekstür başarıyla kaydedildi → {model_path}")
        
    except Exception as e:
        log.error(f"❌ Scan {scan_id} Texturing Hatası: {e}", exc_info=True)
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Scans).where(Scans.scan_id == scan_id).values(status="failed")
            )
            await db.commit()
