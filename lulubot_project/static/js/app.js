import CameraController from './core/camera.js';
import ChatController from './core/chat.js';
import UIController from './core/ui.js';
import StatusController from './core/status.js';
import UserController from './core/user.js';

let camera, chat, ui, status, user;

const $ = (id) => document.getElementById(id);
const cacheBust = () => `cb=${Date.now()}`;

// 단순 토스트(프로젝트 토스트 있으면 UIController 내부 구현으로 대체됨)
const toast = (msg, type='info') => console[type === 'error' ? 'error' : 'log'](`[${type}] ${msg}`);

// JSON POST 헬퍼
async function postJSON(url, body = {}) {
  const res = await fetch(`${url}?${cacheBust()}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  let j = {};
  try { j = await res.json(); } catch {}
  if (!res.ok) throw new Error(j.msg || `${url} failed`);
  return j;
}

// 모달 열고 닫기
function openRegisterModal() {
  const modal = $('registerModal');
  if (modal) {
    modal.style.display = 'block';
    const input = $('userName');
    if (input) {
      input.value = '';
      input.focus();
    }
  }
}
function closeRegisterModal() {
  const modal = $('registerModal');
  if (modal) modal.style.display = 'none';
}

// 사용자 등록 로직: 서버의 latest_frame에서 얼굴 1개 찾아 저장
async function registerUserFlow() {
  const nameInput = $('userName');
  const name = (nameInput?.value || '').trim();
  if (!name) {
    toast('이름을 입력하세요.', 'error');
    ui?.updateStatus?.('error', '이름이 비어 있습니다');
    $('beepAudio3')?.play?.().catch(()=>{});
    return;
  }

  try {
    ui?.showLoading?.('사용자 등록 중… 카메라를 똑바로 봐주세요');
    ui?.updateStatus?.('idle', '등록 중…');

    const r = await postJSON('/api/register_face', { name });

    toast(r.updated ? '기존 사용자 인코딩 업데이트 완료' : '새 사용자 등록 완료', 'success');
    ui?.updateStatus?.('active', `등록됨: ${r.name}`);
    $('beepAudio2')?.play?.().catch(()=>{});

    closeRegisterModal();
  } catch (e) {
    console.error(e);
    toast(`등록 실패: ${e.message}`, 'error');
    ui?.updateStatus?.('error', '등록 실패—화면에 얼굴 1개만 보이게 해주세요');
    $('beepAudio3')?.play?.().catch(()=>{});
  } finally {
    ui?.hideLoading?.();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // --- 컨트롤러 생성 ---
  ui = new UIController();

  camera = new CameraController({
    // 주의: index.html에서는 <img id="videoFeed"> 이므로 core/camera.js가 MJPEG <img>를 지원하도록 되어 있어야 함
    video: $('videoFeed'),
    startBtn: $('startBtn'),
    stopBtn: $('stopBtn'),
    registerBtn: $('registerBtn'),
    ui,
  });

  chat = new ChatController({
    input: $('chatInput'),
    sendBtn: $('sendBtn'),
    chatMessages: $('chatMessages'),
    ui,
  });

  user = new UserController({
    userNameInput: $('userName'),
    confirmRegisterBtn: $('confirmRegister'),
    cancelRegisterBtn: $('cancelRegister'),
    registerModal: $('registerModal'),
    ui,
  });

  status = new StatusController({
    ui,
    chat,
  });

  // --- 모듈 init ---
  camera.init();
  chat.init();
  user.init();
  status.init();

  // --- 등록 버튼 → 모달 열기 ---
  $('registerBtn')?.addEventListener('click', openRegisterModal);
  $('closeModal')?.addEventListener('click', closeRegisterModal);
  $('cancelRegister')?.addEventListener('click', closeRegisterModal);

  // --- 모달 확인 → 서버 등록 ---
  $('confirmRegister')?.addEventListener('click', registerUserFlow);

  // (선택) Enter 키로도 등록
  $('userName')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') registerUserFlow();
  });

  // --- (선택) 카메라 상태 폴링해 우측 상단 상태 갱신 ---
  setInterval(async () => {
    try {
      const res = await fetch(`/api/camera_status?${cacheBust()}`);
      if (!res.ok) return;
      const j = await res.json();
      if (j.status === 'started') {
        ui?.updateStatus?.('active', '스트리밍 중');
      }
    } catch {}
  }, 5000);
});
