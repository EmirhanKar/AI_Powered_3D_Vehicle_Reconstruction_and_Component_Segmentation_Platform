"""
ModifAI 3D Servisi — Güvenli Alt Süreç (Subprocess) Çalıştırıcısı.

FFmpeg, COLMAP ve Nerfstudio gibi harici CLI araçlarını çalıştırırken:
1. Sonsuz kilitlenmeleri önlemek için `timeout` uygulanır.
2. Standart çıktı (stdout) ve hata çıktısı (stderr) yakalanıp adım günlüğüne yazılır.
3. Süreç sıfırdan farklı bir çıkış koduyla (return code != 0) biterse veya
   zaman aşımına uğrarsa, son N satır `stderr` çıktısını da içeren bir `StepError`
   fırlatılır. Böylece COLMAP veya CUDA çökmeleri anında teşhis edilebilir.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import subprocess
from typing import Dict, List, Optional, Sequence, Union

from pipeline.errors import StepError


@dataclass
class CommandResult:
    """Tamamlanan bir alt sürecin çıktısını temsil eder."""

    command: List[str]
    returncode: int
    stdout: str
    stderr: str


def run_subprocess(
    command: Sequence[Union[str, Path]],
    step_name: str,
    error_code: str,
    error_message: str,
    hint: Optional[str] = None,
    timeout_seconds: int = 1800,
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    logger: Optional[logging.Logger] = None,
    stderr_tail_lines: int = 30,
) -> CommandResult:
    """
    Harici bir komutu çalıştırır, çıktısını kaydeder ve başarısızlıkta `StepError` üretir.

    Neden bu sarmalayıcı kullanılır?
    COLMAP veya FFmpeg hata verdiğinde genellikle asıl sebep `stderr` çıktısının
    son 15-30 satırındadır (ör. "CUDA out of memory" veya "No good initial image pair").
    Bu fonksiyon son `stderr_tail_lines` satırı otomatik olarak `StepError.details`
    içine gömer.
    """
    cmd_str_list = [str(part) for part in command]
    if logger:
        logger.info("Alt süreç başlatılıyor: %s", " ".join(cmd_str_list))

    try:
        completed = subprocess.run(
            cmd_str_list,
            cwd=str(cwd) if cwd else None,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise StepError(
            step=step_name,
            code=error_code,
            message=f"{error_message} (Çalıştırılabilir ikili dosya bulunamadı: '{cmd_str_list[0]}').",
            hint=hint or f"Sistemde '{cmd_str_list[0]}' aracının kurulu ve PATH üzerinde olduğundan emin olun.",
            details={"command": cmd_str_list, "exception": str(exc)},
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raw_stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        tail = "\n".join(raw_stderr.splitlines()[-stderr_tail_lines:])
        raise StepError(
            step=step_name,
            code=f"{error_code}_TIMEOUT",
            message=f"{error_message} ({timeout_seconds} saniye zaman aşımı aşıldı).",
            hint=hint or "Video süresini veya hedef kare sayısını azaltarak tekrar deneyin.",
            details={
                "command": cmd_str_list,
                "timeout_seconds": timeout_seconds,
                "stderr_tail": tail,
            },
        ) from exc

    if completed.stdout and logger:
        for line in completed.stdout.splitlines()[-20:]:
            logger.debug("[stdout] %s", line)

    if completed.returncode != 0:
        stderr_lines = (completed.stderr or "").splitlines()
        stdout_lines = (completed.stdout or "").splitlines()
        stderr_tail = "\n".join(stderr_lines[-stderr_tail_lines:])
        stdout_tail = "\n".join(stdout_lines[-stderr_tail_lines:])

        if logger:
            logger.error(
                "Alt süreç başarısız oldu (kod=%d): %s\nStderr Son Satırlar:\n%s",
                completed.returncode,
                " ".join(cmd_str_list),
                stderr_tail or stdout_tail,
            )

        raise StepError(
            step=step_name,
            code=error_code,
            message=f"{error_message} (Çıkış kodu: {completed.returncode}).",
            hint=hint,
            details={
                "command": cmd_str_list,
                "returncode": completed.returncode,
                "stderr_tail": stderr_tail,
                "stdout_tail": stdout_tail,
            },
        )

    return CommandResult(
        command=cmd_str_list,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
