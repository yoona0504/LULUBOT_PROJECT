import CameraController from './core/camera.js';
import ChatController from './core/chat.js';
import UIController from './core/ui.js';
import StatusController from './core/status.js';
import UserController from './core/user.js';

let camera, chat, ui, status, user;

document.addEventListener('DOMContentLoaded', () => {
    ui = new UIController();
    camera = new CameraController({
        video: document.getElementById('videoFeed'),
        startBtn: document.getElementById('startBtn'),
        stopBtn: document.getElementById('stopBtn'),
        registerBtn: document.getElementById('registerBtn'),
        ui: ui
    });

    chat = new ChatController({
        input: document.getElementById('chatInput'),
        sendBtn: document.getElementById('sendBtn'),
        chatMessages: document.getElementById('chatMessages'),
        ui: ui
    });

    user = new UserController({
        userNameInput: document.getElementById('userName'),
        confirmRegisterBtn: document.getElementById('confirmRegister'),
        cancelRegisterBtn: document.getElementById('cancelRegister'),
        registerModal: document.getElementById('registerModal'),
        ui: ui
    });

    status = new StatusController({
        ui: ui,
        chat: chat
    });

    // 모듈 실행
    camera.init();
    chat.init();
    user.init();
    status.init();
});
