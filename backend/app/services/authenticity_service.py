import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from app.config import settings
from app.services.deepfake_detector import deepfake_detector

logger = logging.getLogger(__name__)

class AuthenticityService:
    def __init__(self):
        self.api_url = settings.AUTHENTICITY_API_URL
        self.api_key = settings.AUTHENTICITY_API_KEY
        self.demo_mode = settings.DEMO_MODE

    def analyze_evidence_image(self, file_path: str, evidence_id: int = 0) -> Dict[str, Any]:
        """
        Run Deepfake & Tampering Forensics on an uploaded evidence photo:
        1. Discrete Cosine Transform (DCT) & 2D FFT spectral diffusion analysis (detecting latent diffusion lattice patterns).
        2. Error Level Analysis (ELA) for localized recompression discrepancies.
        3. Noise print & PRNU gradient variance.
        4. Camera EXIF hardware provenance vs synthetic canvas signatures.
        5. Visual forensic artifact heatmap generation.
        """
        if not os.path.exists(file_path):
            return {
                "provider": "Deepfake Forensics Engine",
                "model_name": "Spectral-ELA-v2",
                "result": "Analysis unavailable",
                "score": None,
                "explanation": "Image file could not be accessed on server filesystem.",
                "is_demo": False
            }

        # Run Deepfake & Tampering Forensic Pipeline
        try:
            forensics = deepfake_detector.analyze(file_path, evidence_id=evidence_id)
            return {
                "provider": "PropertyWatch Spectral-ELA Deepfake Forensics Engine",
                "model_name": "Spectral-Diffusion-Artifact-Detector-v2",
                "result": forensics["verdict"],
                "score": forensics["deepfake_probability"], # 0.0 to 1.0 synthetic probability
                "explanation": forensics["explanation"],
                "raw_response": forensics,
                "is_demo": False
            }
        except Exception as e:
            logger.error(f"Deepfake detector analysis failed: {e}")
            return {
                "provider": "PropertyWatch Deepfake Forensics",
                "model_name": "Spectral-ELA-v2",
                "result": "Inconclusive",
                "score": 0.50,
                "explanation": f"Automated deepfake forensics encountered processing error: {str(e)}",
                "is_demo": False,
                "raw_response": {}
            }

authenticity_service = AuthenticityService()
