// 📁 static/js/core/status.js
const API = "http://127.0.0.1:5001";

export default class StatusController {
  constructor({ ui, chat }) {
    this.ui = ui;
    this.chat = chat;
    this.interval = null;
    this.currentUserNameElem = document.getElementById('currentUser');
    this.currentEmotionElem = document.getElementById('currentEmotion');
    this.confidenceFillElem = document.getElementById('confidenceFill');
    this.emotionImage = document.getElementById('emotionImage');
    this.personalityContainer = document.getElementById('personalityTraits');
    this.emotionHistoryContainer = document.getElementById('emotionHistory');
  }

  init() {
    this.interval = setInterval(() => this.updateStatus(), 1000);
  }

  async updateStatus() {
    try {
      const res = await fetch(`${API}/api/current_status`); // <<<<<< API 붙임
      if (!res.ok) return;
      const data = await res.json();

      // app.py 기준: { camera, known_count }만 존재
      const camOn = data.camera === 'started';

      // 사용자/감정 정보는 아직 없으므로 기본 텍스트 유지
      this.currentUserNameElem.textContent = camOn ? '사용자 인식 대기중' : '카메라 꺼짐';

      // 채팅 입력 활성/비활성(카메라 켜짐 기준)
      if (this.chat) {
        this.chat.input.disabled = !camOn;
        this.chat.sendBtn.disabled = !camOn;
      }

      // 아래는 추후 백엔드가 emotion/user 필드를 주면 활성화
      if (data.emotion) {
        this.currentEmotionElem.textContent = data.emotion_korean || data.emotion;
        this.confidenceFillElem.style.width = `${(data.confidence || 0) * 100}%`;
        if (data.emotion_image) this.emotionImage.src = data.emotion_image;
      }

      if (data.behavior) {
        const avatar = document.getElementById('lurubotAvatar');
        avatar.classList.add(data.behavior);
        setTimeout(() => avatar.classList.remove(data.behavior), 1000);
      }

      // 아직 백엔드 없음 → 실패해도 콘솔만
      this.loadPersonality().catch(()=>{});
      this.loadEmotionHistory().catch(()=>{});
    } catch (err) {
      console.error('상태 업데이트 실패:', err);
    }
  }

  async loadPersonality() {
    const res = await fetch(`${API}/api/personality_info`); // <<<<<< API 붙임
    if (!res.ok) throw new Error('no endpoint');
    const traits = await res.json();
    this.personalityContainer.innerHTML = '';
    traits.forEach(trait => {
      const traitDiv = document.createElement('div');
      traitDiv.className = 'trait-item';
      traitDiv.innerHTML = `
        <div class="trait-name">${trait.trait_korean}</div>
        <div class="trait-value">
          <div class="trait-bar">
            <div class="trait-fill" style="width: ${trait.value * 100}%"></div>
          </div>
          <span class="trait-percentage">${Math.round(trait.value * 100)}%</span>
        </div>`;
      this.personalityContainer.appendChild(traitDiv);
    });
  }

  async loadEmotionHistory() {
    const res = await fetch(`${API}/api/emotion_history`); // <<<<<< API 붙임
    if (!res.ok) throw new Error('no endpoint');
    const history = await res.json();
    this.emotionHistoryContainer.innerHTML = '';

    if (!history.length) {
      this.emotionHistoryContainer.innerHTML = '<p>아직 감정 기록이 없습니다.</p>';
      return;
    }

    history.forEach(item => {
      const itemDiv = document.createElement('div');
      itemDiv.className = 'history-item';
      itemDiv.innerHTML = `
        <div class="history-emotion">😊</div>
        <div class="history-info">
          <div class="history-emotion-name">${item.emotion_korean}</div>
          <div class="history-time">${this.formatTime(item.timestamp)}</div>
        </div>
        <div class="history-confidence">${Math.round(item.confidence * 100)}%</div>`;
      this.emotionHistoryContainer.appendChild(itemDiv);
    });
  }

  formatTime(ts) {
    const date = new Date(ts);
    const now = new Date();
    const diff = now - date;
    if (diff < 60000) return '방금 전';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}분 전`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}시간 전`;
    return date.toLocaleDateString('ko-KR');
  }
}
