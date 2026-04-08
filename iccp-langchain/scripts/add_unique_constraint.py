"""
为 user_preferences 表添加唯一约束

这个脚本会在数据库中添加 UNIQUE 约束,防止未来出现重复的 (user_id, preference_key) 记录
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
    # 检查约束是否已存在
    cursor.execute("""
        SELECT sql FROM sqlite_master 
        WHERE type='table' AND name='user_preferences'
    """)
    
    table_sql = cursor.fetchone()[0]
    
    if 'uq_user_preference' in table_sql or 'UNIQUE' in table_sql:
        print("✅ 唯一约束已存在,无需添加")
        conn.close()
        exit(0)
    
    print("为 user_preferences 表添加唯一约束...")
    print("注意: SQLite 需要重建表来添加约束\n")
    
    # SQLite 不支持直接 ALTER TABLE ADD CONSTRAINT
    # 需要重建表
    
    # 1. 创建新表 (带约束)
    cursor.execute("""
        CREATE TABLE user_preferences_new (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'anonymous',
            preference_key TEXT NOT NULL,
            preference_value TEXT DEFAULT '',
            confidence REAL DEFAULT 0.5,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, preference_key)
        )
    """)
    
    # 2. 复制数据
    cursor.execute("""
        INSERT INTO user_preferences_new 
        SELECT id, user_id, preference_key, preference_value, confidence, updated_at
        FROM user_preferences
    """)
    
    # 3. 删除旧表
    cursor.execute("DROP TABLE user_preferences")
    
    # 4. 重命名新表
    cursor.execute("ALTER TABLE user_preferences_new RENAME TO user_preferences")
    
    # 5. 重建索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_user_preferences_user_id 
        ON user_preferences(user_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS ix_user_preferences_preference_key 
        ON user_preferences(preference_key)
    """)
    
    # 提交事务
    conn.commit()
    
    print("✅ 唯一约束添加成功!")
    print("\n现在 (user_id, preference_key) 组合必须唯一")
    
    # 验证
    cursor.execute("""
        SELECT sql FROM sqlite_master 
        WHERE type='table' AND name='user_preferences'
    """)
    
    new_table_sql = cursor.fetchone()[0]
    print("\n新表结构:")
    print(new_table_sql)

except Exception as e:
    print(f"❌ 错误: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()

finally:
    conn.close()
