# emotions.py
import cv2
import numpy as np

EMOTIONS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

def _complete7(d):
    out = {k: float(max(0.0, min(1.0, d.get(k, 0.0)))) for k in ALL7}
    s = sum(out.values())
    if s == 0:  # 아무 정보 없으면 neutral=1.0
        return {k: (1.0 if k=="neutral" else 0.0) for k in ALL7}
    return {k: out[k]/s for k in ALL7}

class HeuristicEmotion:
    def __init__(self, **kwargs): pass

    def predict(self, bgr_or_face_roi):
        # 아주 단순한 베이스라인: 밝기/대비로 happy/neutral 가중 (원하면 규칙 추가)
        img = cv2.resize(bgr_or_face_roi, (96, 96))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mean = float(np.mean(gray)) / 255.0
        std  = float(np.std(gray)) / 255.0

        base = {k:0.0 for k in ALL7}
        # 예: 밝으면 happy↑, 너무 어두우면 sad/neutral 쪽
        base["happy"]    = max(0.0, min(1.0, 0.2 + 0.8*mean))
        base["sad"]      = max(0.0, min(1.0, 0.2 + 0.8*(1-mean)))
        base["surprise"] = max(0.0, min(1.0, 0.3*std*2.0))
        base["neutral"]  = max(0.0, 0.5 - 0.3*std)

        return _complete7(base)

# FER 끄기
FerEmotion = None
