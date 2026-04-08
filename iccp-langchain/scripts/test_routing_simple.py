"""
简单测试：验证配置文件格式和内容
Requirements: 7.1, 7.5
"""
import yaml
from pathlib import Path

def main():
    print("=" * 70)
    print("配置驱动路由规则 - 验证测试")
    print("=" * 70)
    
    config_path = Path("app/config/routing_config.yaml")
    
    # 1. 文件存在性
    print(f"\n[1] 检查配置文件")
    print(f"    路径: {config_path}")
    if not config_path.exists():
        print(f"    ✗ 文件不存在")
        return False
    print(f"    ✓ 文件存在")
    
    # 2. YAML 解析
    print(f"\n[2] 解析 YAML")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        print(f"    ✓ YAML 格式正确")
    except Exception as e:
        print(f"    ✗ YAML 解析失败: {e}")
        return False
    
    # 3. 结构验证
    print(f"\n[3] 验证配置结构")
    if 'strategies' not in data:
        print(f"    ✗ 缺少 'strategies' 字段")
        return False
    
    strategies = data['strategies']
    if not isinstance(strategies, list):
        print(f"    ✗ 'strategies' 必须是列表")
        return False
    
    if len(strategies) == 0:
        print(f"    ✗ 'strategies' 列表为空")
        return False
    
    print(f"    ✓ 包含 {len(strategies)} 个策略")
    
    # 4. 策略字段验证
    print(f"\n[4] 验证策略字段")
    valid_names = {
        "SimpleQAStrategy",
        "KnowledgeStrategy",
        "RealtimeStrategy",
        "HighQualityStrategy",
        "MediumReflectionStrategy",
        "DefaultStrategy",
    }
    valid_agents = {"simple", "react", "reflection"}
    
    has_default = False
    errors = []
    
    for i, s in enumerate(strategies):
        # 必填字段
        if 'name' not in s:
            errors.append(f"strategies[{i}] 缺少 'name' 字段")
            continue
        if 'agent' not in s:
            errors.append(f"strategies[{i}] 缺少 'agent' 字段")
            continue
        if 'priority' not in s:
            errors.append(f"strategies[{i}] 缺少 'priority' 字段")
            continue
        
        name = s['name']
        agent = s['agent']
        priority = s['priority']
        enabled = s.get('enabled', True)
        
        # 验证值
        if name not in valid_names:
            errors.append(f"strategies[{i}].name={name!r} 不是合法的策略名称")
        if agent not in valid_agents:
            errors.append(f"strategies[{i}].agent={agent!r} 不是合法的 agent 名称")
        if not isinstance(priority, int):
            errors.append(f"strategies[{i}].priority 必须是整数")
        if not isinstance(enabled, bool):
            errors.append(f"strategies[{i}].enabled 必须是布尔值")
        
        if name == "DefaultStrategy" and enabled:
            has_default = True
    
    if errors:
        print(f"    ✗ 发现 {len(errors)} 个错误:")
        for err in errors:
            print(f"      - {err}")
        return False
    
    print(f"    ✓ 所有策略字段验证通过")
    
    # 5. 兜底策略验证
    print(f"\n[5] 验证兜底策略")
    if not has_default:
        print(f"    ✗ 缺少已启用的 DefaultStrategy")
        return False
    print(f"    ✓ 包含已启用的 DefaultStrategy")
    
    # 6. 优先级排序验证
    print(f"\n[6] 验证优先级排序")
    enabled_strategies = [s for s in strategies if s.get('enabled', True)]
    priorities = [s['priority'] for s in enabled_strategies]
    
    print(f"    已启用策略优先级: {priorities}")
    
    if priorities != sorted(priorities):
        print(f"    ⚠ 建议按优先级升序排列（当前未排序）")
    else:
        print(f"    ✓ 已按优先级升序排列")
    
    # 7. 打印配置摘要
    print(f"\n[7] 配置摘要")
    print(f"    {'优先级':<10} {'策略名称':<30} {'目标Agent':<12} {'状态'}")
    print(f"    {'-'*10} {'-'*30} {'-'*12} {'-'*6}")
    for s in sorted(strategies, key=lambda x: x['priority']):
        enabled = s.get('enabled', True)
        status = "启用" if enabled else "禁用"
        print(f"    {s['priority']:<10} {s['name']:<30} {s['agent']:<12} {status}")
    
    print("\n" + "=" * 70)
    print("✓ 配置验证通过!")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
