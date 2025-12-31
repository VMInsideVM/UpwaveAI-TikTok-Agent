/**
 * 前端全局配置
 * 支持根路径部署和子路径部署
 */

// 自动检测 base path
// 如果在 /agent/ 下部署，会自动检测
// 如果在根路径部署，base path 为空
const BASE_PATH = (() => {
    const path = window.location.pathname;
    // 如果路径包含 /agent/，则 base path 为 /agent
    if (path.startsWith('/agent/')) {
        return '/agent';
    }
    // 否则为根路径部署
    return '';
})();

// API 基础 URL（当前域名 + base path）
const API_BASE_URL = window.location.origin + BASE_PATH;

// WebSocket 协议（自动根据 HTTP/HTTPS 切换）
const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

// WebSocket 基础 URL
const WS_BASE_URL = `${WS_PROTOCOL}//${window.location.host}${BASE_PATH}`;

// 导出配置
window.APP_CONFIG = {
    BASE_PATH,
    API_BASE_URL,
    WS_PROTOCOL,
    WS_BASE_URL
};

// 辅助函数：获取完整路径
window.getFullPath = (path) => {
    // 确保路径以 / 开头
    if (!path.startsWith('/')) {
        path = '/' + path;
    }
    return BASE_PATH + path;
};

// 辅助函数：页面跳转（自动添加 base path）
window.navigateTo = (path) => {
    window.location.href = window.getFullPath(path);
};

console.log('🔧 App Config:', window.APP_CONFIG);
