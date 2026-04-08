# Scripts Directory

## 概述

此目录包含用于开发、测试和验证的脚本工具。这些脚本不是正式测试套件的一部分，而是用于快速验证、基准测试和演示。

## 脚本分类

### 验证脚本

#### verify_routing.py
验证路由配置和策略匹配逻辑。

**用途**：
- 检查路由配置文件格式
- 验证策略优先级
- 测试路由决策

**运行**：
```bash
python scripts/verify_routing.py
```

### 测试脚本（快速验证）

#### test_adapter_simple.py
简单的适配器功能测试，无需完整环境。

**特点**：
- 最小依赖
- 快速执行
- 适合 CI/CD

**运行**：
```bash
python scripts/test_adapter_simple.py
```

#### test_routing_simple.py
路由配置的简单验证测试。

**运行**：
```bash
python scripts/test_routing_simple.py
```

#### test_routing_config.py
路由配置加载和验证测试。

**运行**：
```bash
python scripts/test_routing_config.py
```

#### test_config_integration.py
配置系统集成测试。

**运行**：
```bash
python scripts/test_config_integration.py
```

#### test_api.py
API 端点快速测试。

**运行**：
```bash
python scripts/test_api.py
```

#### test_graph.py
LangGraph 编排快速测试。

**运行**：
```bash
python scripts/test_graph.py
```

### 基准测试

#### benchmark_rag_search.py
RAG 检索性能基准测试。

**用途**：
- 测试检索速度
- 比较不同配置
- 性能优化参考

**运行**：
```bash
python scripts/benchmark_rag_search.py
```

## 脚本 vs 正式测试

| 特性 | Scripts | Tests (tests/) |
|------|---------|----------------|
| 目的 | 快速验证、演示 | 正式测试套件 |
| 依赖 | 最小化 | 完整环境 |
| 执行 | 手动运行 | CI/CD 自动运行 |
| 覆盖率 | 不计入 | 计入覆盖率 |
| 维护 | 可选 | 必须 |

## 使用场景

### 开发阶段
- 快速验证新功能
- 调试特定组件
- 性能测试

### 演示
- 展示功能
- 生成示例输出
- 文档截图

### CI/CD
- 预检查（在完整测试前）
- 配置验证
- 快速反馈

## 注意事项

1. **不要依赖外部服务**：脚本应该能在本地独立运行
2. **最小依赖**：只依赖核心库，避免复杂依赖
3. **清晰输出**：提供易读的输出和错误信息
4. **文档化**：每个脚本应有清晰的注释说明用途

## 添加新脚本

创建新脚本时，请遵循以下模板：

```python
"""
脚本名称和用途的简短描述

Usage:
    python scripts/your_script.py [options]

Requirements:
    - 列出必需的依赖
    - 列出必需的环境变量

Example:
    python scripts/your_script.py --option value
"""

def main():
    """主函数"""
    print("=" * 60)
    print("脚本名称")
    print("=" * 60)
    
    # 你的代码
    
    print("\n✓ 完成")

if __name__ == "__main__":
    main()
```

## 相关文档

- [测试目录说明](../tests/README.md)
- [项目结构优化建议](../docs/项目结构优化建议.md)
