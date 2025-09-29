// 📁 static/js/utils/dom.js

/**
 * 안전한 HTML 문자 이스케이프 처리
 * @param {string} unsafe 
 * @returns {string}
 */
export function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/**
 * 상대 시간 포맷 (ex: 3분 전)
 * @param {string|number} timestamp 
 * @returns {string}
 */
export function formatRelativeTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;

    if (diff < 60000) return '방금 전';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}분 전`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}시간 전`;
    return date.toLocaleDateString('ko-KR');
}