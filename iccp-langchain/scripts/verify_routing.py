"""简单验证路由配置"""
import yaml
from pathlib import Path

config_path = Path("app/config/routing_config.yaml")

print("=" * 70)
print("验证路由配置文件")
print("=" * 70)

# 1. 检查文件存在
print(f"\n[1] 配置文件: {config_path}")
print(f"    存在: {config_path.exists()}")

if not config_path.exists():
    print("    ✗ 文件不存在!")
    exit(1)

# 2. 解析 YAML
print(f"\n[2] 解析 YAML")
try:
    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    print(f"    ✓ YAML 解析成功")
except Exception as e:
    print(f"    ✗ YAML 解析失败: {e}")
    exit(1)

# 3. 验证结构
print(f"\n[3] 验证配置结构")
if 'strategies' not in data:
    print(f"    ✗ 缺少 'strategies' 字段")
    exit(1)

strategies = data['strategies']
print(f"    ✓ 策略数量: {len(strategies)}")

# 4. 验证每个策略
print(f"\n[4] 验证策略配置")
valid_strategy_names = {
    "SimpleQAStrategy",
    "KnowledgeStrategy",
    "RealtimeStrategy",
    "HighQualityStrategy",
    "MediumReflectionStrategy",
    "DefaultStrategy",
}
valid_agents = {"simple", "react", "reflection"}

has_default = False
for i, s in enumerate(strategies):
    name = s.get('name', '<missing>')
    agent = s.get('agent', '<missing>')
    priority = s.get('priority', '<missing>')
    enabled = s.get('enabled', True)
    
    print(f"    [{i}] {name:30s} -> {agent:10s} (priority={priority}, enabled={enabled})")
    
    # 验证字段
    if name not in valid_strategy_names:
        print(f"        ✗ 无效的策略名称: {name}")
    if agent not in valid_agents:
        print(f"        ✗ 无效的 agent: {agent}")
    if not isinstance(priority, int):
        print(f"        ✗ priority 必须是整数")
    
    if name == "DefaultStrategy" and enabled:
        has_default = True

# 5. 验证必须有 DefaultStrategy
print(f"\n[5] 验证兜底策略")
if has_default:
    print(f"    ✓ 存在已启用的 DefaultStrategy")
else:
    print(f"    ✗ 缺少已启用的 DefaultStrategy")
    exit(1)

print("\n" + "=" * 70)
print("✓ 配置验证通过!")
print("=" * 70)
