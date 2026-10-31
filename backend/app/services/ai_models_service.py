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
        "provider": "Not configured",
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
        "provider": "Not configured",
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
                existing.limitations = m_data["limitations"]
                existing.metadata_info = m_data.get("metadata_info")
        # Availability reflects reality: weights present AND loadable by onnxruntime.
        for key, det in (("LEVIR-CD-Building-v2", None), ("Rooftop-Solar-SmallObj-v1", None)):
            entry = db.query(AIModelRegistry).filter(AIModelRegistry.model_key == key).first()
            if not entry:
                continue
            runner = _levir_runner if key.startswith("LEVIR") else _rooftop_runner
            ok, why = runner.check()
            entry.is_available = ok
            entry.provider = ("ONNX Runtime: " + Path(runner.path).name) if ok else f"Not available: {why}"
        db.commit()
    except Exception as e:
        logger.error(f"Error initializing AI model registry: {e}")
        db.rollback()
    finally:
        db.close()


# ----------------------------------------------------------------------------- ONNX runners
class _OnnxRunner:
    """Lazy ONNX Runtime session. Reports unavailable (never fakes) if weights/runtime are missing."""

    def __init__(self, path_getter, default_name):
        self._path_getter = path_getter
        self._default_name = default_name
        self._session = None
        self._loaded_path = None

    @property
    def path(self) -> str:
        configured = self._path_getter()
        if configured:
            return configured
        return str(settings.MODELS_DIR / self._default_name)

    def check(self):
        p = Path(self.path)
        if not p.is_file():
            return False, f"weights file not found at {p} (set the model path env var or place the file there)"
        try:
            self.session()
        except Exception as exc:  # noqa: BLE001
            return False, f"could not load ONNX model: {exc}"
        return True, "ok"

    def session(self):
        path = self.path
        if self._session is None or self._loaded_path != path:
            import onnxruntime as ort  # local import: optional dependency
            self._session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
            self._loaded_path = path
        return self._session

    def reset(self):
        self._session = None


_levir_runner = _OnnxRunner(lambda: settings.LEVIR_CD_MODEL_PATH, "levir_cd.onnx")
_rooftop_runner = _OnnxRunner(lambda: settings.ROOFTOP_MODEL_PATH, "rooftop_yolo.onnx")


def _unavailable(model_key, why, extra=None):
    out = {"status": "UNAVAILABLE", "model_key": model_key, "model_version": None, "confidence": None,
           "limitations": f"Model not operational: {why}. No prediction was generated."}
    out.update(extra or {})
    return out


def _record(model_key, entity_type, entity_id, result, features, raw):
    db = SessionLocal()
    try:
        model = db.query(AIModelRegistry).filter(AIModelRegistry.model_key == model_key).first()
        if model and result.get("status") == "COMPLETED":
            db.add(ModelInference(
                model_id=model.id, entity_type=entity_type, entity_id=entity_id,
                confidence=result.get("confidence"), detected_features=features,
                result_summary=result.get("summary", ""), limitations_disclaimer=result.get("limitations"),
                raw_output=raw, is_simulated=False))
            db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not record inference: %s", exc)
        db.rollback()
    finally:
        db.close()


class LEVIRCDBuildingDetector:
    """
    Bi-temporal building change detection with a trained ONNX change-detection network
    (e.g. a LEVIR-CD-trained FC-Siam / BIT / ChangeFormer export).

    Accepted ONNX signatures (auto-detected):
      * two inputs  (A, B), each float32 [1,3,H,W]
      * one input   float32 [1,6,H,W] = concat(A, B)
    Output: change logits/probabilities [1,1,H,W] (sigmoid) or [1,2,H,W] (softmax, class 1 = change).
    Inputs are RGB scaled to 0..1 then normalised with mean/std 0.5 (the LEVIR-CD convention).
    """

    def __init__(self):
        self.model_key = "LEVIR-CD-Building-v2"

    def detect_building_changes(self, baseline_img_path: str, target_img_path: str, property_id: int) -> Dict[str, Any]:
        ok, why = _levir_runner.check()
        if not ok:
            return _unavailable(self.model_key, why, {"change_detected": None, "detected_features": []})
        if not os.path.exists(baseline_img_path) or not os.path.exists(target_img_path):
            return {"status": "FAILED", "model_key": self.model_key, "error": "Input imagery files are missing.",
                    "limitations": "Missing imagery source files."}
        try:
            a, b = cv2.imread(baseline_img_path), cv2.imread(target_img_path)
            if a is None or b is None:
                return {"status": "FAILED", "model_key": self.model_key, "error": "Could not decode imagery."}
            sess = _levir_runner.session()
            inputs = sess.get_inputs()
            size = 256
            shp = inputs[0].shape
            if len(shp) == 4 and isinstance(shp[2], int) and isinstance(shp[3], int):
                size = int(shp[2])

            def prep(img):
                img = cv2.cvtColor(cv2.resize(img, (size, size), interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2RGB)
                return ((img.astype(np.float32) / 255.0 - 0.5) / 0.5).transpose(2, 0, 1)[None]

            pa, pb = prep(a), prep(b)
            if len(inputs) >= 2:
                out = sess.run(None, {inputs[0].name: pa, inputs[1].name: pb})[0]
            else:
                out = sess.run(None, {inputs[0].name: np.concatenate([pa, pb], axis=1)})[0]
            out = np.asarray(out, dtype=np.float32)
            if out.shape[1] == 2:
                e = np.exp(out - out.max(axis=1, keepdims=True))
                prob = (e / e.sum(axis=1, keepdims=True))[0, 1]
            else:
                x = out[0, 0]
                prob = 1.0 / (1.0 + np.exp(-x)) if (x.min() < 0 or x.max() > 1) else x
            thr = 0.5
            mask = (prob >= thr).astype(np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_area = 0.002 * size * size
            feats = []
            for c in contours:
                area = cv2.contourArea(c)
                if area < min_area:
                    continue
                x, y, w, h = cv2.boundingRect(c)
                region = prob[y:y + h, x:x + w][mask[y:y + h, x:x + w] > 0]
                feats.append({"box": [int(y), int(x), int(y + h), int(x + w)], "image_size": size,
                              "area_pixels": int(area), "confidence": round(float(region.mean()), 3)})
            pct = float(mask.mean() * 100.0)
            conf = round(float(np.mean([f["confidence"] for f in feats])), 3) if feats else 0.0
            result = {
                "status": "COMPLETED", "model_key": self.model_key,
                "model_name": "Trained building change-detection network (ONNX)",
                "model_version": Path(_levir_runner.path).stem,
                "change_detected": bool(feats), "change_area_percentage": round(pct, 2),
                "confidence": conf, "detected_features": feats, "structural_modifications_count": len(feats),
                "summary": (f"Model flagged {len(feats)} changed region(s) covering {pct:.1f}% of the scene "
                            f"(mean confidence {conf:.2f})." if feats else
                            "Model found no changed building regions. This does not prove that no modification occurred."),
                "limitations": ("LEVIR-CD style networks are trained on <=1 m imagery. On 10 m Sentinel-2 tiles only "
                                "large footprint changes are resolvable. Output is advisory and needs human review."),
            }
            _record(self.model_key, "Modification", f"PROP-{property_id}", result, feats,
                    {"change_area_percentage": result["change_area_percentage"], "threshold": thr})
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("Building change inference failed")
            return {"status": "SYSTEM_ERROR", "model_key": self.model_key, "error": str(exc),
                    "limitations": "Inference interrupted by runtime exception."}


class RooftopSmallObjectDetector:
    """
    Rooftop object detection with a trained YOLO-family ONNX model (Ultralytics export,
    output [1, 4+num_classes, N] or [1, N, 4+num_classes]). Class names come from ROOFTOP_MODEL_CLASSES.
    """

    def __init__(self):
        self.model_key = "Rooftop-Solar-SmallObj-v1"

    def detect_rooftop_objects(self, image_path: str, property_id: int) -> Dict[str, Any]:
        ok, why = _rooftop_runner.check()
        if not ok:
            return _unavailable(self.model_key, why, {"solar_detected": None, "objects_count": None, "objects": []})
        if not os.path.exists(image_path):
            return {"status": "FAILED", "model_key": self.model_key, "error": f"Image file not found: {image_path}"}
        try:
            img = cv2.imread(image_path)
            if img is None:
                return {"status": "FAILED", "model_key": self.model_key, "error": "Failed to decode image"}
            sess = _rooftop_runner.session()
            inp = sess.get_inputs()[0]
            size = int(inp.shape[2]) if len(inp.shape) == 4 and isinstance(inp.shape[2], int) else 640
            h0, w0 = img.shape[:2]
            blob = cv2.cvtColor(cv2.resize(img, (size, size)), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            out = np.asarray(sess.run(None, {inp.name: blob.transpose(2, 0, 1)[None]})[0])[0]
            classes = [c.strip() for c in settings.ROOFTOP_MODEL_CLASSES.split(",") if c.strip()]
            if out.shape[0] < out.shape[1]:
                out = out.T  # -> [N, 4+nc]
            thr = 0.60
            boxes, scores, cls_ids = [], [], []
            for row in out:
                cs = row[4:]
                cid = int(np.argmax(cs))
                sc = float(cs[cid])
                if sc < thr:
                    continue
                cx, cy, w, h = row[:4]
                boxes.append([int((cx - w / 2) * w0 / size), int((cy - h / 2) * h0 / size),
                              int(w * w0 / size), int(h * h0 / size)])
                scores.append(sc)
                cls_ids.append(cid)
            keep = cv2.dnn.NMSBoxes(boxes, scores, thr, 0.45) if boxes else []
            objs = []
            for i in np.array(keep).flatten():
                x, y, w, h = boxes[i]
                label = classes[cls_ids[i]] if cls_ids[i] < len(classes) else f"class_{cls_ids[i]}"
                objs.append({"label": label, "confidence": round(scores[i], 3), "box": [y, x, y + h, x + w]})
            mean_conf = round(float(np.mean([o["confidence"] for o in objs])), 3) if objs else 0.0
            result = {
                "status": "COMPLETED", "model_key": self.model_key,
                "model_name": "Rooftop object detector (ONNX)", "model_version": Path(_rooftop_runner.path).stem,
                "solar_detected": any("solar" in o["label"].lower() or "pv" in o["label"].lower() for o in objs),
                "objects_count": len(objs), "objects": objs, "confidence": mean_conf,
                "summary": (f"Detected {len(objs)} rooftop object(s) with mean confidence {mean_conf:.2f}."
                            if objs else "No rooftop objects detected above the confidence threshold."),
                "limitations": ("Detection requires imagery fine enough to resolve rooftop equipment (<=0.5 m). "
                                "Sentinel-2 (10 m) is not suitable. Corroborate with permits/invoices."),
            }
            _record(self.model_key, "RooftopFeature", f"PROP-{property_id}", result, objs,
                    {"objects_count": len(objs), "threshold": thr})
            return result
        except Exception as exc:  # noqa: BLE001
            logger.exception("Rooftop inference failed")
            return {"status": "SYSTEM_ERROR", "model_key": self.model_key, "error": str(exc),
                    "limitations": "Inference interrupted by runtime exception."}


levir_cd_detector = LEVIRCDBuildingDetector()
rooftop_object_detector = RooftopSmallObjectDetector()
