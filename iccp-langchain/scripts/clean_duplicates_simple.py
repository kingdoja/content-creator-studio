"""
清理 user_preferences 表中的重复记录 (最简单版本)
直接使用 sqlite3
"""
import sqlite3
from pathlib import Path

# 数据库文件路径
db_path = Path(__file__).parent.parent / "iccp.db"

if not db_path.exists():
    print(f"❌ 数据库文件不存在: {db_path}")
    exit(1)

print(f"连接数据库: {db_path}\n")

# 连接数据库
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

try:
    # 1. 查找重复记录
    print("查找重复记录...")
    cursor.execute("""
        SELECT user_id, preference_key, COUNT(*) as count
        FROM user_preferences
        GROUP BY user_id, preference_key
        HAVING COUNT(*) > 1
    """)
    
    duplicates = cursor.fetchall()
    
    if not duplicates:
        print("✅ 没有发现重复记录")
        conn.close()
        exit(0)
    
    print(f"⚠️  发现 {len(duplicates)} 组重复记录:")
    for user_id, pref_key, count in duplicates:
        print(f"  - user_id={user_id}, key={pref_key}, count={count}")
    
    # 2. 删除重复记录 (保留最新的)
    print("\n开始清理...")
    total_deleted = 0
    
    for user_id, pref_key, count in duplicates:
        # 获取该组的所有 ID,按更新时间降序
        cursor.execute("""
            SELECT id FROM user_preferences
            WHERE user_id = ? AND preference_key = ?
            ORDER BY updated_at DESC
        """, (user_id, pref_key))
        
        ids = [row[0] for row in cursor.fetchall()]
        
        if len(ids) > 1:
            # 保留第一个,删除其他的
            keep_id = ids[0]
            delete_ids = ids[1:]
            
            placeholders = ','.join('?' * len(delete_ids))
            cursor.execute(f"""
                DELETE FROM user_preferences
                WHERE id IN ({placeholders})
            """, delete_ids)
            
            deleted = cursor.rowcount
            total_deleted += deleted
            print(f"  ✓ 保留 id={keep_id}, 删除 {deleted} 条旧记录")
    
    # 提交事务
    conn.commit()
    print(f"\n✅ 清理完成! 共删除 {total_deleted} 条重复记录")
    
    # 3. 验证
    print("\n验证清理结果...")
    cursor.execute("""
        SELECT user_id, preference_key, COUNT(*) as count
        FROM user_preferences
        GROUP BY user_id, preference_key
        HAVING COUNT(*) > 1
    """)
    
    remaining = cursor.fetchall()
    if remaining:
        print(f"⚠️  警告: 仍有 {len(remaining)} 组重复记录")
    else:
        print("✅ 验证通过: 没有重复记录了")

except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()

finally:
    conn.close()

print("\n" + "="*60)
print("建议: 添加唯一约束防止未来出现重复")
print("="*60)
print("""
在 app/models/memory.py 的 UserPreference 类中添加:

from sqlalchemy import UniqueConstraint

class UserPreference(Base):
    __tablename__ = "user_preferences"
    
    # ... 现有字段 ...
    
    __table_args__ = (
        UniqueConstraint('user_id', 'preference_key', 
                        name='uq_user_preference'),
    )
""")
