// 📁 static/js/core/user.js
export default class UserController {
    constructor({ userNameInput, confirmRegisterBtn, cancelRegisterBtn, registerModal, ui }) {
        this.userNameInput = userNameInput;
        this.confirmBtn = confirmRegisterBtn;
        this.cancelBtn = cancelRegisterBtn;
        this.registerModal = registerModal;
        this.ui = ui;
    }

    init() {
        this.confirmBtn.addEventListener('click', () => this.registerUser());
        this.cancelBtn.addEventListener('click', () => this.hideRegisterModal());
        this.registerModal.addEventListener('click', (e) => {
            if (e.target === this.registerModal) {
                this.hideRegisterModal();
            }
        });

        this.userNameInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.registerUser();
            }
        });
    }

    showRegisterModal() {
        this.registerModal.classList.add('show');
        this.userNameInput.focus();
    }

    hideRegisterModal() {
        this.registerModal.classList.remove('show');
        this.userNameInput.value = '';
    }

    async registerUser() {
        const name = this.userNameInput.value.trim();
        if (!name) {
            this.ui.showNotification('이름을 입력해주세요.', 'warning');
            return;
        }

        try {
            this.ui.showLoading('사용자를 등록하는 중...');
            const response = await fetch('/api/register_user', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });

            const data = await response.json();
            if (data.success) {
                this.ui.showNotification(data.message, 'success');
                this.hideRegisterModal();
            } else {
                this.ui.showNotification(data.error || '등록 중 오류가 발생했습니다.', 'error');
            }
        } catch (err) {
            console.error('사용자 등록 오류:', err);
            this.ui.showNotification('사용자 등록 실패', 'error');
        } finally {
            this.ui.hideLoading();
        }
    }
}