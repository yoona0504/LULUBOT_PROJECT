# app.py
import os, time, threading, pickle
from collections import deque
from flask import Flask, Response, jsonify, request
import cv2
import numpy as np
import face_recognition  # pip install face_recognition
from tensorflow.keras.models import load_model  # 감정 모델 사용시
from tensorflow.keras.preprocessing.image import img_to_array

app = Flask(__name__)

# ---------- 경로/스토리지 ----------
DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "faces_db.pkl")

known_encodings = []  # [{name:str, encoding:np.ndarray}]
if os.path.exists(DB_PATH):
    with open(DB_PATH, "rb") as f:
        known_encodings = pickle.load(f)

def save_db():
    with open(DB_PATH, "wb") as f:
        pickle.dump(known_encodings, f)

# ---------- 감정 모델(예시) ----------
# 사전 학습된 표정분류 모델(h5)을 ./models/emotion.h5 로 가정
EMO_LABELS = ["angry","disgust","fear","happy","sad","surprise","neutral"]
emotion_model = None
EMO_INPUT = (48,48)

def load_emotion_model():
    global emotion_model
    model_path = os.path.join("models", "emotion.h5")
    if os.path.exists(model_path):
        emotion_model = load_model(model_path)

def predict_emotion(face_bgr):
    """BGR 얼굴 이미지 -> (label, prob)"""
    if emotion_model is None:
        return ("neutral", 0.0)  # 모델 없을 땐 기본값
    gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
    roi = cv2.resize(gray, EMO_INPUT)
    roi = roi.astype("float32") / 255.0
    roi = img_to_array(roi)
    roi = np.expand_dims(roi, axis=0)
    preds = emotion_model.predict(roi, verbose=0)[0]
    idx = int(np.argmax(preds))
    return (EMO_LABELS[idx], float(preds[idx]))

# ---------- 카메라 스레드 ----------
cap = None
cam_lock = threading.Lock()
running = False
latest_frame = None            # 마지막 원본 프레임 (등록에 사용)
annotated_frame = None         # 오버레이된 프레임 (스트림 송출)
fps_skip = 2                   # 성능을 위해 N프레임마다 인식

def camera_loop():
    global cap, running, latest_frame, annotated_frame
    i = 0
    while running and cap and cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.02)
            continue
        latest_frame = frame.copy()

        # 매 N프레임마다 얼굴/감정/인식
        if i % fps_skip == 0:
            small = cv2.resize(frame, (0,0), fx=0.25, fy=0.25)
            rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            boxes = face_recognition.face_locations(rgb_small, model="hog")  # or "cnn"
            encs  = face_recognition.face_encodings(rgb_small, boxes)

            names = []
            emotions = []
            for enc in encs:
                name = "Unknown"
                prob = 0.0
                if known_encodings:
                    db_encs = [e["encoding"] for e in known_encodings]
                    dists = face_recognition.face_distance(db_encs, enc)
                    j = int(np.argmin(dists))
                    # 임계값: 0.6 근처가 보편적. 더 빡세게면 0.45~0.5
                    if dists[j] < 0.5:
                        name = known_encodings[j]["name"]
                names.append(name)
            # 감정은 원본에서 ROI 추출
            for (top,right,bottom,left) in boxes:
                (t,r,b,l) = (top*4, right*4, bottom*4, left*4)
                face_roi = frame[max(0,t):b, max(0,l):r]
                if face_roi.size == 0:
                    emotions.append(("neutral", 0.0))
                else:
                    emotions.append(predict_emotion(face_roi))

            # 오버레이
            draw = frame.copy()
            for (top,right,bottom,left), name, emo in zip(boxes, names, emotions):
                (t,r,b,l) = (top*4, right*4, bottom*4, left*4)
                cv2.rectangle(draw, (l,t), (r,b), (0,255,0), 2)
                label = f"{name} | {emo[0]} {int(emo[1]*100)}%"
                cv2.rectangle(draw, (l, b-22), (r, b), (0,255,0), -1)
                cv2.putText(draw, label, (l+4, b-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,0), 1, cv2.LINE_AA)
            annotated_frame = draw
        else:
            # 지난 프레임 재사용
            if annotated_frame is None:
                annotated_frame = frame
        i += 1

    # 정리
    if cap:
        cap.release()
    annotated_frame = None

def gen_mjpeg():
    while running:
        frame = annotated_frame if annotated_frame is not None else latest_frame
        if frame is None:
            time.sleep(0.02)
            continue
        ret, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n")
        time.sleep(0.02)  # ~50fps

# ---------- API ----------
@app.route("/api/start_camera", methods=["GET","POST"])
def start_camera():
    global cap, running
    with cam_lock:
        if running:
            return jsonify({"status":"started"})
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return jsonify({"status":"error","msg":"camera open failed"}), 500
        running = True
        threading.Thread(target=camera_loop, daemon=True).start()
    load_emotion_model()
    return jsonify({"status":"started"})

@app.route("/api/stop_camera", methods=["GET","POST"])
def stop_camera():
    global running
    with cam_lock:
        running = False
    return jsonify({"status":"stopped"})

@app.route("/api/camera_status")
def camera_status():
    return jsonify({"status":"started" if running else "stopped"})

@app.route("/video_feed")
def video_feed():
    if not running:
        return jsonify({"error":"camera not started"}), 409
    return Response(gen_mjpeg(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")
    
@app.route("/api/current_status")
def current_status():
    return jsonify({
        "camera": "started" if running else "stopped",
        "known_count": len(known_encodings)
    })

@app.route("/api/register_face", methods=["POST"])
def register_face():
    """
    body: { "name": "홍길동" }
    현재 latest_frame에서 얼굴 1개를 찾아 인코딩 저장
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok":False,"msg":"name required"}), 400
    if latest_frame is None:
        return jsonify({"ok":False,"msg":"no frame yet"}), 409

    frame = latest_frame.copy()
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    boxes = face_recognition.face_locations(rgb, model="hog")
    if len(boxes) != 1:
        return jsonify({"ok":False,"msg":f"need exactly 1 face, got {len(boxes)}"}), 400
    enc = face_recognition.face_encodings(rgb, boxes)[0]

    # 같은 이름 있으면 교체(갱신), 없으면 추가
    replaced = False
    for e in known_encodings:
        if e["name"] == name:
            e["encoding"] = enc
            replaced = True
            break
    if not replaced:
        known_encodings.append({"name":name, "encoding":enc})
    save_db()
    return jsonify({"ok":True,"name":name,"updated":replaced})

if __name__ == "__main__":
    # 환경에 맞게 호스트/포트 조정
    app.run(host="0.0.0.0", port=5001, debug=True)
