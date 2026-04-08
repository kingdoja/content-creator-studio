"""
集成测试：验证配置驱动的路由规则完整流程
Requirements: 7.1, 7.5
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from app.config import routing_config

def test_config_validation():
    """测试配置验证功能"""
    print("\n[测试 1] 配置文件验证")
    print("-" * 70)
    
    config_path = Path(__file__).parent / "app" / "config" / "routing_config.yaml"
    
    try:
        config = routing_config.load_routing_config(config_path)
        print(f"✓ 配置加载成功")
        print(f"  - 策略总数: {len(config.strategies)}")
        print(f"  - 已启用: {len(config.enabled_strategies_by_priority())}")
        
        # 验证必须有 DefaultStrategy
        has_default = any(
            s.name == "DefaultStrategy" and s.enabled 
            for s in config.strategies
        )
        assert has_default, "必须包含已启用的 DefaultStrategy"
        print(f"  - 包含兜底策略: ✓")
        
        # 验证所有策略名称合法
        for s in config.strategies:
            assert s.name in routing_config.VALID_STRATEGY_NAMES, \
                f"非法策略名称: {s.name}"
            assert s.agent in routing_config.VALID_AGENT_NAMES, \
                f"非法 agent 名称: {s.agent}"
        print(f"  - 策略名称验证: ✓")
        
        return True
    except Exception as e:
        print(f"✗ 配置验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_invalid_config():
    """测试无效配置的错误处理"""
    print("\n[测试 2] 无效配置错误处理")
    print("-" * 70)
    
    import tempfile
    import yaml
    
    # 测试 1: 缺少 strategies 字段
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({"invalid": "config"}, f)
        temp_path = f.name
    
    try:
        routing_config.load_routing_config(temp_path)
        print("✗ 应该抛出 ConfigurationError（缺少 strategies）")
        return False
    except routing_config.ConfigurationError as e:
        print(f"✓ 正确捕获错误: {str(e)[:60]}...")
    finally:
        Path(temp_path).unlink()
    
    # 测试 2: 无效的策略名称
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({
            "strategies": [
                {"name": "InvalidStrategy", "agent": "simple", "priority": 10},
                {"name": "DefaultStrategy", "agent": "react", "priority": 100},
            ]
        }, f)
        temp_path = f.name
    
    try:
        routing_config.load_routing_config(temp_path)
        print("✗ 应该抛出 ConfigurationError（无效策略名）")
        return False
    except routing_config.ConfigurationError as e:
        print(f"✓ 正确捕获错误: {str(e)[:60]}...")
    finally:
        Path(temp_path).unlink()
    
    # 测试 3: 缺少 DefaultStrategy
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({
            "strategies": [
                {"name": "SimpleQAStrategy", "agent": "simple", "priority": 10},
            ]
        }, f)
        temp_path = f.name
    
    try:
        routing_config.load_routing_config(temp_path)
        print("✗ 应该抛出 ConfigurationError（缺少 DefaultStrategy）")
        return False
    except routing_config.ConfigurationError as e:
        print(f"✓ 正确捕获错误: {str(e)[:60]}...")
    finally:
        Path(temp_path).unlink()
    
    return True

def test_strategy_priority():
    """测试策略优先级排序"""
    print("\n[测试 3] 策略优先级排序")
    print("-" * 70)
    
    config_path = Path(__file__).parent / "app" / "config" / "routing_config.yaml"
    
    try:
        config = routing_config.load_routing_config(config_path)
        strategies = config.enabled_strategies_by_priority()
        
        # 验证按优先级升序排列
        priorities = [s.priority for s in strategies]
        assert priorities == sorted(priorities), "策略未按优先级排序"
        print(f"✓ 策略按优先级排序")
        
        # 打印排序结果
        for s in strategies:
            print(f"  [{s.priority:3d}] {s.name:30s} -> {s.agent}")
        
        # 验证 DefaultStrategy 优先级最低（最后匹配）
        assert strategies[-1].name == "DefaultStrategy", \
            "DefaultStrategy 应该优先级最低"
        print(f"✓ DefaultStrategy 优先级最低（兜底）")
        
        return True
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """运行所有测试"""
    print("=" * 70)
    print("配置驱动路由规则 - 集成测试")
    print("=" * 70)
    
    results = []
    
    results.append(("配置文件验证", test_config_validation()))
    results.append(("无效配置错误处理", test_invalid_config()))
    results.append(("策略优先级排序", test_strategy_priority()))
    
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{status:8s} - {name}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ 所有测试通过!")
    else:
        print("✗ 部分测试失败")
    print("=" * 70)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit(main())
