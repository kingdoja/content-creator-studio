# ICCP 智能创作 - 微信小程序

基于 ICCP LangChain 后端的微信小程序前端，提供多 Agent 智能内容创作能力。

## 功能

- **首页**：板块入口、快捷操作、最近创作
- **AI 对话**：多轮会话、session 管理、Agent 自动路由
- **内容创作**：7 大板块选择、主题输入、长度/风格配置、一键生成
- **历史记录**：查看过往创作，点击查看详情并复制/分享
- **个人中心**：登录状态、创作统计

## 项目结构

```
iccp-miniprogram/
├── app.js / app.json / app.wxss      # 小程序入口与全局样式
├── project.config.json                # 微信开发者工具配置
├── utils/
│   ├── api.js                         # 后端 API 封装
│   ├── auth.js                        # 微信登录逻辑
│   └── util.js                        # 工具函数与板块配置
├── components/
│   ├── category-picker/               # 板块选择器组件
│   ├── message-bubble/                # 聊天气泡组件
│   └── loading-overlay/               # 加载遮罩组件
├── pages/
│   ├── index/                         # 首页（TabBar）
│   ├── chat/                          # AI 对话（TabBar）
│   ├── writing/                       # 内容创作（TabBar）
│   ├── profile/                       # 个人中心（TabBar）
│   ├── history/                       # 历史记录
│   └── detail/                        # 内容详情
└── static/                            # TabBar 图标（需自行放置）
```

## 快速开始

### 1. 准备后端

确保 ICCP LangChain 后端已运行并可通过 HTTPS 访问：

```bash
conda activate opc 
cd iccp-langchain
# pip install httpx   # 微信登录接口需要
python -m app.main
```

在 `.env` 中配置微信小程序参数：

```
WX_APPID=你的小程序AppID
WX_SECRET=你的小程序AppSecret
```

### 2. 配置小程序

1. 打开 `app.js`，修改 `apiBase` 为后端实际 HTTPS 地址
2. 打开 `project.config.json`，修改 `appid` 为你的小程序 AppID
3. 在 `static/` 目录放置 TabBar 图标文件（81x81 px PNG）：
   - `tab-home.png` / `tab-home-active.png`
   - `tab-chat.png` / `tab-chat-active.png`
   - `tab-write.png` / `tab-write-active.png`
   - `tab-user.png` / `tab-user-active.png`

### 3. 导入微信开发者工具

1. 下载 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
2. 导入项目，选择 `iccp-miniprogram` 目录
3. 填写 AppID
4. 编译预览

### 4. 微信后台配置（正式/体验版才需要）

在 [微信公众平台](https://mp.weixin.qq.com/) 中：

- **开发管理 → 开发设置 → 服务器域名**：添加后端 HTTPS 域名到 `request 合法域名`
- **开发管理 → 开发设置 → AppSecret**：获取 AppSecret 填入后端 `.env`

---

### 本地开发：使用 localhost:8000（无 HTTPS 域名）

没有 HTTPS 域名、后端跑在本机 `http://localhost:8000` 时，按下面步骤即可在开发者工具里联调，**无需**在微信后台配置服务器域名。

1. **确认后端已启动**
   - 在项目根目录（如 `iccp-langchain`）执行：
     ```bash
     cd iccp-langchain
     conda activate opc
     python -m app.main
     ```
   - 保证浏览器访问 `http://localhost:8000/docs` 能打开接口文档。

2. **确认小程序指向本机**
   - 打开 `app.js`，确认 `apiBase` 为：
     ```js
     apiBase: 'http://localhost:8000',
     ```
   - 若本机 IP 为 `192.168.x.x`，真机预览时需改为 `http://192.168.0.112:8000`（见下方第 5 步）。

3. **在微信开发者工具中关闭域名校验**
   - 打开微信开发者工具，顶部菜单：**详情 → 本地设置**。
   - 勾选：**「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」**。
   - 保存后重新编译，小程序即可请求 `http://localhost:8000`。

4. **（可选）微信登录**
   - 若要用静默登录，仍需在微信公众平台 **开发管理 → 开发设置** 获取 **AppSecret**，填入后端 `iccp-langchain/.env` 的 `WX_SECRET`；与是否有 HTTPS 无关。

5. **真机预览时用本机 IP（仍无 HTTPS）**
   - 手机和电脑需在同一局域网。
   - 将 `app.js` 中 `apiBase` 改为电脑局域网 IP，例如：
     ```js
     apiBase: 'http://192.168.0.112:8000',
     ```
   - 真机预览时，在开发者工具里同样勾选「不校验合法域名…」**无效**（只对模拟器生效）。真机请求非 HTTPS 会报错，因此真机调试本地 HTTP 需使用 **调试器 → 打开调试** 或 [微信开发者工具「真机调试」](https://developers.weixin.qq.com/miniprogram/dev/devtools/debug.html)，在真机上开启调试模式才能访问 HTTP。
   - 若不做真机调试，仅用开发者工具模拟器，保持 `apiBase: 'http://localhost:8000'` 即可。

## 技术说明

### 认证流程

```
wx.login() → code → 后端 /api/v1/auth/wx-login → openid → 自动注册/登录 → JWT
```

小程序启动时自动完成静默登录，后续请求携带 JWT Bearer Token。

### API 对接

小程序复用后端现有 REST API，**不使用 SSE 流式接口**（小程序不支持 EventSource），
采用非流式端点 + loading 动画的方式处理。

| 小程序页面 | 后端 API |
|-----------|---------|
| 对话 | `POST /api/v1/chat/sessions/{id}/message` |
| 创作 | `POST /api/v1/content/create` |
| 历史 | `GET /api/v1/content/history` |
| 详情 | `GET /api/v1/content/record/{id}` |
| 登录 | `POST /api/v1/auth/wx-login` |
| 封面图 | `POST /api/v1/content/generate-cover` |

### 封面图生成：图片在哪、如何返回、是否下载到本地

生成封面图后的数据流如下。

1. **后端保存位置（服务器）**  
   图片保存在**运行后端的机器**上（本地开发时就是你的电脑）：
   - 目录：`iccp-langchain/static/generated-covers/`
   - 文件名：`cover_<uuid>.png`
   - 通过 FastAPI 的 `/static` 路由对外提供访问。

2. **如何返回前端**  
   - 接口返回：`image_url: "/static/generated-covers/cover_xxx.png"`（相对路径）。  
   - 小程序里用 `utils/api.js` 的 `toAbsoluteApiUrl()` 转成完整地址，例如：  
     `http://你的后端地址:8000/static/generated-covers/cover_xxx.png`。  
   - 页面用 `<image src="{{result.imageUrl}}">` 显示时，是**直接请求这个 URL**，从服务器拉图显示，**不会**自动存到手机或电脑。

3. **会不会下载到本地？**  
   - **不会自动下载**。  
   - **手机**：只有用户点击「保存到相册」时，小程序会先通过 `wx.getImageInfo` 把该网络图片下载到手机临时目录，再调用 `wx.saveImageToPhotosAlbum` 写入系统相册，此时图片才在**手机本地**。  
   - **电脑**：图片只在后端所在电脑的 `static/generated-covers/` 目录里；开发者用浏览器或开发者工具打开页面时，只是从本机服务器加载显示，不会自动下载到“我的电脑”的某个文件夹，除非你手动另存或后端另有下载逻辑。

总结：图片物理位置在**后端机器的磁盘**；前端是**按 URL 在线显示**；只有用户点「保存到相册」时才会在**手机**上存一份到相册。

### 后端改动清单

| 文件 | 改动 |
|------|------|
| `app/config.py` | 新增 `WX_APPID`、`WX_SECRET` |
| `app/models/user.py` | User 模型新增 `wx_openid` 字段 |
| `app/api/v1/wx_auth.py` | 新增微信 code2session 登录接口 |
| `app/main.py` | 注册 `wx_auth.router` 路由 |
