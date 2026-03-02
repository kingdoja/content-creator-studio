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
