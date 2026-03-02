# ICCP LangChain - 完整使用指南

## 项目结构

```
iccp-langchain/
├── app/                    # FastAPI后端
├── frontend/               # React前端
└── static/                 # 静态HTML（备用）
```

## 完整启动流程

### 方式1：React前端（推荐）

#### 1. 启动后端
```bash
conda activate opc
cd iccp-langchain
python -m app.main
# 后端运行在 http://localhost:8000
```

#### 2. 启动前端（新终端）
```bash
conda activate opc
cd iccp-langchain/frontend
# npm install
npm run dev
# 前端运行在 http://localhost:3000
```

#### 3. 访问
打开浏览器访问：http://localhost:3000

#### 4. Docker 启动前端（可选）

先按上面步骤启动后端（`http://localhost:8000`），然后在 `iccp-langchain` 目录执行：

**开发模式（热更新）**
```bash
cd iccp-langchain
docker build -t iccp-frontend:dev -f ./frontend/Dockerfile.dev ./frontend
docker run --rm -it --name iccp-frontend-dev \
  -p 3000:3000 \
  -v "$(pwd)/frontend:/app" \
  -v /app/node_modules \
  -e VITE_API_BASE_URL=http://host.docker.internal:8000 \
  iccp-frontend:dev
# 前端访问 http://localhost:3000
```

**生产模式（Nginx 托管构建产物）**
```bash
cd iccp-langchain
docker build -t iccp-frontend:prod \
  --build-arg VITE_API_BASE_URL=https://your-backend-domain.com \
  ./frontend
docker run -d --name iccp-frontend -p 3000:80 iccp-frontend:prod
# 前端访问 http://localhost:3000
```

**停止容器**
```bash
docker stop iccp-frontend-dev 2>/dev/null || true
docker stop iccp-frontend 2>/dev/null || true
docker rm iccp-frontend-dev iccp-frontend 2>/dev/null || true
```

#### 5. Docker Compose 一键启动前后端（前后端分离）

在 `iccp-langchain` 目录执行：

```bash
cd iccp-langchain

# 可选：指定打包到前端里的后端地址（浏览器实际访问地址）
# 不设置时默认 http://localhost:8000
export FRONTEND_API_BASE_URL=http://localhost:8000

docker compose up -d --build
docker compose ps
```

访问地址：
- 前端：http://localhost:3000
- 后端：http://localhost:8000

常用命令：

```bash
# 查看日志
docker compose logs -f

# 停止并删除容器（保留 Redis 数据卷）
docker compose down

# 停止并删除容器 + Redis 数据卷
docker compose down -v
```

### 方式2：静态HTML（简单）

```bash
cd iccp-langchain
python -m app.main
# 访问 http://localhost:8000
```

## React前端特性

- ✅ 现代化UI设计
- ✅ 响应式布局
- ✅ 组件化架构
- ✅ 状态管理
- ✅ 错误处理
- ✅ 加载状态
- ✅ Agent建议功能

## 对比

| 特性 | React前端 | 静态HTML |
|------|-----------|----------|
| UI美观度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 交互体验 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 开发效率 | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| 部署复杂度 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 适合场景 | 生产环境 | 快速演示 |

## 推荐使用

- **开发/生产**：使用React前端
- **快速测试**：使用静态HTML
