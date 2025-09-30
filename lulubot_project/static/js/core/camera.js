// 📁 static/js/core/camera.js
const API = "" // Flask 서버 포트 맞추기

export default class CameraController {
  constructor({ video, startBtn, stopBtn, registerBtn, ui }) {
    this.el = video; // <img id="videoFeed">
    this.startBtn = startBtn;
    this.stopBtn = stopBtn;
    this.registerBtn = registerBtn;
    this.ui = ui;

    this.isStreaming = false;
    this._reconnect = null;
    this._health = null;
  }

  init() {
    this._bind();
    this.start(); // 자동 시작 원치 않으면 주석
  }

  _bind() {
    this.startBtn?.addEventListener("click", () => this.start());
    this.stopBtn?.addEventListener("click", () => this.stop());

    // MJPEG <img> 에러 시 재연결
    this.el?.addEventListener("error", () => {
      if (!this.isStreaming) return;
      this.ui?.updateStatus?.("error", "스트림 오류 — 재연결 중…");
      this._scheduleReconnect();
    });
  }

  _cb() {
    return `cb=${Date.now()}`;
  }
  _feed() {
    return `${API}/video_feed?${this._cb()}`; // <<<<<< API 붙임
  }

  async start() {
    try {
      this.ui?.showLoading?.("카메라를 시작하는 중...");

      const response = await fetch(`${API}/api/start_camera`);
      const data = await response.json();

      if (data.status === "started") {
        this.isStreaming = true;
        this.el.src = this._feed(); // <<<<<< this.el 사용

        this._startHealth(); // <<<<<< 옵션: 헬스체크 시작

        this._setButtons(true);
        this.ui?.updateStatus?.("active", "카메라 실행 중");
      } else {
        this.ui?.updateStatus?.("error", "카메라 시작 실패");
      }
    } catch (err) {
      this.ui?.updateStatus?.("error", "카메라 시작 실패");
      console.error(err);
    } finally {
      this.ui?.hideLoading?.();
    }
  }

  async stop() {
    try {
      this.ui?.showLoading?.("카메라 정지 중…");
      this._clearReconnect();
      this._stopHealth();

      // 서버 알림(없어도 무시)
      try {
        await fetch(`${API}/api/stop_camera?${this._cb()}`, { method: "POST" }); // <<<<<< API 붙임
      } catch {}

      this.isStreaming = false;
      this.el.removeAttribute("src");
      this._setButtons(false);
      this.ui?.updateStatus?.("idle", "카메라 정지됨");
    } finally {
      this.ui?.hideLoading?.();
    }
  }

  _scheduleReconnect(delay = 1500) {
    if (!this.isStreaming) return;
    this._clearReconnect();
    this._reconnect = setTimeout(() => {
      this.el.src = this._feed();
      this._scheduleReconnect(Math.min(delay * 1.6, 8000));
    }, delay);
  }
  _clearReconnect() {
    if (this._reconnect) clearTimeout(this._reconnect);
    this._reconnect = null;
  }

  _startHealth() {
    this._stopHealth();
    this._health = setInterval(async () => {
      if (!this.isStreaming) return;
      try {
        const r = await fetch(`${API}/api/camera_status?${this._cb()}`); // <<<<<< API 붙임
        const j = await r.json();
        if (j.status !== "started") this._scheduleReconnect();
      } catch {
        this._scheduleReconnect();
      }
    }, 5000);
  }
  _stopHealth() {
    if (this._health) clearInterval(this._health);
    this._health = null;
  }

  _setButtons(started) {
    if (this.startBtn) this.startBtn.disabled = !!started;
    if (this.stopBtn) this.stopBtn.disabled = !started;
    if (this.registerBtn) this.registerBtn.disabled = !started;
  }
}
