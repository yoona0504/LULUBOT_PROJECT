// 📁 static/js/utils/format.js

/**
 * 감정 코드에 대응하는 이모지 반환
 * @param {string} emotion
 * @returns {string}
 */
export function getEmotionEmoji(emotion) {
    const emojis = {
        happy: '😊',
        sad: '😢',
        angry: '😠',
        surprise: '😲',
        fear: '😨',
        neutral: '😐',
        disgust: '🤢'
    };
    return emojis[emotion] || '❓';
}

/**
 * 감정 코드에 대응하는 색상 반환
 * @param {string} emotion
 * @returns {string}
 */
export function getEmotionColor(emotion) {
    const colors = {
        happy: '#34C759',
        sad: '#007AFF',
        angry: '#FF3B30',
        surprise: '#FF9500',
        fear: '#5856D6',
        neutral: '#8E8E93',
        disgust: '#FF2D92'
    };
    return colors[emotion] || '#CCCCCC';
}
