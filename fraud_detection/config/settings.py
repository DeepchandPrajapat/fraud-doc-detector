"""Central configuration. Override any value with env vars prefixed FDD_."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDD_")

    # intake
    allowed_extensions: tuple[str, ...] = (".pdf", ".jpg", ".jpeg", ".png")
    max_file_mb: float = 15.0
    max_pdf_pages: int = 10
    pdf_render_dpi: int = 300
    min_short_side_px: int = 600
    min_blur_variance: float = 60.0      # Laplacian variance; tune on real data
    max_glare_ratio: float = 0.08
    min_brightness: float = 40.0
    max_brightness: float = 235.0

    # OCR
    ocr_backend: str = "easyocr"         # easyocr | tesseract
    ocr_languages: tuple[str, ...] = ("en",)
    ocr_gpu: bool = True

    # classifier
    classifier_min_confidence: float = 0.35

    # paths
    reference_dir: Path = ROOT / "data" / "reference_lists"
    uidai_cert_path: Path = ROOT / "data" / "reference_lists" / "uidai_offline_publickey.cer"


settings = Settings()
