"""
检查数据库状态
"""
import sqlite3
from pathlib import Path

# 数据库文件路径
db_path = Path(__file__).parent.parent / "iccp.db"

if not db_path.exists():
    print(f"❌ 数据库文件不存在: {db_path}")
    exit(1)

print(f"数据库: {db_path}\n")

# 连接数据库
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

try:
    # 1. 检查表结构
    print("=" * 60)
    print("user_preferences 表结构:")
    print("=" * 60)
    cursor.execute("""
        SELECT sql FROM sqlite_master 
        WHERE type='table' AND name='user_preferences'
    """)
    table_sql = cursor.fetchone()
    if table_sql:
        print(table_sql[0])
    else:
        print("表不存在")
    
    # 2. 检查重复记录
    print("\n" + "=" * 60)
    print("检查重复记录:")
    print("=" * 60)
    cursor.execute("""
        SELECT user_id, preference_key, COUNT(*) as count
        FROM user_preferences
        GROUP BY user_id, preference_key
        HAVING COUNT(*) > 1
    """)
    
    duplicates = cursor.fetchall()
    if duplicates:
        print(f"⚠️  发现 {len(duplicates)} 组重复记录:")
        for user_id, pref_key, count in duplicates:
            print(f"  - user_id={user_id}, key={pref_key}, count={count}")
    else:
        print("✅ 没有重复记录")
    
    # 3. 查看所有记录
    print("\n" + "=" * 60)
    print("所有 user_preferences 记录:")
    print("=" * 60)
    cursor.execute("""
        SELECT user_id, preference_key, preference_value, updated_at
        FROM user_preferences
        ORDER BY user_id, preference_key
    """)
    
    records = cursor.fetchall()
    if records:
        print(f"共 {len(records)} 条记录:")
        for user_id, key, value, updated_at in records:
            print(f"  {user_id} | {key} | {value} | {updated_at}")
    else:
        print("表为空")

except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()

finally:
    conn.close()
