"""
ModifAI 3D Servisi — Komut Satırı Arayüzü (CLI).

Bu modül, mevcut bir iş klasörü (`jobs/<job_id>/`) üzerinde tek bir adımı veya
bir adım aralığını bağımsız olarak çalıştırmak ve hata ayıklamak için kullanılır.

Kullanım Örnekleri (`3Dservice/` dizini içinden):
    # Yeni bir iş başlatıp tüm adımları çalıştır:
    python -m pipeline.cli --job test_arac_01 --video ./ornek.mp4

    # Sadece 4. adımı (estimate_poses) tek başına yeniden çalıştır:
    python -m pipeline.cli --job test_arac_01 --step 4

    # 4. adımdan 6. adıma kadar (dahil) çalıştır:
    python -m pipeline.cli --job test_arac_01 --from 4 --to 6

    # Başarısız olmuş bir işi kaldığı adımdan devam ettir (öncekileri tekrarlama):
    python -m pipeline.cli --job test_arac_01 --resume
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Optional, Sequence

from config import settings
from pipeline.errors import StepError
from pipeline.orchestrator import PipelineOrchestrator


def build_parser() -> argparse.ArgumentParser:
    """CLI argüman ayrıştırıcısını oluşturur."""
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.cli",
        description="ModifAI 3D Servisi — Tekil Adım veya Aralık Çalıştırma Aracı",
    )
    parser.add_argument(
        "--job",
        required=True,
        help="Çalıştırılacak işin tekil kimliği (jobs/<job_id>/).",
    )
    parser.add_argument(
        "--video",
        type=str,
        default=None,
        help="Yeni bir iş başlatılıyorsa girdi video dosyasının yolu.",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=None,
        help="Yalnızca belirtilen sıra numaralı adımı çalıştır (0-9 arası, ör. --step 4).",
    )
    parser.add_argument(
        "--from",
        dest="from_step",
        type=int,
        default=None,
        help="Belirtilen adım numarasından (dahil) başlayarak çalıştır.",
    )
    parser.add_argument(
        "--to",
        dest="to_step",
        type=int,
        default=None,
        help="Belirtilen adım numarasına (dahil) kadar çalıştır.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Daha önce 'done' veya 'skipped' olan adımları atlayarak kaldığı yerden devam et.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Ortam değişkeninden bağımsız olarak DEV_MOCK_MODE=true ile çalıştır.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI ana giriş noktası. Başarıda 0, adım hatasında 2, argüman hatasında 1 döndürür."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Eğer --mock bayrağı verildiyse çalışma zamanı yapılandırmasını kopyalayıp mock modunu aç
    cfg = settings
    if args.mock and not cfg.dev_mock_mode:
        from dataclasses import replace

        cfg = replace(cfg, dev_mock_mode=True)

    orchestrator = PipelineOrchestrator(config=cfg)
    state_path = orchestrator.get_state_path(args.job)

    if args.video:
        video_path = Path(args.video).resolve()
        orchestrator.initialize_job(
            job_id=args.job,
            initial_artifacts={"input_video": str(video_path)},
            metadata={"source": "cli"},
        )
    elif not state_path.exists():
        print(
            f"[HATA] '{args.job}' işi için '{state_path}' bulunamadı. "
            "İlk çalıştırmada '--video <dosya_yolu>' parametresini belirtmelisiniz.",
            file=sys.stderr,
        )
        return 1

    from_step = args.from_step
    to_step = args.to_step
    if args.step is not None:
        from_step = args.step
        to_step = args.step

    try:
        final_state = orchestrator.run_pipeline(
            job_id=args.job,
            from_step=from_step,
            to_step=to_step,
            resume=args.resume,
        )
        print(
            json.dumps(
                {
                    "job_id": final_state["job_id"],
                    "status": final_state["status"],
                    "progress": final_state["progress"],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    except StepError as err:
        print(
            json.dumps(
                {
                    "status": "failed",
                    **err.to_dict(),
                },
                indent=2,
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
