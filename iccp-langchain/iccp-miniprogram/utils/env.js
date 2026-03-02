// 一键切换 API 环境：
// - 本地调试：MODE = 'local'（请求 127.0.0.1）
// - 真机调试：MODE = 'lan'（请求局域网 IP）
// - 线上/预览：MODE = 'prod'（请求 HTTPS 域名）
//
// 切换步骤：
// 1) 改 MODE
// 2) 若是 lan，改 LAN_HOST 为当前电脑 IPv4
// 3) 微信开发者工具重新编译

const MODE = 'lan' // 'local' | 'lan' | 'prod'
const PORT = 8000
const LAN_HOST = '192.168.43.211'
const PROD_HOST = 'https://api.your-domain.com'

const API_BASE_MAP = {
  local: `http://127.0.0.1:${PORT}`,
  lan: `http://${LAN_HOST}:${PORT}`,
  prod: PROD_HOST,
}

const API_BASE = API_BASE_MAP[MODE] || API_BASE_MAP.local

module.exports = {
  MODE,
  PORT,
  LAN_HOST,
  API_BASE,
}
