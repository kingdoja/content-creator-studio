# Tests Directory

## 目录结构

```
tests/
├── unit/                    # 单元测试
│   └── (待整理)
├── integration/             # 集成测试
│   └── (待整理)
├── legacy/                  # 遗留测试（新架构相关）
│   ├── test_legacy_adapter.py
│   └── test_feature_flag.py
├── test_auth.py            # 认证测试
├── test_content_access.py  # 内容访问测试
├── test_evaluation.py      # 评估测试
├── test_memory_*.py        # 记忆系统测试
├── test_observability.py   # 可观测性测试
└── conftest.py             # pytest 配置
```

## 测试分类

### 单元测试 (unit/)
测试单个函数、类或模块的功能。

**特点**：
- 快速执行
- 无外部依赖
- 使用 Mock 对象

**示例**：
- 领域模型测试
- 路由策略测试
- 工具函数测试

### 集成测试 (integration/)
测试多个组件协作的功能。

**特点**：
- 涉及多个模块
- 可能需要数据库
- 测试真实交互

**示例**：
- API 端点测试
- 服务层测试
- 数据库操作测试

### 遗留测试 (legacy/)
与新架构迁移相关的测试。

**包含**：
- 适配器测试
- 特性开关测试
- 兼容性测试

## 运行测试

### 运行所有测试
```bash
pytest tests/
```

### 运行特定类型测试
```bash
# 单元测试
pytest tests/unit/

# 集成测试
pytest tests/integration/

# 遗留测试
pytest tests/legacy/
```

### 运行单个测试文件
```bash
pytest tests/test_auth.py
```

### 带覆盖率报告
```bash
pytest tests/ --cov=app --cov-report=html
```

## 测试命名规范

- **文件名**：`test_<module>.py`
- **类名**：`Test<Feature>`
- **函数名**：`test_<scenario>`

**示例**：
```python
# tests/unit/test_strategies.py
class TestSimpleQAStrategy:
    def test_matches_simple_query(self):
        ...
    
    def test_does_not_match_complex_query(self):
        ...
```

## 待整理任务

### 需要移动到 unit/
- [ ] 领域模型测试
- [ ] 策略测试
- [ ] 工具测试

### 需要移动到 integration/
- [ ] API 测试
- [ ] 服务层测试
- [ ] 端到端测试

## 测试覆盖率目标

- **单元测试**：80%+
- **集成测试**：60%+
- **总体覆盖率**：75%+

## 相关文档

- [测试策略](../docs/架构重构总结.md#测试策略)
- [项目结构优化建议](../docs/项目结构优化建议.md)
