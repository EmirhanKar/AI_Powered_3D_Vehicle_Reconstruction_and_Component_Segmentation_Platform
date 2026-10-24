"""
ModifAI 3D Servisi — Standartlaştırılmış Hata Sınıfları.

Her adım (step) beklenmeyen bir durumla veya kalite kapısı (quality gate)
ihlaliyle karşılaştığında çıplak `Exception` yerine `StepError` fırlatır.
Böylece hem `state.json` dosyasında hem de Backend/API yanıtlarında hangi
adımın (`step`), hangi makine koduyla (`code`), neden (`message`) başarısız
olduğu ve kullanıcının videoyu yeniden çekerken neye dikkat etmesi gerektiği
(`hint`) net olarak raporlanır.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class StepError(Exception):
    """
    Pipeline adımlarında oluşan tüm öngörülen veya sarmalanan hataları temsil eder.

    Özellikler:
        step: Hatayı üreten adımın tekil adı (ör. 'step_04_estimate_poses').
        code: Makine tarafından okunabilir sabit hata kodu (ör. 'POSE_REGISTRATION_LOW').
        message: Geliştirici ve kullanıcı için Türkçe hata açıklaması.
        hint: Kullanıcının sorunu çözmek için yapabileceği eylem önerisi (Türkçe).
        details: Tanılama (debugging) için ek metrikler, eşik değerleri veya stderr çıktısı.
    """

    def __init__(
        self,
        step: str,
        code: str,
        message: str,
        hint: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(f"[{step}] {code}: {message}")
        self.step: str = step
        self.code: str = code
        self.message: str = message
        self.hint: str = (
            hint
            or "Lütfen aracın etrafında sabit hızla, iyi aydınlatılmış bir ortamda tam tur yürüyerek tekrar video çekin."
        )
        self.details: Dict[str, Any] = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Hata bilgisini JSON serileştirmeye ve API yanıtlarına uygun sözlüğe çevirir."""
        return {
            "failed_step": self.step,
            "error_code": self.code,
            "detail": self.message,
            "message": self.message,
            "hint": self.hint,
            "details": self.details,
        }
