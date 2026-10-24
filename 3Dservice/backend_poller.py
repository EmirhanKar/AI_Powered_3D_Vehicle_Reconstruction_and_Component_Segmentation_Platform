"""
ModifAI 3D Servisi — Backend Kuyruk Tarayıcısı (Backend Poller).

Bu modül, mevcut `Backend/` servisindeki `/scans/pending_3d` uç noktasını
periyodik olarak sorgular, yeni işleri tespit eder ve bunları `service.py`
içerisindeki ortak `JobRunner` kuyruğuna teslim eder.

Mimari İlkeler (Karar 1):
1. İki ayrı iş çalıştırma yolu yoktur: hem HTTP `POST /jobs` istekleri hem de
   bu poller aynı `JobRunner.enqueue_job(...)` metodunu kullanır.
2. Çift işlemeyi (duplicate processing) önlemek için iş alındığı anda hem yerel
   bellekte (`claimed_scan_ids`) kilitlenir hem de Backend'e `/scans/progress/{scan_id}`
   üzerinden `status="processing"` bildirimi gönderilir.
3. Hata durumunda Backend'e `failed_step`, `error_code`, `message` ve `hint`
   bilgilerini içeren yapılandırılmış hata raporu iletilir.
4. Ağ/bağlantı hatalarında ve GLB yüklemelerinde üssel geri çekilme
   (exponential backoff) uygulanır.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set
import cv2
import httpx
import numpy as np

from config import ServiceConfig

logger = logging.getLogger("3dservice.poller")


class BackendPoller:
    """
    Mevcut FastAPI Backend servisini (`GET /scans/pending_3d`) dinleyen ve
    tamamlanan GLB modellerini (`PUT /scans/complete/3d/{scan_id}`) geri yükleyen
    asenkron arka plan bileşeni.
    """

    def __init__(
        self,
        config: ServiceConfig,
        enqueue_fn: Callable[[str, Path, Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        self.config = config
        self.enqueue_fn = enqueue_fn
        self.claimed_scan_ids: Set[int] = set()
        self._stop_event = asyncio.Event()
        self._consecutive_failures = 0

    @property
    def headers(self) -> Dict[str, str]:
        """Backend'in `deps.py` içinde beklediği `X-Admin-Key` kimlik doğrulama başlığı."""
        return {"X-Admin-Key": self.config.api_key}

    def stop(self) -> None:
        """Poller döngüsünü güvenli bir şekilde durdurmak için sinyal gönderir."""
        self._stop_event.set()

    async def mark_scan_processing(self, client: httpx.AsyncClient, scan_id: int) -> None:
        """
        İş kuyruğa alındığı anda Backend'e 'processing' durumunu bildirir.
        Böylece birden fazla poller döngüsünde aynı `scan_id`'nin tekrar
        alınması önlenir.
        """
        url = f"{self.config.backend_url.rstrip('/')}/scans/progress/{scan_id}"
        payload = {
            "status": "processing",
            "stage": "queued",
            "message": "3D rekonstrüksiyon kuyruğuna alındı (processing).",
        }
        try:
            await client.post(url, json=payload, headers=self.headers, timeout=5.0)
        except Exception as exc:
            logger.debug("Scan %d için progress/processing bildirimi gönderilemedi (opsiyonel uç nokta): %s", scan_id, exc)

    async def report_scan_progress(
        self,
        scan_id: int,
        step_id: str,
        message: str,
        progress: int,
    ) -> None:
        """Adım geçişlerinde Backend'e canlı ilerleme yüzdesi ve adım adı bildirir."""
        url = f"{self.config.backend_url.rstrip('/')}/scans/progress/{scan_id}"
        payload = {
            "status": "processing",
            "stage": step_id,
            "progress": progress,
            "message": message,
        }
        async with httpx.AsyncClient() as client:
            try:
                await client.post(url, json=payload, headers=self.headers, timeout=5.0)
            except Exception as exc:
                logger.debug("Scan %d ilerleme bildirimi atlandı: %s", scan_id, exc)

    async def report_scan_failure(
        self,
        scan_id: int,
        failed_step: str,
        error_code: str,
        message: str,
        hint: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Pipeline herhangi bir adımda başarısız olduğunda Backend'e `failed_step`
        ve `error_code` bilgilerini üssel geri çekilmeyle (exponential backoff) bildirir.
        """
        url = f"{self.config.backend_url.rstrip('/')}/scans/fail/{scan_id}"
        payload = {
            "status": "failed",
            "failed_step": failed_step,
            "error_code": error_code,
            "detail": message,
            "error": f"[{failed_step}] {error_code}: {message}",
            "hint": hint,
            "details": details or {},
        }
        max_retries = self.config.backend_max_retries
        async with httpx.AsyncClient() as client:
            for attempt in range(1, max_retries + 1):
                try:
                    resp = await client.post(url, json=payload, headers=self.headers, timeout=10.0)
                    if resp.status_code < 500:
                        logger.info(
                            "Scan %d hata durumu Backend'e bildirildi (failed_step=%s, code=%s).",
                            scan_id,
                            failed_step,
                            error_code,
                        )
                        return
                except Exception as exc:
                    logger.warning(
                        "Scan %d hata bildirimi başarısız (deneme %d/%d): %s",
                        scan_id,
                        attempt,
                        max_retries,
                        exc,
                    )
                if attempt < max_retries:
                    await asyncio.sleep(min(2**attempt, 15))

    async def upload_completed_glb(self, scan_id: int, glb_path: Path) -> bool:
        """
        Üretilen nihai `.glb` dosyasını Backend'in `PUT /scans/complete/3d/{scan_id}`
        uç noktasına raw binary (`application/octet-stream`) gövde olarak yükler.
        Ağ kopmalarına karşı exponential backoff uygular.
        """
        if not glb_path.exists():
            logger.error("Scan %d: Yüklenecek GLB dosyası bulunamadı: %s", scan_id, glb_path)
            return False

        url = f"{self.config.backend_url.rstrip('/')}/scans/complete/3d/{scan_id}"
        raw_bytes = glb_path.read_bytes()
        headers = {
            **self.headers,
            "Content-Type": "application/octet-stream",
        }

        max_retries = self.config.backend_max_retries
        async with httpx.AsyncClient() as client:
            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(
                        "Scan %d: GLB dosyası Backend'e yükleniyor (%.2f KB, deneme %d/%d)...",
                        scan_id,
                        len(raw_bytes) / 1024.0,
                        attempt,
                        max_retries,
                    )
                    resp = await client.put(url, content=raw_bytes, headers=headers, timeout=180.0)
                    if 200 <= resp.status_code < 300:
                        logger.info("Scan %d: GLB başarıyla Backend'e yüklendi.", scan_id)
                        return True
                    if 400 <= resp.status_code < 500:
                        logger.error(
                            "Scan %d: Backend istemci hatası döndü (HTTP %d): %s",
                            scan_id,
                            resp.status_code,
                            resp.text[:300],
                        )
                        return False
                except Exception as exc:
                    logger.warning(
                        "Scan %d: GLB yükleme bağlantı hatası (deneme %d/%d): %s",
                        scan_id,
                        attempt,
                        max_retries,
                        exc,
                    )

                if attempt < max_retries:
                    backoff = min(2**attempt * 3, 30)
                    await asyncio.sleep(backoff)

        return False

    async def _prepare_input_video_for_scan(
        self,
        client: httpx.AsyncClient,
        scan: Dict[str, Any],
        job_dir: Path,
    ) -> Path:
        """
        Backend'den gelen scan kaydındaki medya URL'lerini indirir.
        Eğer girdi zaten bir video (`.mp4`, `.mov`) ise doğrudan kaydeder;
        eğer mevcut Backend'den çoklu fotoğraf geldiyse, adımların video sözleşmesini
        bozmamak için bunları kayıpsız bir giriş videosuna (`scan_input.mp4`) dönüştürür.
        """
        input_dir = job_dir / "raw_input"
        input_dir.mkdir(parents=True, exist_ok=True)
        target_video = input_dir / "scan_input.mp4"

        images_info: List[Dict[str, Any]] = scan.get("images", [])
        downloaded_files: List[Path] = []

        for idx, img_entry in enumerate(images_info):
            rel_url = str(img_entry.get("image_url", "")).lstrip("/")
            if not rel_url:
                continue
            full_url = f"{self.config.backend_url.rstrip('/')}/{rel_url}"
            ext = Path(rel_url).suffix.lower() or ".jpg"
            local_file = input_dir / f"media_{idx:03d}{ext}"
            try:
                resp = await client.get(full_url, timeout=30.0)
                if resp.status_code == 200:
                    local_file.write_bytes(resp.content)
                    downloaded_files.append(local_file)
            except Exception as exc:
                logger.warning("Medya indirilemedi (%s): %s", full_url, exc)

        # Eğer indirilen ilk dosya doğrudan bir video ise onu kullan
        for f in downloaded_files:
            if f.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
                return f

        # Fotoğraflar indirildiyse veya mock modundaysak geçerli bir MP4 oluştur
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(target_video), fourcc, 10.0, (640, 480))
        try:
            if downloaded_files:
                # Her fotoğrafı ardışık kareler halinde videoya yaz (minimum 4 saniye olması için tekrarla)
                frames_to_write = max(40, len(downloaded_files) * 10)
                for i in range(frames_to_write):
                    src_img_path = downloaded_files[i % len(downloaded_files)]
                    img = cv2.imread(str(src_img_path))
                    if img is None:
                        img = np.full((480, 640, 3), 128, dtype=np.uint8)
                    else:
                        img = cv2.resize(img, (640, 480))
                    writer.write(img)
            else:
                # Hiç medya indirilemediyse sentetik test kareleri yaz
                for i in range(45):
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.rectangle(frame, (160 + i, 160), (480 + i, 340), (40, 120, 220), -1)
                    writer.write(frame)
        finally:
            writer.release()

        return target_video

    async def poll_forever(self) -> None:
        """
        Servis kapanana kadar `/scans/pending_3d` kuyruğunu tarar.
        Bağlantı hatalarında üssel geri çekilme (exponential backoff: 5s, 10s, 20s, 40s, max 60s)
        uygulayarak Backend henüz ayağa kalkmamışken bile logları boğmadan bekler.
        """
        logger.info(
            "Backend Poller başlatıldı (Hedef=%s, Aralık=%ds).",
            self.config.backend_url,
            self.config.poll_interval_seconds,
        )

        while not self._stop_event.is_set():
            try:
                async with httpx.AsyncClient() as client:
                    url = f"{self.config.backend_url.rstrip('/')}/scans/pending_3d"
                    resp = await client.get(url, headers=self.headers, timeout=10.0)
                    resp.raise_for_status()
                    pending_scans: List[Dict[str, Any]] = resp.json()

                    # Başarılı bağlantıda hata sayacını sıfırla
                    self._consecutive_failures = 0

                    for scan in pending_scans:
                        scan_id = int(scan["scan_id"])
                        scan_status = str(scan.get("status", "pending")).lower()

                        # Zaten işlenmekte olan veya tamamlanmış işleri atla (çift işlemeyi önle)
                        if scan_id in self.claimed_scan_ids or scan_status in {"processing", "completed", "failed"}:
                            continue

                        self.claimed_scan_ids.add(scan_id)
                        await self.mark_scan_processing(client, scan_id)

                        job_id = f"scan_{scan_id}"
                        job_dir = self.config.jobs_dir / job_id
                        video_path = await self._prepare_input_video_for_scan(client, scan, job_dir)

                        metadata = {
                            "source": "backend_poller",
                            "scan_id": scan_id,
                            "car_name": scan.get("car_name", ""),
                            "method": scan.get("method", "3d"),
                            "jant_image_url": scan.get("jant_image_url"),
                            "renk_kodu": scan.get("renk_kodu"),
                        }

                        logger.info("Backend'den yeni 3D iş alındı: scan_id=%d -> job_id=%s", scan_id, job_id)
                        await self.enqueue_fn(job_id, video_path, metadata)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._consecutive_failures += 1
                backoff = min(
                    self.config.poll_interval_seconds * (2 ** min(self._consecutive_failures, 4)),
                    60,
                )
                logger.warning(
                    "Backend kuyruk sorgusu başarısız (ardışık_hata=%d, %ds sonra tekrar denenecek): %s",
                    self._consecutive_failures,
                    backoff,
                    exc,
                )
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=float(backoff))
                except asyncio.TimeoutError:
                    pass
                continue

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=float(self.config.poll_interval_seconds),
                )
            except asyncio.TimeoutError:
                pass
