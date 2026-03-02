# ICCP Frontend - React前端

基于React + Vite + TailwindCSS的现代化前端界面，用于连接FastAPI后端。

## 功能特性

- ✅ 现代化的React Hooks架构
- ✅ 响应式设计（TailwindCSS）
- ✅ 美观的UI界面
- ✅ 实时加载状态
- ✅ 错误处理
- ✅ Agent建议功能
- ✅ 一键复制内容

## 技术栈

- **React 18** - UI框架
- **Vite** - 构建工具
- **TailwindCSS** - 样式框架
- **Axios** - HTTP客户端
- **Lucide React** - 图标库

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 配置环境变量（可选）

复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

如果后端运行在不同端口，修改 `VITE_API_BASE_URL`。

### 3. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:3000

### 4. 构建生产版本

```bash
npm run build
```

构建文件在 `dist/` 目录。

## 项目结构

```
frontend/
├── src/
│   ├── components/          # React组件
│   │   ├── ContentCreator.jsx    # 主内容创作组件
│   │   ├── CategorySelect.jsx    # 板块选择组件
│   │   ├── ResultDisplay.jsx     # 结果显示组件
│   │   ├── LoadingSpinner.jsx    # 加载动画组件
│   │   ├── ErrorMessage.jsx       # 错误提示组件
│   │   └── Header.jsx             # 头部组件
│   ├── services/            # API服务
│   │   └── api.js           # API调用封装
│   ├── App.jsx              # 主应用组件
│   ├── main.jsx             # 入口文件
│   └── index.css            # 全局样式
├── index.html               # HTML模板
├── vite.config.js           # Vite配置
├── tailwind.config.js       # Tailwind配置
└── package.json             # 依赖配置
```

## 使用说明

1. **确保后端服务运行**
   ```bash
   # 在另一个终端
   cd ..
   python -m app.main
   ```

2. **启动前端**
   ```bash
   npm run dev
   ```

3. **使用界面**
   - 选择内容板块
   - 输入主题
   - 可选：添加额外要求
   - 选择长度和风格
   - 点击"开始创作"
   - 查看生成结果

## 开发

### 添加新功能

1. 在 `src/components/` 创建新组件
2. 在 `src/services/api.js` 添加API调用
3. 在 `ContentCreator.jsx` 中集成

### 样式定制

修改 `tailwind.config.js` 中的主题配置。

## 部署

### 开发环境
- 前端：`npm run dev` (localhost:3000)
- 后端：`python -m app.main` (localhost:8000)
- Vite代理自动处理跨域

### 生产环境

1. **构建前端**
   ```bash
   npm run build
   ```

2. **部署选项**
   - 选项1：部署到Nginx/CDN，后端单独部署
   - 选项2：将dist目录放到FastAPI的static目录
   - 选项3：使用Docker部署

## 注意事项

- 确保后端CORS配置允许前端域名
- 开发时使用Vite代理避免跨域问题
- 生产环境需要配置正确的API URL
