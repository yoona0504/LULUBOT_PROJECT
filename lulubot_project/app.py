# app.py
import os, time, threading, pickle, traceback
from collections import deque
from flask import Flask, Response, jsonify, request, send_from_directory
import cv2
import numpy as np
import face_recognition  # pip install face_recognition
from tensorflow.keras.models import load_model  # 감정 모델 사용시
from tensorflow.keras.preprocessing.image import img_to_array

app = Flask(__name__)

# ---------- 설정 ----------
MIRROR = True  # 셀카 모드(좌우반전) 출력 여부
FACE_THRESH = 0.50  # 얼굴 매칭 임계값(낮을수록 엄격)
DETECT_EVERY_N = 5  # N프레임마다 얼굴/감정 수행(부하 감소)
JPEG_QUALITY = 80

# ---------- 경로/스토리지 ----------
DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "faces_db.pkl")

known_encodings = []  # [{name:str, encoding:np.ndarray}]
if os.path.exists(DB_PATH):
    with open(DB_PATH, "rb") as f:
        try:
            known_encodings = pickle.load(f)
        except Exception:
            known_encodings = []

def save_db():
    with open(DB_PATH, "wb") as f:
        pickle.dump(known_encodings, f)

# ---------- 감정 모델 ----------
EMO_LABELS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]
emotion_model = None
EMO_INPUT = (48, 48)

def load_emotion_model():
    global emotion_model
    model_path = os.path.join("models", "emotion.h5")
    if os.path.exists(model_path):
        try:
            emotion_model = load_model(model_path)
            # warm-up: 첫 추론 지연 방지
            _ = emotion_model.predict(np.zeros((1, EMO_INPUT[0], EMO_INPUT[1], 1), dtype="float32"), verbose=0)
            print("[OK] emotion model loaded & warmed up")
        except Exception as e:
            print("[WARN] emotion model load failed:", e)
            emotion_model = None
    else:
        print("[WARN] emotion model not found at", model_path)

def predict_emotion(face_bgr):
    """BGR 얼굴 이미지 -> (label:str, prob:float)"""
    if emotion_model is None:
        return ("neutral", 0.0)  # 모델 없을 땐 기본값
    try:
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        roi = cv2.resize(gray, EMO_INPUT)
        roi = roi.astype("float32") / 255.0
        roi = img_to_array(roi)             # (48,48,1)
        roi = np.expand_dims(roi, axis=0)   # (1,48,48,1)
        preds = emotion_model.predict(roi, verbose=0)[0]
        idx = int(np.argmax(preds))
        return (EMO_LABELS[idx], float(preds[idx]))
    except Exception as e:
        # 예측 실패 시 안전 폴백
        return ("neutral", 0.0)

# ---------- 런타임 상태 ----------
cap = None
cam_lock = threading.Lock()
running = False
latest_frame = None        # 마지막 원본 프레임 (등록/인식에 사용, 미러링 안 함)
annotated_frame = None     # 화면 송출용 프레임 (오버레이 + 필요 시 미러링)

# 상태 공유(프론트 폴링/디버깅용)
state = {
    "faces": 0,
    "last_emotion": None,
    "last_conf": 0.0,
    "last_names": [],
    "last_error": None,
    "tick": 0,
}

def _overlay_status(base_frame, text_lines, org=(12, 28)):
    """좌상단에 여러 줄 텍스트 오버레이 (가독성 테두리 포함)"""
    x, y = org
    for i, line in enumerate(text_lines):
        yy = y + i * 24
        cv2.putText(base_frame, line, (x, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(base_frame, line, (x, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)

def camera_loop():
    global cap, running, latest_frame, annotated_frame, state
    i = 0
    try:
        while running and cap and cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                state["last_error"] = "camera read fail"
                time.sleep(0.02)
                continue

            latest_frame = frame.copy()
            draw = frame.copy()
            names = []
            emotions = []
            boxes = []

            # N프레임에 한 번만 무거운 작업 실행
            if i % DETECT_EVERY_N == 0:
                try:
                    small = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                    rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                    boxes = face_recognition.face_locations(rgb_small, model="hog")  # or "cnn"
                    encs = face_recognition.face_encodings(rgb_small, boxes)
                    # 이름 매칭
                    for enc in encs:
                        name = "Unknown"
                        if known_encodings:
                            db_encs = [e["encoding"] for e in known_encodings]
                            dists = face_recognition.face_distance(db_encs, enc)
                            j = int(np.argmin(dists))
                            if dists[j] < FACE_THRESH:
                                name = known_encodings[j]["name"]
                        names.append(name)
                    # 감정 예측(원본 좌표로 ROI 추출)
                    for (top, right, bottom, left) in boxes:
                        (t, r, b, l) = (top * 4, right * 4, bottom * 4, left * 4)
                        face_roi = frame[max(0, t): b, max(0, l): r]
                        if face_roi.size == 0:
                            emotions.append(("neutral", 0.0))
                        else:
                            emotions.append(predict_emotion(face_roi))
                except Exception as e:
                    state["last_error"] = f"detect/predict error: {e}"
                    boxes, names, emotions = [], [], []

            # 오버레이(얼굴 박스/라벨)
            for (top, right, bottom, left), name, emo in zip(boxes, names, emotions):
                (t, r, b, l) = (top * 4, right * 4, bottom * 4, left * 4)
                cv2.rectangle(draw, (l, t), (r, b), (0, 255, 0), 2)
                label = f"{name} | {emo[0]} {int(emo[1] * 100)}%"
                cv2.rectangle(draw, (l, b - 22), (r, b), (0, 255, 0), -1)
                cv2.putText(draw, label, (l + 4, b - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

            # 상단 상태 텍스트: 얼굴 없어도 항상 띄우기
            if len(boxes) == 0:
                header = ["얼굴 미검출"]
                if len(known_encodings) == 0:
                    header.append("등록자 없음 — 감정만 표시 모드")
            else:
                # 여러 얼굴인 경우 첫 번째 기준으로 간단 요약
                emo_txt = f"{emotions[0][0]} ({int(emotions[0][1] * 100)}%)" if emotions else "분석중"
                who_txt = names[0] if names else "Unknown"
                header = [f"{who_txt} | {emo_txt}  ·  얼굴:{len(boxes)}"]

            _overlay_status(draw, header)

            # 미러링은 최종 단계에서만
            annotated_frame = cv2.flip(draw, 1) if MIRROR else draw

            # 상태 업데이트(폴링/디버깅용)
            state["faces"] = len(boxes)
            state["last_names"] = names
            if emotions:
                state["last_emotion"] = emotions[0][0]
                state["last_conf"] = float(emotions[0][1])
            else:
                state["last_emotion"] = None
                state["last_conf"] = 0.0
            state["tick"] += 1

            i += 1
            time.sleep(0.001)  # 너무 바쁘지 않게
    except Exception as e:
        state["last_error"] = f"camera_loop crashed: {e}"
        traceback.print_exc()
    finally:
        if cap:
            try:
                cap.release()
            except Exception:
                pass
        annotated_frame = None

def gen_mjpeg():
    global annotated_frame, latest_frame
    while running:
        frame = annotated_frame if annotated_frame is not None else latest_frame
        if frame is None:
            time.sleep(0.02)
            continue
        ret, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
        if not ret:
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n")
        time.sleep(0.02)  # ~50fps

# ---------- API ----------
@app.route("/api/start_camera", methods=["GET", "POST"])
def start_camera():
    global cap, running, state
    with cam_lock:
        if running:
            return jsonify({"status": "started"})
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            state["last_error"] = "camera open failed"
            return jsonify({"status": "error", "msg": "camera open failed"}), 500
        running = True
        # 모델은 카메라와 별개로 미리 로드
        load_emotion_model()
        threading.Thread(target=camera_loop, daemon=True).start()
    return jsonify({"status": "started"})

@app.route("/api/stop_camera", methods=["GET", "POST"])
def stop_camera():
    global running
    with cam_lock:
        running = False
    return jsonify({"status": "stopped"})

@app.route("/api/camera_status")
def camera_status():
    return jsonify({"status": "started" if running else "stopped"})

@app.route("/video_feed")
def video_feed():
    if not running:
        return jsonify({"error": "camera not started"}), 409
    return Response(gen_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/api/current_status")
def current_status():
    return jsonify({
        "camera": "started" if running else "stopped",
        "known_count": len(known_encodings),
        "mirror": MIRROR,
    })

@app.route("/api/status")
def api_status():
    """프론트 폴링용 상세 상태"""
    return jsonify({
        "camera": "started" if running else "stopped",
        "faces": state["faces"],
        "names": state["last_names"],
        "emotion": state["last_emotion"],
        "conf": state["last_conf"],
        "error": state["last_error"],
        "tick": state["tick"],
        "known_count": len(known_encodings),
        "mirror": MIRROR,
    })

@app.route("/api/register_face", methods=["POST"])
def register_face():
    """
    body: { "name": "홍길동" }
    현재 latest_frame(원본)에서 얼굴 1개를 찾아 인코딩 저장
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "msg": "name required"}), 400
    if latest_frame is None:
        return jsonify({"ok": False, "msg": "no frame yet"}), 409

    frame = latest_frame.copy()  # 원본 사용 (미러링 안 됨)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb, model="hog")
    if len(boxes) != 1:
        return jsonify({"ok": False, "msg": f"need exactly 1 face, got {len(boxes)}"}), 400
    enc = face_recognition.face_encodings(rgb, boxes)[0]

    # 같은 이름 있으면 교체(갱신), 없으면 추가
    replaced = False
    for e in known_encodings:
        if e["name"] == name:
            e["encoding"] = enc
            replaced = True
            break
    if not replaced:
        known_encodings.append({"name": name, "encoding": enc})
    save_db()
    return jsonify({"ok": True, "name": name, "updated": replaced})

@app.route("/")
def root():
    # 프로젝트 루트의 index.html 반환
    return send_from_directory(os.getcwd(), "index.html")

@app.route("/favicon.ico")
def favicon():
    return ("", 204)  # 파비콘 404 로그 방지

if __name__ == "__main__":
    # 환경에 맞게 호스트/포트 조정
    app.run(host="0.0.0.0", port=5001, debug=True)
