"""基于 MediaPipe BlazePose 的动作姿态评分。

- 关键点：BlazePose 33 点，CPU 推理（XNNPACK，不依赖 CUDA）
- 运行模式：IMAGE 单帧模式，无任何随机成分，同一张图两次结果一致
- 支持动作：深蹲（squat）、肩外展（shoulder_abduction）
- 评分：由膝关节角度、膝内扣偏移、躯干前倾、左右对称等几何指标分段线性加权，
  每个扣分项都对应一条可解释的问题与纠正建议
"""
from __future__ import annotations

import math
import threading
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "pose_landmarker_full.task"

# BlazePose 关键点索引
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_KNEE, R_KNEE = 25, 26
L_ANKLE, R_ANKLE = 27, 28

VIS_THRESHOLD = 0.5

_landmarker = None
_landmarker_lock = threading.Lock()
_infer_lock = threading.Lock()


class PoseError(Exception):
    """姿态分析不可用或图中没有可识别的完整人体。"""


def _get_landmarker():
    """惰性创建全局 landmarker（模型加载约 1s，避免每次请求重复加载）。"""
    global _landmarker
    if _landmarker is None:
        with _landmarker_lock:
            if _landmarker is None:
                if not MODEL_PATH.exists():
                    raise PoseError(f"姿态模型缺失：{MODEL_PATH}")
                options = vision.PoseLandmarkerOptions(
                    base_options=mp_python.BaseOptions(model_asset_path=str(MODEL_PATH)),
                    running_mode=vision.RunningMode.IMAGE,
                    num_poses=1,
                    min_pose_detection_confidence=0.5,
                    min_pose_presence_confidence=0.5,
                )
                _landmarker = vision.PoseLandmarker.create_from_options(options)
    return _landmarker


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _angle(a, b, c) -> float:
    """三点夹角（度），b 为顶点。输入为像素坐标。"""
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    norm = math.hypot(*ba) * math.hypot(*bc)
    if norm == 0:
        return 0.0
    cos = max(-1.0, min(1.0, (ba[0] * bc[0] + ba[1] * bc[1]) / norm))
    return math.degrees(math.acos(cos))


def _valgus_deg(hip, knee, ankle) -> float:
    """膝关节相对“髋-踝连线”的横向偏移角（度），正值为膝内扣方向。"""
    if abs(ankle[1] - hip[1]) < 1e-6:
        return 0.0
    ratio = (knee[1] - hip[1]) / (ankle[1] - hip[1])
    line_x = hip[0] + (ankle[0] - hip[0]) * ratio
    lateral = knee[0] - line_x
    body_center_x = (hip[0] + ankle[0]) / 2
    if (knee[0] - body_center_x) * (lateral) < 0:
        lateral = -lateral
    return math.degrees(math.atan2(lateral, max(1.0, math.hypot(ankle[0] - hip[0], ankle[1] - hip[1]))))


def _detect(image_path: Path):
    image = cv2.imread(str(image_path))
    if image is None:
        raise PoseError("图片无法读取，请上传 jpg/png 格式的照片")
    height, width = image.shape[:2]
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
    with _infer_lock:
        result = _get_landmarker().detect(mp_image)
    if not result.pose_landmarks:
        raise PoseError("未检测到人体关键点，请上传全身、光线充足、无遮挡的照片")
    landmarks = result.pose_landmarks[0]
    points = [(lm.x * width, lm.y * height) for lm in landmarks]
    visibility = [lm.visibility for lm in landmarks]
    return points, visibility, width, height


def _pick_exercise(image_url: str, exercise: str, points, visibility) -> str:
    if exercise in ("squat", "shoulder_abduction"):
        return exercise
    hint = (image_url or "").lower()
    if any(k in hint for k in ("shoulder", "abduction", "外展")):
        return "shoulder_abduction"
    if any(k in hint for k in ("squat", "蹲")):
        return "squat"
    # 自动判断：双手抬到肩部以上视为肩外展，否则按深蹲
    if visibility[L_WRIST] >= VIS_THRESHOLD and visibility[R_WRIST] >= VIS_THRESHOLD:
        if points[L_WRIST][1] < points[L_SHOULDER][1] and points[R_WRIST][1] < points[R_SHOULDER][1]:
            return "shoulder_abduction"
    return "squat"


def _score_squat(points, visibility):
    required = [L_HIP, R_HIP, L_KNEE, R_KNEE, L_ANKLE, R_ANKLE, L_SHOULDER, R_SHOULDER]
    missing = [i for i in required if visibility[i] < VIS_THRESHOLD]
    if missing:
        raise PoseError("关键点不完整（髋/膝/踝被遮挡），请上传正面全身照")

    knee_l = _angle(points[L_HIP], points[L_KNEE], points[L_ANKLE])
    knee_r = _angle(points[R_HIP], points[R_KNEE], points[R_ANKLE])
    depth = min(knee_l, knee_r)

    valgus_l = _valgus_deg(points[L_HIP], points[L_KNEE], points[L_ANKLE])
    valgus_r = -_valgus_deg(points[R_HIP], points[R_KNEE], points[R_ANKLE])
    valgus = max(0.0, (valgus_l + valgus_r) / 2)

    mid_shoulder = ((points[L_SHOULDER][0] + points[R_SHOULDER][0]) / 2,
                    (points[L_SHOULDER][1] + points[R_SHOULDER][1]) / 2)
    mid_hip = ((points[L_HIP][0] + points[R_HIP][0]) / 2,
               (points[L_HIP][1] + points[R_HIP][1]) / 2)
    dx = mid_shoulder[0] - mid_hip[0]
    dy = mid_shoulder[1] - mid_hip[1]
    trunk_lean = math.degrees(math.atan2(abs(dx), abs(dy) or 1e-6))
    symmetry = abs(knee_l - knee_r)

    if depth <= 100:
        depth_score = 30.0
    elif depth <= 145:
        depth_score = 30.0 * (1 - (depth - 100) / 45)
    else:
        depth_score = 0.0
    valgus_score = 25.0 * _clamp01(1 - max(0.0, valgus - 5) / 12)
    trunk_score = 25.0 * _clamp01(1 - max(0.0, trunk_lean - 20) / 25)
    symmetry_score = 20.0 * _clamp01(1 - max(0.0, symmetry - 5) / 15)
    score = int(round(depth_score + valgus_score + trunk_score + symmetry_score))

    issues = []
    tips = []
    if depth > 130:
        issues.append(f"下蹲深度不足（膝关节最小角度 {depth:.0f}°，目标 ≤110°）")
        tips.append("臀部向后下坐，屈髋屈膝同步，蹲到大腿接近与地面平行")
    if valgus > 10:
        issues.append(f"膝盖内扣（偏离髋-踝连线约 {valgus:.0f}°）")
        tips.append("膝盖始终对准第二脚趾，可在膝上套弹力带做抗阻外展激活臀中肌")
    if trunk_lean > 40:
        issues.append(f"躯干前倾过多（约 {trunk_lean:.0f}°，目标 ≤30°）")
        tips.append("收紧核心、抬起胸口，先屈髋再屈膝，必要时减少下蹲幅度")
    if symmetry > 12:
        issues.append(f"左右腿发力不对称（两侧膝角差 {symmetry:.0f}°）")
        tips.append("降低训练强度，弱侧单独加练，避免重心偏向一侧")
    if not issues:
        issues.append("动作对称、下蹲深度与躯干控制均达标")
        tips.append("保持当前节奏，每组 8–12 次，注意起身时呼气")

    metrics = {
        "knee_angle": round(depth, 1),
        "knee_angle_left": round(knee_l, 1),
        "knee_angle_right": round(knee_r, 1),
        "valgus_deg": round(valgus, 1),
        "trunk_lean_deg": round(trunk_lean, 1),
        "symmetry_deg": round(symmetry, 1),
    }
    return score, metrics, issues, "；".join(tips)


def _score_shoulder(points, visibility):
    required = [L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST, L_HIP, R_HIP]
    missing = [i for i in required if visibility[i] < VIS_THRESHOLD]
    if missing:
        raise PoseError("关键点不完整（肩/肘/腕被遮挡），请上传正面全身照")

    abd_l = _angle(points[L_HIP], points[L_SHOULDER], points[L_ELBOW])
    abd_r = _angle(points[R_HIP], points[R_SHOULDER], points[R_ELBOW])
    abduction = max(abd_l, abd_r)
    side = "左" if abd_l >= abd_r else "右"

    elbow_main = _angle(points[L_SHOULDER], points[L_ELBOW], points[L_WRIST]) if abd_l >= abd_r \
        else _angle(points[R_SHOULDER], points[R_ELBOW], points[R_WRIST])
    elbow_other = _angle(points[R_SHOULDER], points[R_ELBOW], points[R_WRIST]) if abd_l >= abd_r \
        else _angle(points[L_SHOULDER], points[L_ELBOW], points[L_WRIST])
    elbow_deg = min(elbow_main, elbow_other)

    shoulder_tilt = math.degrees(math.atan2(
        abs(points[R_SHOULDER][1] - points[L_SHOULDER][1]),
        abs(points[R_SHOULDER][0] - points[L_SHOULDER][0]) or 1e-6))

    abd_score = 50.0 * _clamp01((abduction - 90) / 70)
    elbow_score = 25.0 * _clamp01((elbow_deg - 120) / 40)
    trunk_score = 25.0 * _clamp01(1 - max(0.0, shoulder_tilt - 5) / 10)
    score = int(round(abd_score + elbow_score + trunk_score))

    issues = []
    tips = []
    if abduction < 150:
        issues.append(f"{side}肩上举不足（肩关节角度 {abduction:.0f}°，目标 ≥160°）")
        tips.append("可先做肩胛上回旋与胸小肌放松，再逐步增加上举幅度，避免耸肩代偿")
    if elbow_deg < 160:
        issues.append(f"肘关节屈曲代偿（{elbow_deg:.0f}°，目标 ≥160°）")
        tips.append("上举过程保持肘伸直，必要时减轻负重或改为无负重侧平举")
    if shoulder_tilt > 10:
        issues.append(f"躯干侧倾约 {shoulder_tilt:.0f}°，存在代偿")
        tips.append("收紧核心保持躯干直立，双侧肩胛对称上回旋")
    if not issues:
        issues.append("上举角度与肘伸展均达标，双侧对称")
        tips.append("保持肩胛稳定，上举到末端停留 1–2 秒再缓慢放下")

    metrics = {
        "abduction_deg": round(abduction, 1),
        "abduction_left": round(abd_l, 1),
        "abduction_right": round(abd_r, 1),
        "elbow_deg": round(elbow_deg, 1),
        "shoulder_tilt_deg": round(shoulder_tilt, 1),
    }
    return score, metrics, issues, "；".join(tips)


def analyze_image(image_path: Path, exercise: str = "auto", image_url: str = "") -> dict:
    """分析一张本地图片，返回确定性评分结果。

    同一张图、同一 exercise 参数，多次调用结果完全一致。
    """
    points, visibility, width, height = _detect(Path(image_path))
    exercise_key = _pick_exercise(image_url, exercise, points, visibility)
    if exercise_key == "shoulder_abduction":
        score, metrics, issues, tips = _score_shoulder(points, visibility)
        pose_name = "肩外展"
    else:
        score, metrics, issues, tips = _score_squat(points, visibility)
        pose_name = "深蹲"

    keypoints = [
        {"x": round(p[0] / width, 5), "y": round(p[1] / height, 5), "v": round(float(visibility[i]), 3)}
        for i, p in enumerate(points)
    ]
    return {
        "score": max(0, min(100, score)),
        "pose": pose_name,
        "exercise": exercise_key,
        "issues": issues,
        "tips": tips,
        "metrics": metrics,
        "keypoints": keypoints,
        "image_size": {"width": width, "height": height},
        "engine": "mediapipe-blazepose-full/cpu",
    }
