import numpy as np
import onnx
from onnx import helper, TensorProto
import cv2
from app.config import settings
from app.services import ai_models_service as ai


def _snap(client, auth, pid):
    return client.get(f"/api/satellite/properties/{pid}/snapshots", headers=auth["admin"]).json()


def test_unavailable_without_weights(client, auth):
    r = client.get("/api/models", headers=auth["admin"]).json()
    by = {m["model_key"]: m for m in r}
    assert by["LEVIR-CD-Building-v2"]["is_available"] is False
    out = ai.levir_cd_detector.detect_building_changes("a.png", "b.png", 1)
    assert out["status"] == "UNAVAILABLE" and out["change_detected"] is None
    assert ai.rooftop_object_detector.detect_rooftop_objects("a.png", 1)["status"] == "UNAVAILABLE"


def _make_change_model(path):
    """Tiny real ONNX graph with the documented signature (2 inputs -> change logit map). Test fixture only."""
    a = helper.make_tensor_value_info("a", TensorProto.FLOAT, [1, 3, 256, 256])
    b = helper.make_tensor_value_info("b", TensorProto.FLOAT, [1, 3, 256, 256])
    y = helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 1, 256, 256])
    nodes = [helper.make_node("Sub", ["a", "b"], ["d"]), helper.make_node("Abs", ["d"], ["ad"]),
             helper.make_node("ReduceMean", ["ad"], ["m"], axes=[1], keepdims=1) if False else
             helper.make_node("ReduceMean", ["ad"], ["m"], keepdims=1, axes=[1])]
    nodes.append(helper.make_node("Sub", ["m", "k"], ["y"]))
    k = helper.make_tensor("k", TensorProto.FLOAT, [1], [0.3])
    g = helper.make_graph(nodes, "g", [a, b], [y], initializer=[k])
    model = helper.make_model(g, opset_imports=[helper.make_opsetid("", 11)])
    model.ir_version = 8
    onnx.save(model, path)


def test_change_detector_runs_with_weights(tmp_path, monkeypatch, client, auth):
    mp = tmp_path / "change.onnx"
    _make_change_model(str(mp))
    monkeypatch.setattr(settings, "LEVIR_CD_MODEL_PATH", str(mp))
    ai._levir_runner.reset()
    a = np.full((200, 200, 3), 80, np.uint8)
    b = a.copy()
    cv2.rectangle(b, (40, 40), (140, 140), (250, 250, 250), -1)
    cv2.imwrite(str(tmp_path / "a.png"), a)
    cv2.imwrite(str(tmp_path / "b.png"), b)
    out = ai.levir_cd_detector.detect_building_changes(str(tmp_path / "a.png"), str(tmp_path / "b.png"), 1)
    assert out["status"] == "COMPLETED", out
    assert out["change_detected"] is True and out["detected_features"]
    same = ai.levir_cd_detector.detect_building_changes(str(tmp_path / "a.png"), str(tmp_path / "a.png"), 1)
    assert same["change_detected"] is False
    ai.init_ai_model_registry()
    models = {m["model_key"]: m for m in client.get("/api/models", headers=auth["admin"]).json()}
    assert models["LEVIR-CD-Building-v2"]["is_available"] is True
    monkeypatch.setattr(settings, "LEVIR_CD_MODEL_PATH", "")
    ai._levir_runner.reset()
    ai.init_ai_model_registry()


def test_endpoints_do_not_crash_on_path_resolution(client, auth):
    pid = client.get("/api/properties", headers=auth["admin"]).json()[0]["id"]
    snaps = _snap(client, auth, pid)
    r = client.post("/api/models/building-change", json={"property_id": pid, "baseline_snapshot_id": snaps[-1]["id"],
                    "comparison_snapshot_id": snaps[0]["id"]}, headers=auth["admin"])
    assert r.status_code == 200 and r.json()["status"] == "UNAVAILABLE"
