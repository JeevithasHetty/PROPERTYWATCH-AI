import cv2
import numpy as np
from pathlib import Path
from app.config import settings
from app.services.cv_service import run_image_comparison_pipeline


def _scene(tmp_path):
    rng = np.random.default_rng(1)
    base = cv2.GaussianBlur((rng.random((400, 400, 3)) * 120 + 60).astype(np.uint8), (0, 0), 3)
    after = base.copy()
    cv2.rectangle(after, (240, 120), (340, 220), (255, 255, 255), -1)  # a new bright "structure"
    sharp_a, soft_b = tmp_path / "a.png", tmp_path / "b.png"
    cv2.imwrite(str(sharp_a), cv2.resize(base, (1600, 1600), interpolation=cv2.INTER_NEAREST))  # sharp, big
    cv2.imwrite(str(soft_b), cv2.GaussianBlur(after, (0, 0), 4))                              # soft, small
    return sharp_a, soft_b


def test_pipeline_circles_the_change_and_matches_resolution(tmp_path):
    a, b = _scene(tmp_path)
    res = run_image_comparison_pipeline(str(a), str(b), 1)
    assert res["contours_count"] >= 1
    assert "sharpness_matching" in res
    out = cv2.imread(str(settings.HEATMAPS_DIR / Path(res["diff_image_path"]).name))
    assert out is not None and out.shape[:2] == (800, 800)
    # red circle pixels (BGR ~ (0,0,230)) must exist on the annotated image
    red = (out[:, :, 2] > 200) & (out[:, :, 1] < 40) & (out[:, :, 0] < 40)
    assert red.sum() > 200
