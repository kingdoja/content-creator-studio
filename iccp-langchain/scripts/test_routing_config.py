"""
测试路由配置加载功能
"""
import sys
from pathlib import Path

# 确保可以导入 app 模块
sys.path.insert(0, str(Path(__file__).parent))

from app.config import routing_config

def test_load_config():
    """测试从 YAML 文件加载配置"""
    config_path = Path(__file__).parent / "app" / "config" / "routing_config.yaml"
    
    print(f"配置文件路径: {config_path}")
    print(f"文件存在: {config_path.exists()}")
    
    try:
        config = routing_config.load_routing_config(config_path)
        print(f"\n✓ 配置加载成功!")
        print(f"  - 策略总数: {len(config.strategies)}")
        print(f"  - 已启用策略: {len(config.enabled_strategies_by_priority())}")
        print(f"  - 配置来源: {config.source_path}")
        
        print("\n策略列表:")
        for s in config.enabled_strategies_by_priority():
            print(f"  [{s.priority:3d}] {s.name:30s} -> {s.agent:10s} ({s.description})")
        
        return True
    except routing_config.ConfigurationError as e:
        print(f"\n✗ 配置加载失败: {e}")
        return False

def test_build_strategies():
    """测试从配置构建策略实例"""
    config_path = Path(__file__).parent / "app" / "config" / "routing_config.yaml"
    
    try:
        config = routing_config.load_routing_config(config_path)
        strategies = routing_config.build_strategies_from_config(config)
        
        print(f"\n✓ 策略实例构建成功!")
        print(f"  - 策略实例数: {len(strategies)}")
        
        print("\n策略实例:")
        for i, strategy in enumerate(strategies):
            print(f"  [{i}] {type(strategy).__name__:30s} -> {strategy.agent_name()}")
        
        return True
    except Exception as e:
        print(f"\n✗ 策略构建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_router_from_config():
    """测试从配置文件构建路由器"""
    try:
        from app.agents.router_v2 import AgentRouterV2
        
        config_path = Path(__file__).parent / "app" / "config" / "routing_config.yaml"
        router = AgentRouterV2.from_config(config_path)
        
        print(f"\n✓ 路由器构建成功!")
        print(f"  - 策略数量: {len(router._strategies)}")
        
        return True
    except Exception as e:
        print(f"\n✗ 路由器构建失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 70)
    print("测试配置驱动的路由规则")
    print("=" * 70)
    
    success = True
    
    print("\n[测试 1] 加载 YAML 配置")
    print("-" * 70)
    success &= test_load_config()
    
    print("\n[测试 2] 构建策略实例")
    print("-" * 70)
    success &= test_build_strategies()
    
    print("\n[测试 3] 从配置构建路由器")
    print("-" * 70)
    success &= test_router_from_config()
    
    print("\n" + "=" * 70)
    if success:
        print("✓ 所有测试通过!")
    else:
        print("✗ 部分测试失败")
    print("=" * 70)
