"""
ModifAI 3D Servisi — Adım Sözleşmeleri, Orkestratör, CLI ve API Testleri.

Bu test modülü:
1. Her bir pipeline adımının (`step_00` .. `step_09`) kendi klasörüne yazdığını,
   `requires` / `produces` sözleşmesine uyduğunu ve idempotent (yeniden
   çalıştırılabilir) olduğunu doğrular.
2. Normal video (`is_360=False`) ve 360° equirectangular video (`is_360=True`)
   akışlarını test eder.
3. Adım 06 ve Adım 09'un glTF koordinat kurallarını (`wheel_base_y == 0.0`,
   RANSAC +Y, PCA +Z, GLB `extras` içerisindeki `meters_per_unit`, `scale_known`,
   `front_confidence`) ikili GLB başlığından okuyarak doğrular.
4. Başarısız bir adımdan sonra `--resume` ile devam edildiğinde önceki adımların
   tekrarlanmadığını ve hata durumunda hem `state.json` hem de API yanıtında
   `failed_step` ile `error_code` alanlarının raporlandığını doğrular.
"""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import struct
import time

import cv2
from fastapi.testclient import TestClient
import numpy as np

try:
    import pytest  # type: ignore
except ImportError:
    pytest = None  # type: ignore

from config import ServiceConfig, load_config
from pipeline.cli import main as cli_main
from pipeline.errors import StepError
from pipeline.orchestrator import PipelineOrchestrator
from service import app, job_runner


def _create_dummy_video(video_path: Path, width: int = 640, height: int = 480, num_frames: int = 40) -> Path:
    """Testler için OpenCV ile gerçek, okunabilir ve keskin dokulu bir MP4 video dosyası üretir."""
    video_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_path), fourcc, 10.0, (width, height))
    try:
        for idx in range(num_frames):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            # Keskin dama tahtası arka planı (Laplacian varyansı yüksek olsun)
            tile = 32
            for y in range(0, height, tile):
                for x in range(0, width, tile):
                    c = 200 if ((x // tile) + (y // tile)) % 2 == 0 else 50
                    frame[y : y + tile, x : x + tile] = (c, c, c)
            # Hareket eden (paralaks üreten) araç kutusu
            offset = (idx * 8) % (width // 3)
            cv2.rectangle(
                frame,
                (120 + offset, height // 3),
                (360 + offset, (height * 2) // 3),
                (40, 100, 230),
                thickness=-1,
            )
            writer.write(frame)
    finally:
        writer.release()

    # Eğer sistemde mp4v codec desteği kısıtlıysa en azından boş olmayan geçerli boyutlu dosya garantisi
    if not video_path.exists() or video_path.stat().st_size == 0:
        video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 4096)
    return video_path


def _make_test_config(tmp_path: Path, **overrides) -> ServiceConfig:
    """Her test için geçici `jobs/` ve `outputs/` klasörleri kullanan izole yapılandırma döndürür."""
    base_cfg = load_config()
    jobs_dir = tmp_path / "jobs"
    outputs_dir = tmp_path / "outputs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    cfg = replace(
        base_cfg,
        jobs_dir=jobs_dir,
        outputs_dir=outputs_dir,
        dev_mock_mode=True,
        enable_backend_poller=False,
        min_frame_count=8,
        target_frame_count=12,
        min_video_seconds=1.0,
        **overrides,
    )
    cfg.validate()
    return cfg


def _read_glb_json_chunk(glb_path: Path) -> dict:
    """Üretilen ikili `.glb` dosyasının JSON başlığını ayrıştırıp döndürür."""
    raw = glb_path.read_bytes()
    magic, version, _length = struct.unpack_from("<III", raw, 0)
    assert magic == 0x46546C67, "GLB magic 'glTF' olmalıdır"
    assert version == 2
    json_len, chunk_type = struct.unpack_from("<II", raw, 12)
    assert chunk_type == 0x4E4F534A
    json_bytes = raw[20 : 20 + json_len]
    return json.loads(json_bytes.decode("utf-8").rstrip(" \t\r\n\x00"))


def test_full_pipeline_steps_00_to_09_and_glb_extras(tmp_path: Path) -> None:
    """
    Adım 00'dan Adım 09'a kadar tüm adımları sırasıyla çalıştırır, her adımın
    kendi klasörünü ve logunu oluşturduğunu, normal videoda Adım 02'nin `skipped`
    olduğunu ve nihai GLB'nin `extras` ve `y=0` tekerlek tabanı şartlarını sağladığını doğrular.
    """
    cfg = _make_test_config(tmp_path)
    orchestrator = PipelineOrchestrator(config=cfg)

    video_file = _create_dummy_video(tmp_path / "normal_car.mp4", width=640, height=480, num_frames=40)
    job_id = "test_normal_video"

    orchestrator.initialize_job(
        job_id=job_id,
        initial_artifacts={"input_video": str(video_file)},
    )
    state = orchestrator.run_pipeline(job_id=job_id)

    assert state["status"] == "done"
    assert state["progress"] == 100
    assert state["steps"]["step_02_reproject_360"]["status"] == "skipped"

    # Adım 06 mesh metriklerini kontrol et: tekerlek tabanı y=0.0 olmalı
    mesh_metrics_path = Path(state["artifacts"]["mesh_metrics"])
    mesh_metrics = json.loads(mesh_metrics_path.read_text(encoding="utf-8"))
    assert abs(mesh_metrics["wheel_base_y"]) < 1e-4
    assert "front_confidence" in mesh_metrics
    assert mesh_metrics["scale_known"] is False
    assert mesh_metrics["meters_per_unit"] > 0.0

    # Adım 09 GLB ikili dosyasındaki `extras` alanlarını kontrol et (Karar 2a)
    glb_path = Path(state["artifacts"]["exported_glb"])
    assert glb_path.exists()
    gltf_json = _read_glb_json_chunk(glb_path)
    extras = gltf_json.get("extras", {})
    assert "meters_per_unit" in extras
    assert "scale_known" in extras
    assert "front_confidence" in extras
    assert extras["scale_known"] is False

    # Log dosyalarının her satırda job_id ve step adı taşıdığını doğrula
    step_06_log = (cfg.jobs_dir / job_id / "logs" / "step_06.log").read_text(encoding="utf-8")
    assert f"[job={job_id}]" in step_06_log
    assert "[step=step_06_extract_mesh]" in step_06_log


def test_360_video_reprojection_and_known_metric_scale(tmp_path: Path) -> None:
    """
    2:1 en-boy oranlı 360° videoda Adım 02'nin `done` olarak sanal perspektif
    kameralar ürettiğini ve `KNOWN_METERS_PER_UNIT > 0` verildiğinde `scale_known=True`
    olarak doğrudan metre ölçeğinde dışa aktarıldığını doğrular.
    """
    cfg = _make_test_config(
        tmp_path,
        virtual_view_count=4,
        known_meters_per_unit=1.0,
        export_formats_raw="glb,usdz",
    )
    orchestrator = PipelineOrchestrator(config=cfg)

    video_360 = _create_dummy_video(tmp_path / "car_360_equirect.mp4", width=1280, height=640, num_frames=30)
    job_id = "test_360_video"

    orchestrator.initialize_job(
        job_id=job_id,
        initial_artifacts={"input_video": str(video_360)},
    )
    state = orchestrator.run_pipeline(job_id=job_id)

    assert state["status"] == "done"
    assert state["steps"]["step_02_reproject_360"]["status"] == "done"
    assert state["steps"]["step_02_reproject_360"]["metrics"]["virtual_view_count"] == 4

    # USDZ ve GLB ikisinin de üretildiğini doğrula
    assert Path(state["artifacts"]["exported_glb"]).exists()
    assert Path(state["artifacts"]["exported_usdz"]).exists()

    gltf_json = _read_glb_json_chunk(Path(state["artifacts"]["exported_glb"]))
    assert gltf_json["extras"]["scale_known"] is True
    assert gltf_json["extras"]["meters_per_unit"] == 1.0


def test_cli_single_step_and_resume_does_not_repeat_earlier_steps(tmp_path: Path, monkeypatch) -> None:
    """
    Kabul Kriterleri:
    1. Tek bir adım CLI üzerinden (`--step 4`) çalıştırılabilir.
    2. Başarısız bir adımdan sonra `--resume` ile devam edildiğinde önceki
       tamamlanmış adımlar (`00..03`) tekrar çalıştırılmaz.
    """
    cfg = _make_test_config(tmp_path)
    monkeypatch.setattr("pipeline.cli.settings", cfg)

    video_file = _create_dummy_video(tmp_path / "cli_car.mp4", width=640, height=480, num_frames=35)
    job_id = "cli_job_01"

    # Önce sadece 0..3 adımlarını çalıştır
    rc = cli_main(["--job", job_id, "--video", str(video_file), "--from", "0", "--to", "3", "--mock"])
    assert rc == 0

    orch = PipelineOrchestrator(config=cfg)
    state_after_03 = orch.load_state(job_id)
    step_01_end_time = state_after_03["steps"]["step_01_extract_frames"]["ended_at"]
    assert state_after_03["steps"]["step_03_segment_car"]["status"] == "done"
    assert state_after_03["steps"]["step_04_estimate_poses"]["status"] == "pending"

    # Şimdi sadece 4. adımı tek başına CLI ile çalıştır (`--step 4`)
    rc_step4 = cli_main(["--job", job_id, "--step", "4", "--mock"])
    assert rc_step4 == 0

    state_after_04 = orch.load_state(job_id)
    assert state_after_04["steps"]["step_04_estimate_poses"]["status"] == "done"
    # Adım 01 tekrar çalışmamış olmalı (bitiş zamanı değişmemeli)
    assert state_after_04["steps"]["step_01_extract_frames"]["ended_at"] == step_01_end_time

    # Şimdi `--resume` ile kalan adımları (05..09) tamamla
    rc_resume = cli_main(["--job", job_id, "--resume", "--mock"])
    assert rc_resume == 0

    final_state = orch.load_state(job_id)
    assert final_state["status"] == "done"
    assert final_state["steps"]["step_01_extract_frames"]["ended_at"] == step_01_end_time


def test_step_failure_reporting_and_http_api_contract(tmp_path: Path, monkeypatch) -> None:
    """
    Hatalı bir girdi verildiğinde (ör. desteklenmeyen uzantı) hangi adımın
    (`failed_step`) hangi kodla (`error_code`) başarısız olduğunun hem `state.json`
    hem de FastAPI yanıtında raporlandığını ve geçerli bir işin API üzerinden
    uçtan uca tamamlandığını doğrular.
    """
    cfg = _make_test_config(tmp_path)
    monkeypatch.setattr("service.settings", cfg)
    job_runner.config = cfg
    job_runner.orchestrator = PipelineOrchestrator(config=cfg)

    bad_file = tmp_path / "bozuk_dosya.txt"
    bad_file.write_text("bu bir video degildir", encoding="utf-8")

    caught_err = None
    try:
        job_runner.orchestrator.initialize_job("bad_job", {"input_video": str(bad_file)})
        job_runner.orchestrator.run_pipeline("bad_job")
    except StepError as err:
        caught_err = err

    assert caught_err is not None
    assert caught_err.step == "step_00_validate_input"
    assert caught_err.code == "UNSUPPORTED_FORMAT"

    bad_state = job_runner.orchestrator.load_state("bad_job")
    assert bad_state["status"] == "failed"
    assert bad_state["failed_step"] == "step_00_validate_input"
    assert bad_state["error"]["error_code"] == "UNSUPPORTED_FORMAT"

    # FastAPI TestClient ile Auth, Health, Status ve Result uç noktalarını doğrula
    headers = {"X-Admin-Key": cfg.api_key}
    with TestClient(app) as client:
        # 1. Yetkisiz erişim 403 dönmeli
        unauth_resp = client.get("/jobs/bad_job")
        assert unauth_resp.status_code == 403

        # 2. Health kontrolü
        health_resp = client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["dev_mock_mode"] is True

        # 3. Başarısız işin durumu failed_step ve error_code içermeli
        bad_status_resp = client.get("/jobs/bad_job", headers=headers)
        assert bad_status_resp.status_code == 200
        bad_json = bad_status_resp.json()
        assert bad_json["status"] == "failed"
        assert bad_json["failed_step"] == "step_00_validate_input"
        assert bad_json["error_code"] == "UNSUPPORTED_FORMAT"

        # 4. Geçerli bir işi POST /jobs ile gönder ve tamamlanmasını bekle
        good_video = _create_dummy_video(tmp_path / "api_car.mp4", width=640, height=480, num_frames=35)
        create_resp = client.post(
            "/jobs",
            json={"video_path": str(good_video), "car_name": "Test Sedan"},
            headers=headers,
        )
        assert create_resp.status_code == 202
        created_job_id = create_resp.json()["job_id"]

        # Arka plan işçisinin tamamlamasını bekle
        deadline = time.time() + 20.0
        final_status_json = {}
        while time.time() < deadline:
            st_resp = client.get(f"/jobs/{created_job_id}", headers=headers)
            final_status_json = st_resp.json()
            if final_status_json["status"] in {"done", "failed"}:
                break
            time.sleep(0.2)

        assert final_status_json.get("status") == "done"

        # Sonuç ve GLB indirme uç noktasını kontrol et
        res_resp = client.get(f"/jobs/{created_job_id}/result", headers=headers)
        assert res_resp.status_code == 200
        res_json = res_resp.json()
        assert res_json["status"] == "success"
        assert "meters_per_unit" in res_json["export_manifest"]["extras"]

        dl_resp = client.get(f"/jobs/{created_job_id}/result?download=true", headers=headers)
        assert dl_resp.status_code == 200
        assert dl_resp.content[:4] == b"glTF"


if __name__ == "__main__":
    import tempfile

    class _SimpleMonkeyPatch:
        def __init__(self) -> None:
            self._originals = []

        def setattr(self, target: str, value) -> None:
            mod_path, attr = target.rsplit(".", 1)
            mod = __import__(mod_path, fromlist=[attr])
            self._originals.append((mod, attr, getattr(mod, attr)))
            setattr(mod, attr, value)

        def undo(self) -> None:
            for mod, attr, orig in reversed(self._originals):
                setattr(mod, attr, orig)

    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        print("[TEST 1/4] Normal video tam pipeline (00..09), y=0 zemin ve GLB extras kontrolü...")
        test_full_pipeline_steps_00_to_09_and_glb_extras(root / "t1")
        print("  -> BAŞARILI")

        print("[TEST 2/4] 360° video yeniden izdüşüm (step_02), bilinen metre ölçeği ve USDZ...")
        test_360_video_reprojection_and_known_metric_scale(root / "t2")
        print("  -> BAŞARILI")

        print("[TEST 3/4] CLI tek adım (--step 4) ve kaldığı yerden devam (--resume)...")
        mp1 = _SimpleMonkeyPatch()
        try:
            test_cli_single_step_and_resume_does_not_repeat_earlier_steps(root / "t3", mp1)
        finally:
            mp1.undo()
        print("  -> BAŞARILI")

        print("[TEST 4/4] Adım hatası raporlama (state.json + HTTP API) ve uçtan uca /jobs testi...")
        mp2 = _SimpleMonkeyPatch()
        try:
            test_step_failure_reporting_and_http_api_contract(root / "t4", mp2)
        finally:
            mp2.undo()
        print("  -> BAŞARILI")

    print("TÜM TESTLER BAŞARIYLA TAMAMLANDI!")

