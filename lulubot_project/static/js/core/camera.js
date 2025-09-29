export default class CameraController {
    constructor({ video, startBtn, stopBtn, registerBtn, ui }) {
        this.video = video;
        this.startBtn = startBtn;
        this.stopBtn = stopBtn;
        this.registerBtn = registerBtn;
        this.ui = ui;
        this.isStreaming = false;
        this.stream = null;
    }

    init() {
        this.bindEvents();
        this.start(); // 페이지 진입 시 자동 시작
    }

    bindEvents() {
        this.startBtn.addEventListener('click', () => this.start());
        this.stopBtn.addEventListener('click', () => this.stop());
    }

    async start() {
        try {
            this.ui.showLoading('카메라를 시작하는 중...');

            const response = await fetch('/api/start_camera');
            const data = await response.json();

            if (data.status === 'started') {
                this.isStreaming = true;
                this.video.src = '/video_feed?' + new Date().getTime();
                this.video.play();

                this.startBtn.disabled = true;
                this.stopBtn.disabled = false;
                this.registerBtn.disabled = false;

                this.ui.updateStatus('active', '카메라 활성화');
                this.ui.showNotification('카메라가 시작되었습니다!', 'success');
            }
        } catch (err) {
            console.error('카메라 시작 오류:', err);
            this.ui.showNotification('카메라 시작 중 오류가 발생했습니다.', 'error');
        } finally {
            this.ui.hideLoading();
        }
    }

    async stop() {
        try {
            this.ui.showLoading('카메라를 정지하는 중...');

            const response = await fetch('/api/stop_camera');
            const data = await response.json();

            if (data.status === 'stopped') {
                this.isStreaming = false;
                this.video.pause();
                this.video.src = '';

                this.startBtn.disabled = false;
                this.stopBtn.disabled = true;
                this.registerBtn.disabled = true;

                this.ui.updateStatus('inactive', '카메라 정지됨');
                this.ui.showNotification('카메라가 정지되었습니다.', 'info');
            }
        } catch (err) {
            console.error('카메라 정지 오류:', err);
            this.ui.showNotification('카메라 정지 중 오류가 발생했습니다.', 'error');
        } finally {
            this.ui.hideLoading();
        }
    }
}