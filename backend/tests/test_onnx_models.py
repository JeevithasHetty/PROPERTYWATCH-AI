"""Integration test with the real ONNX weights. Skipped automatically when the weights are not in <project>/models."""
import numpy as np
import pytest
import cv2
from pathlib import Path

from app.config import settings

# conftest points MODELS_DIR at a temp dir, so look at the real <project>/models folder directly
MODELS = Path(__file__).resolve().parents[2] / "models"
pytestmark = pytest.mark.skipif(
    not ((MODELS / "levir_cd.onnx").is_file() and (MODELS / "rooftop_yolo.onnx").is_file()),
    reason="ONNX weights not present in models/",
)


@pytest.fixture(autouse=True)
def real_weights(monkeypatch):
    from app.services import ai_models_service as m
    monkeypatch.setattr(settings, "LEVIR_CD_MODEL_PATH", str(MODELS / "levir_cd.onnx"))
    monkeypatch.setattr(settings, "ROOFTOP_MODEL_PATH", str(MODELS / "rooftop_yolo.onnx"))
    m._levir_runner.reset(); m._rooftop_runner.reset()
    yield
    m._levir_runner.reset(); m._rooftop_runner.reset()


@pytest.fixture()
def imgs(tmp_path):
    rng = np.random.default_rng(0)
    base = (rng.random((300, 500, 3)) * 255).astype(np.uint8)  # non-square on purpose (letterbox path)
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    cv2.imwrite(str(a), base)
    changed = base.copy()
    changed[100:220, 200:380] = 255
    cv2.imwrite(str(b), changed)
    return a, b


def test_change_model_runs_and_identical_images_show_no_change(imgs):
    from app.services.ai_models_service import levir_cd_detector
    a, b = imgs
    same = levir_cd_detector.detect_building_changes(str(a), str(a), 1)
    assert same["status"] == "COMPLETED"
    assert same["change_detected"] is False
    diff = levir_cd_detector.detect_building_changes(str(a), str(b), 1)
    assert diff["status"] == "COMPLETED" and 0.0 <= diff["change_area_percentage"] <= 100.0


def test_rooftop_model_runs_with_correct_labels_and_box_range(imgs, monkeypatch):
    from app.services.ai_models_service import rooftop_object_detector
    monkeypatch.setattr(settings, "ROOFTOP_CONF_THRESHOLD", 0.01)  # force detections to exercise box mapping
    monkeypatch.setattr(settings, "ROOFTOP_MODEL_CLASSES", "solar_panel,pool")
    a, _ = imgs
    res = rooftop_object_detector.detect_rooftop_objects(str(a), 1)
    assert res["status"] == "COMPLETED"
    for o in res["objects"]:
        assert o["label"] in ("solar_panel", "pool")
        y1, x1, y2, x2 = o["box"]
        assert 0 <= x1 <= x2 <= 500 and 0 <= y1 <= y2 <= 300
