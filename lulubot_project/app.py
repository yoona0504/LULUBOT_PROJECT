# app.py (no-h5, uses emotions.py) — routes_emotion.py 기능 통합판
import os, time, threading, pickle, traceback
from collections import deque
from flask import Flask, Response, jsonify, request, send_from_directory
import cv2
import numpy as np
import face_recognition  # 설치되어 있으면 사용 (없으면 아래 주석 참고)
from emotions import HeuristicEmotion, FerEmotion, EMOTIONS  # EMOTIONS 미사용해도 무방

app = Flask(__name__)

# ---------- 설정 ----------
MIRROR = True       # 셀카 모드(좌우반전) 출력 여부
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

# ---------- 감정 엔진 ----------
# fer/mtcnn이 깔려 있으면 FerEmotion.ok=True로 동작, 아니면 자동 폴백(휴리스틱)
try:
    predictor = FerEmotion(alpha=0.50, conf_th=0.40, min_rel=0.12)
    ENGINE_NAME = "fer" if getattr(predictor, "ok", False) else "heuristic"
    if ENGINE_NAME == "heuristic":
        predictor = HeuristicEmotion()
except Exception:
    predictor = HeuristicEmotion()
    ENGINE_NAME = "heuristic"

def _complete7(d: dict) -> dict:
    """항상 7키를 가지도록 보정 + 정규화"""
    ALL7 = ["angry","disgust","fear","happy","sad","surprise","neutral"]
    out = {}
    for k in ALL7:
        v = float(d.get(k, 0.0)) if d else 0.0
        if v < 0: v = 0.0
        if v > 1: v = 1.0
        out[k] = v
    s = sum(out.values())
    if s == 0.0:
        return {k: (1.0 if k == "neutral" else 0.0) for k in ALL7}
    return {k: (out[k] / s) for k in ALL7}

# ---------- 런타임 상태 ----------
cap = None
cam_lock = threading.Lock()
running = False
latest_frame = None        # 마지막 원본 프레임 (등록/인식에 사용, 미러링 안 함)
annotated_frame = None     # 화면 송출용 프레임 (오버레이 + 필요 시 미러링)

# 추가: 감정 히스토리/FPS 관리
HIST_MAX = 200
emotion_hist = deque(maxlen=HIST_MAX)
fps_ma = deque(maxlen=30)
last_time = time.time()

def _now_ms():
    return int(time.time() * 1000)

state = {
    "faces": 0,
    "last_emotion": None,
    "last_conf": 0.0,
    "last_probs": None,   # 추가: 마지막 7클래스 확률 분포
    "last_names": [],
    "last_error": None,
    "tick": 0,
    "engine": ENGINE_NAME,
    "last_ts": time.time(),  # 마지막 갱신 시각
}

def _overlay_status(base_frame, text_lines, org=(12, 28)):
    x, y = org
    for i, line in enumerate(text_lines):
        yy = y + i * 24
        cv2.putText(base_frame, line, (x, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(base_frame, line, (x, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)

def camera_loop():
    global cap, running, latest_frame, annotated_frame, state, last_time
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
            boxes = []
            top_label = None
            top_conf = 0.0
            probs0 = None  # 첫 얼굴 확률(7)

            # N프레임에 한 번만 무거운 작업 실행
            if i % DETECT_EVERY_N == 0:
                try:
                    # face_recognition: 빠른 검출/인코딩을 위해 1/4 스케일
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

                    # 감정 예측 (모든 얼굴에 대해 가능, 요약은 첫 얼굴 기준)
                    emotions_per_face = []
                    for (top, right, bottom, left) in boxes:
                        (t, r, b, l) = (top * 4, right * 4, bottom * 4, left * 4)
                        face_roi = frame[max(0, t): b, max(0, l): r]
                        if face_roi.size == 0:
                            probs = {"neutral": 1.0}
                        else:
                            probs = predictor.predict(face_roi)  # dict(7) or dict 일부 → 보정
                            probs = _complete7(probs)
                        emotions_per_face.append(probs)

                    # 요약(첫 얼굴 기준)
                    if emotions_per_face:
                        probs0 = emotions_per_face[0]
                        top_label = max(probs0, key=probs0.get)
                        top_conf = float(probs0[top_label])
                    else:
                        top_label, top_conf = None, 0.0

                    # FPS 계산(최근 감정 업데이트 주기 기준)
                    now = time.time()
                    dt = now - last_time
                    last_time = now
                    if dt > 0:
                        fps_ma.append(1.0 / dt)

                except Exception as e:
                    state["last_error"] = f"detect/predict error: {e}"
                    boxes, names, top_label, top_conf, probs0 = [], [], None, 0.0, None

            # 오버레이(얼굴 박스/라벨)
            for (top, right, bottom, left), name in zip(boxes, names):
                (t, r, b, l) = (top * 4, right * 4, bottom * 4, left * 4)
                cv2.rectangle(draw, (l, t), (r, b), (0, 255, 0), 2)
                lbl = name if name else "Unknown"
                if top_label is not None:
                    lbl = f"{lbl} | {top_label} {int(top_conf * 100)}%"
                cv2.rectangle(draw, (l, b - 22), (r, b), (0, 255, 0), -1)
                cv2.putText(draw, lbl, (l + 4, b - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

            # 상단 상태 텍스트
            if len(boxes) == 0:
                header = [f"얼굴 미검출 · 엔진:{ENGINE_NAME}"]
                if len(known_encodings) == 0:
                    header.append("등록자 없음 — 감정만 표시 모드")
            else:
                emo_txt = f"{top_label} ({int(top_conf * 100)}%)" if top_label else "분석중"
                who_txt = names[0] if names else "Unknown"
                header = [f"{who_txt} | {emo_txt}  ·  얼굴:{len(boxes)} · 엔진:{ENGINE_NAME}"]

            _overlay_status(draw, header)

            # 미러링은 최종 단계에서만
            annotated_frame = cv2.flip(draw, 1) if MIRROR else draw

            # 상태 업데이트(폴링/디버깅용)
            state["faces"] = len(boxes)
            state["last_names"] = names
            state["last_emotion"] = top_label
            state["last_conf"] = float(top_conf) if top_label else 0.0
            state["last_probs"] = probs0 if probs0 is not None else state.get("last_probs")
            state["tick"] += 1
            state["last_ts"] = time.time()

            # 히스토리 저장(첫 얼굴 기준으로만 기록)
            if probs0 is not None:
                emotion_hist.append({
                    "t": _now_ms(),
                    "probs": probs0,
                    "engine": ENGINE_NAME,
                })

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
    global cap, running, state, last_time
    with cam_lock:
        if running:
            return jsonify({"status": "started"})
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            state["last_error"] = "camera open failed"
            return jsonify({"status": "error", "msg": "camera open failed"}), 500
        # 초기화
        last_time = time.time()
        fps_ma.clear()
        running = True
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
        "engine": ENGINE_NAME,
        "emotion": last_emotion,         # ← 최신 감정 결과
        "confidence": last_confidence    # ← 확률값 (0~1)
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
        "engine": state["engine"],
    })

# === 추가된 라우트들: routes_emotion.py 기능 흡수 ===
@app.route("/api/face_state")
def face_state():
    """
    최신 감정 1개(라벨/스코어)와 ok(stale 여부)를 반환
    """
    probs = state.get("last_probs")
    if not probs:
        probs = {"neutral": 1.0}
    probs7 = _complete7(probs)
    label = max(probs7, key=probs7.get)
    score = float(probs7[label])
    stale = (time.time() - state.get("last_ts", time.time())) > 2.0
    return jsonify({"ok": (not stale), "label": label, "score": round(score, 4), "probs": probs7})

@app.route("/api/emotion")
def emotion():
    """
    엔진, 최근 FPS(이동평균), 최근 감정 분포와 TOP 반환
    """
    # FPS 이동평균
    fps = round(sum(fps_ma) / len(fps_ma), 2) if fps_ma else None

    probs = state.get("last_probs")
    if not probs:
        probs = {"neutral": 1.0}
    probs7 = _complete7(probs)
    top = max(probs7, key=probs7.get)
    return jsonify({
        "engine": ENGINE_NAME,
        "fps": fps,
        "emotions": probs7,
        "top": {"label": top, "score": float(probs7[top])}
    })

@app.route("/api/history")
def history():
    """
    최근 감정 히스토리(시간ms, 확률분포, 엔진)를 FIFO로 반환
    """
    return jsonify(ok=True, data=list(emotion_hist))

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
