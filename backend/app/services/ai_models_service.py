import os
import uuid
import datetime
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import cv2

from app.config import settings
from app.models import AIModelRegistry, ModelInference
from app.database import SessionLocal

logger = logging.getLogger(__name__)

# Register default models in registry if not present
DEFAULT_MODELS = [
    {
        "model_key": "LEVIR-CD-Building-v2",
        "name": "LEVIR-CD Dual-Temporal Building Change Detector",
        "version": "2.1.0",
        "task": "Building Change Detection",
        "provider": "Not configured (no trained model weights supplied)",
        "is_available": False,
        "confidence_threshold": 0.65,
        "limitations": (
            "Optimized for optical remote sensing imagery with GSD <= 1.0m. "
            "At 10m Copernicus Sentinel-2 resolution, subtle roofline adjustments and interior additions "
            "cannot be resolved. An absence of detectable change does NOT constitute proof that no modification occurred. "
            "Never treat model predictions as conclusive proof of unauthorized construction."
        ),
        "metadata_info": {
            "dataset": "LEVIR-CD (benchmark dataset; no project-trained weights configured)",
            "supported_classes": ["Building Expansion", "Floor Addition", "New Outbuilding", "Footprint Demolition"],
            "input_resolution": "800x800 bitemporal"
        }
    },
    {
        "model_key": "Rooftop-Solar-SmallObj-v1",
        "name": "Rooftop Solar PV & Small Object Detector",
        "version": "1.3.0",
        "task": "Rooftop Small-Object Detection",
        "provider": "Not configured (no trained small-object weights supplied)",
        "is_available": False,
        "confidence_threshold": 0.60,
        "limitations": (
            "Detects recurring high-contrast rectangular silicon photovoltaic arrays and rooftop structures. "
            "Shadows from chimneys, dark shingles, and dormers may cause false positives under low sun angles. "
            "Independent permitting and electrical contractor evidence must corroborate all detections."
        ),
        "metadata_info": {
            "supported_classes": ["Solar Photovoltaic Array", "Rooftop HVAC Unit", "Skylight Array"],
            "min_object_size_px": 15
        }
    },
    {
        "model_key": "ELA-Forensic-v1",
        "name": "Error Level Analysis & Compression Forensic Engine",
        "version": "1.0.0",
        "task": "Image Forensics",
        "provider": "Pillow / OpenCV ELA",
        "is_available": True,
        "confidence_threshold": 0.70,
        "limitations": (
            "Evaluates JPEG compression grid discrepancies. Multiple saves or social media re-compression "
            "can alter error signatures. Forensic scores provide corroborating evidence, not absolute proof of fraud."
        )
    },
    {
        "model_key": "Spectral-Diffusion-v1",
        "name": "2D-FFT Spectral Diffusion Artifact Detector",
        "version": "1.2.0",
        "task": "Image Forensics",
        "provider": "SciPy 2D Fast Fourier Transform",
        "is_available": True,
        "confidence_threshold": 0.75,
        "limitations": (
            "Identifies high-frequency periodic lattice artifacts characteristic of generative diffusion decoders. "
            "Heavily compressed or downscaled images may attenuate high-frequency signals."
        )
    }
]

def init_ai_model_registry():
    """Ensure baseline AI models are catalogued in the database registry."""
    db = SessionLocal()
    try:
        for m_data in DEFAULT_MODELS:
            existing = db.query(AIModelRegistry).filter(AIModelRegistry.model_key == m_data["model_key"]).first()
            if not existing:
                model_entry = AIModelRegistry(
                    model_key=m_data["model_key"],
                    name=m_data["name"],
                    version=m_data["version"],
                    task=m_data["task"],
                    provider=m_data["provider"],
                    is_available=m_data["is_available"],
                    confidence_threshold=m_data["confidence_threshold"],
                    limitations=m_data["limitations"],
                    metadata_info=m_data.get("metadata_info")
                )
                db.add(model_entry)
            elif m_data["model_key"] in {"LEVIR-CD-Building-v2", "Rooftop-Solar-SmallObj-v1"}:
                existing.is_available = False
                existing.provider = m_data["provider"]
                existing.limitations = m_data["limitations"]
                existing.metadata_info = m_data.get("metadata_info")
        db.commit()
    except Exception as e:
        logger.error(f"Error initializing AI model registry: {e}")
        db.rollback()
    finally:
        db.close()


class LEVIRCDBuildingDetector:
    """
    Building-change detection service informed by the LEVIR-CD benchmark.
    Performs bitemporal structural feature comparison to detect:
    - Building footprint expansions (horizontal extensions)
    - Additional floors / structural height changes
    - Outbuildings and new detached structures
    """

    def __init__(self):
        self.model_key = "LEVIR-CD-Building-v2"

    def detect_building_changes(
        self,
        baseline_img_path: str,
        target_img_path: str,
        property_id: int
    ) -> Dict[str, Any]:
        """
        Execute dual-temporal building change inference.
        Returns structured detection metrics, bounding boxes, confidence, and audit metadata.
        """
        return {
            "status": "UNAVAILABLE",
            "model_key": self.model_key,
            "model_version": None,
            "change_detected": None,
            "confidence": None,
            "detected_features": [],
            "limitations": "No trained LEVIR-CD model weights are configured. OpenCV image differencing remains available as a non-model visual comparison."
        }

        if not os.path.exists(baseline_img_path) or not os.path.exists(target_img_path):
            return {
                "status": "FAILED",
                "error": "One or both input imagery assets are unavailable.",
                "change_detected": False,
                "confidence": 0.0,
                "limitations": "Missing imagery source files."
            }

        try:
            # Read images
            im_base = cv2.imread(baseline_img_path)
            im_target = cv2.imread(target_img_path)

            if im_base is None or im_target is None:
                return {
                    "status": "FAILED",
                    "error": "Failed to decode imagery files.",
                    "change_detected": False,
                    "confidence": 0.0
                }

            # Standardize sizes (800x800)
            target_size = (800, 800)
            im_base_res = cv2.resize(im_base, target_size)
            im_target_res = cv2.resize(im_target, target_size)

            # Convert to LAB color space for robust luminance separation
            lab1 = cv2.cvtColor(im_base_res, cv2.COLOR_BGR2LAB)
            lab2 = cv2.cvtColor(im_target_res, cv2.COLOR_BGR2LAB)

            # Luminance & structural gradient diff
            diff_l = cv2.absdiff(lab1[:, :, 0], lab2[:, :, 0])
            diff_a = cv2.absdiff(lab1[:, :, 1], lab2[:, :, 1])
            diff_b = cv2.absdiff(lab1[:, :, 2], lab2[:, :, 2])
            combined_diff = cv2.addWeighted(diff_l, 0.6, cv2.addWeighted(diff_a, 0.5, diff_b, 0.5, 0), 0.4, 0)

            # Morphological structural closing to merge building components
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
            closed = cv2.morphologyEx(combined_diff, cv2.MORPH_CLOSE, kernel)
            _, thresh = cv2.threshold(closed, 40, 255, cv2.THRESH_BINARY)

            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            detected_boxes = []
            total_change_area = 0

            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > 1200: # Filter small noise
                    x, y, w, h = cv2.boundingRect(cnt)
                    aspect_ratio = float(w) / max(1, h)
                    # Classify suspected modification category
                    category = "Building Footprint Extension"
                    if y > 250 and y < 500 and (x > 250 and x < 550):
                        category = "Potential Roof Structure / Floor Addition"
                    elif y < 220:
                        category = "Backyard Outbuilding / Structure"

                    conf = float(np.clip(0.65 + (min(area, 20000) / 20000.0) * 0.28, 0.65, 0.94))
                    detected_boxes.append({
                        "box": [int(y), int(x), int(y + h), int(x + w)],
                        "category": category,
                        "area_pixels": int(area),
                        "confidence": round(conf, 3),
                        "aspect_ratio": round(aspect_ratio, 2)
                    })
                    total_change_area += area

            total_pixels = target_size[0] * target_size[1]
            change_pct = (total_change_area / total_pixels) * 100.0
            change_detected = len(detected_boxes) > 0

            overall_conf = round(float(np.mean([b["confidence"] for b in detected_boxes])), 3) if detected_boxes else 0.0

            result = {
                "status": "COMPLETED",
                "model_key": self.model_key,
                "model_name": "LEVIR-CD Dual-Temporal Building Change Detector",
                "model_version": "2.1.0",
                "change_detected": change_detected,
                "change_area_percentage": round(change_pct, 2),
                "confidence": overall_conf,
                "detected_features": detected_boxes,
                "structural_modifications_count": len(detected_boxes),
                "summary": (
                    f"LEVIR-CD detected {len(detected_boxes)} structural building variance sector(s) "
                    f"covering {change_pct:.1f}% of property footprint with mean confidence {overall_conf:.2f}."
                    if change_detected else
                    "LEVIR-CD analysis detected no prominent structural footprint variances between observation dates. "
                    "Note: Absence of detectable optical variance does not prove zero modification."
                ),
                "limitations": (
                    "LEVIR-CD architecture trained on bitemporal optical sets. Sensor zenith angle, seasonal foliage, "
                    "and ground sampling distance influence boundary delineations. Findings are advisory only."
                )
            }

            # Record inference in database
            self._record_inference(property_id, result)
            return result

        except Exception as e:
            logger.error(f"Error executing LEVIR-CD building change detection: {e}")
            return {
                "status": "SYSTEM_ERROR",
                "error": str(e),
                "change_detected": False,
                "confidence": 0.0,
                "limitations": "Inference interrupted by runtime exception."
            }

    def _record_inference(self, property_id: int, result: Dict[str, Any]):
        db = SessionLocal()
        try:
            model = db.query(AIModelRegistry).filter(AIModelRegistry.model_key == self.model_key).first()
            if model and result.get("status") == "COMPLETED":
                inf = ModelInference(
                    model_id=model.id,
                    entity_type="Modification",
                    entity_id=f"PROP-{property_id}",
                    confidence=result.get("confidence"),
                    detected_features=result.get("detected_features"),
                    result_summary=result.get("summary", ""),
                    limitations_disclaimer=result.get("limitations"),
                    raw_output={"change_area_percentage": result.get("change_area_percentage")},
                    is_simulated=False
                )
                db.add(inf)
                db.commit()
        except Exception as e:
            logger.warning(f"Could not record inference log: {e}")
            db.rollback()
        finally:
            db.close()


class RooftopSmallObjectDetector:
    """
    Dedicated small-object detector for rooftop infrastructure:
    - Solar photovoltaic (PV) panel arrays
    - Rooftop HVAC / mechanical equipment
    - Skylights and roof deck structures
    """

    def __init__(self):
        self.model_key = "Rooftop-Solar-SmallObj-v1"

    def detect_rooftop_objects(
        self,
        image_path: str,
        property_id: int
    ) -> Dict[str, Any]:
        """
        Execute small-object detection on property rooftop.
        Returns detected bounding boxes, object classification, confidence, and limitations.
        """
        return {
            "status": "UNAVAILABLE",
            "model_key": self.model_key,
            "model_version": None,
            "solar_detected": None,
            "objects_count": None,
            "objects": [],
            "confidence": None,
            "limitations": "No trained rooftop small-object model weights are configured; no rooftop-object predictions were generated."
        }

        if not os.path.exists(image_path):
            return {
                "status": "FAILED",
                "error": f"Image file not found: {image_path}",
                "objects_detected": [],
                "confidence": 0.0
            }

        try:
            img = cv2.imread(image_path)
            if img is None:
                return {"status": "FAILED", "error": "Failed to decode image"}

            h, w, _ = img.shape
            # Focus on central roof zone (approx 20% to 80% box)
            roof_roi = img[int(h * 0.2):int(h * 0.75), int(w * 0.25):int(w * 0.75)]
            gray = cv2.cvtColor(roof_roi, cv2.COLOR_BGR2GRAY)

            # High-pass filter for regular rectangular panel grids
            grad_x = cv2.Sobel(gray, cv2.CV_16S, 1, 0, ksize=3)
            grad_y = cv2.Sobel(gray, cv2.CV_16S, 0, 1, ksize=3)
            abs_grad = cv2.addWeighted(cv2.convertScaleAbs(grad_x), 0.5, cv2.convertScaleAbs(grad_y), 0.5, 0)

            # Detect low-luminance high-contrast silicon cells
            _, dark_mask = cv2.threshold(gray, 70, 255, cv2.THRESH_BINARY_INV)
            combined = cv2.bitwise_and(abs_grad, dark_mask)

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 5))
            closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            detected_objects = []
            roi_y_offset = int(h * 0.2)
            roi_x_offset = int(w * 0.25)

            for cnt in contours:
                area = cv2.contourArea(cnt)
                # Panels typically occupy 400 - 15000 px in 800x800 image
                if 350 < area < 25000:
                    rx, ry, rw, rh = cv2.boundingRect(cnt)
                    aspect = float(rw) / max(1, rh)
                    # Panels have distinctive aspect ratios and grid alignments
                    if 0.5 < aspect < 3.5:
                        conf = float(np.clip(0.68 + (min(area, 8000) / 8000.0) * 0.24, 0.68, 0.92))
                        detected_objects.append({
                            "label": "Rooftop Solar PV Array",
                            "confidence": round(conf, 3),
                            "box": [
                                roi_y_offset + ry,
                                roi_x_offset + rx,
                                roi_y_offset + ry + rh,
                                roi_x_offset + rx + rw
                            ],
                            "estimated_area_sqm": round(area * 0.05, 1),
                            "aspect_ratio": round(aspect, 2)
                        })

            has_solar = len(detected_objects) > 0
            mean_conf = round(float(np.mean([o["confidence"] for o in detected_objects])), 3) if detected_objects else 0.0

            result = {
                "status": "COMPLETED",
                "model_key": self.model_key,
                "model_name": "Rooftop Solar PV & Small Object Detector",
                "model_version": "1.3.0",
                "solar_detected": has_solar,
                "objects_count": len(detected_objects),
                "objects": detected_objects,
                "confidence": mean_conf,
                "summary": (
                    f"Identified {len(detected_objects)} potential rooftop solar array cluster(s) "
                    f"with confidence {mean_conf:.2f}."
                    if has_solar else
                    "No prominent rooftop photovoltaic arrays or small mechanical clusters detected."
                ),
                "limitations": (
                    "Small-object detection requires high visual contrast. Shadowing from adjacent trees or "
                    "skylight glare may influence detection confidence. Requires corroborating electrical permit."
                )
            }

            self._record_inference(property_id, result)
            return result

        except Exception as e:
            logger.error(f"Error executing rooftop small-object detection: {e}")
            return {
                "status": "SYSTEM_ERROR",
                "error": str(e),
                "solar_detected": False,
                "confidence": 0.0,
                "limitations": "Inference interrupted by runtime exception."
            }

    def _record_inference(self, property_id: int, result: Dict[str, Any]):
        db = SessionLocal()
        try:
            model = db.query(AIModelRegistry).filter(AIModelRegistry.model_key == self.model_key).first()
            if model and result.get("status") == "COMPLETED":
                inf = ModelInference(
                    model_id=model.id,
                    entity_type="RooftopFeature",
                    entity_id=f"PROP-{property_id}",
                    confidence=result.get("confidence"),
                    detected_features=result.get("objects"),
                    result_summary=result.get("summary", ""),
                    limitations_disclaimer=result.get("limitations"),
                    raw_output={"objects_count": result.get("objects_count")},
                    is_simulated=False
                )
                db.add(inf)
                db.commit()
        except Exception as e:
            logger.warning(f"Could not record rooftop inference log: {e}")
            db.rollback()
        finally:
            db.close()

# Singleton instances
levir_cd_detector = LEVIRCDBuildingDetector()
rooftop_object_detector = RooftopSmallObjectDetector()
