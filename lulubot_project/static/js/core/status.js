// 📁 static/js/core/status.js
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
            const res = await fetch('/api/current_status');
            const data = await res.json();

            if (data.user) {
                this.currentUserNameElem.textContent = `${data.user.name}님`;
                this.chat.input.disabled = false;
                this.chat.sendBtn.disabled = false;
            } else {
                this.currentUserNameElem.textContent = '사용자 인식 대기중';
                this.chat.input.disabled = true;
                this.chat.sendBtn.disabled = true;
            }

            if (data.emotion) {
                this.currentEmotionElem.textContent = data.emotion_korean || data.emotion;
                this.confidenceFillElem.style.width = `${data.confidence * 100}%`;
                if (data.emotion_image) {
                    this.emotionImage.src = data.emotion_image;
                }
            }

            if (data.behavior) {
                document.getElementById('lurubotAvatar').classList.add(data.behavior);
                setTimeout(() => {
                    document.getElementById('lurubotAvatar').classList.remove(data.behavior);
                }, 1000);
            }

            this.loadPersonality();
            this.loadEmotionHistory();
        } catch (err) {
            console.error('상태 업데이트 실패:', err);
        }
    }

    async loadPersonality() {
        try {
            const res = await fetch('/api/personality_info');
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
        } catch (err) {
            console.error('성격 정보 불러오기 실패:', err);
        }
    }

    async loadEmotionHistory() {
        try {
            const res = await fetch('/api/emotion_history');
            const history = await res.json();
            this.emotionHistoryContainer.innerHTML = '';

            if (history.length === 0) {
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
        } catch (err) {
            console.error('감정 기록 불러오기 실패:', err);
        }
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