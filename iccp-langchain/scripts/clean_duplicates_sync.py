"""
清理 user_preferences 表中的重复记录 (同步版本)
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.config.settings import settings


def clean_duplicates():
    """清理重复记录"""
    # 使用同步引擎
    engine = create_engine(settings.DATABASE_SYNC_URL)
    
    with engine.connect() as conn:
        # 1. 查找重复记录
        print("查找重复记录...")
        result = conn.execute(text("""
            SELECT user_id, preference_key, COUNT(*) as count
            FROM user_preferences
            GROUP BY user_id, preference_key
            HAVING COUNT(*) > 1
        """))
        
        duplicates = result.fetchall()
        
        if not duplicates:
            print("✅ 没有发现重复记录")
            return
        
        print(f"⚠️  发现 {len(duplicates)} 组重复记录:")
        for row in duplicates:
            print(f"  - user_id={row[0]}, key={row[1]}, count={row[2]}")
        
        # 2. 删除重复记录 (保留最新的)
        print("\n开始清理...")
        
        # SQLite 版本 (不支持 ROW_NUMBER)
        if 'sqlite' in settings.DATABASE_SYNC_URL:
            total_deleted = 0
            for user_id, pref_key, count in duplicates:
                # 获取该组的所有 ID,按更新时间降序
                result = conn.execute(text("""
                    SELECT id FROM user_preferences
                    WHERE user_id = :user_id AND preference_key = :pref_key
                    ORDER BY updated_at DESC
                """), {"user_id": user_id, "pref_key": pref_key})
                
                ids = [row[0] for row in result.fetchall()]
                
                if len(ids) > 1:
                    # 保留第一个,删除其他的
                    keep_id = ids[0]
                    delete_ids = ids[1:]
                    
                    result = conn.execute(text("""
                        DELETE FROM user_preferences
                        WHERE id IN :ids
                    """), {"ids": tuple(delete_ids)})
                    
                    deleted = result.rowcount
                    total_deleted += deleted
                    print(f"  ✓ 保留 id={keep_id}, 删除 {deleted} 条旧记录")
            
            conn.commit()
            print(f"\n✅ 清理完成! 共删除 {total_deleted} 条重复记录")
        
        else:
            # PostgreSQL 版本 (支持 ROW_NUMBER)
            result = conn.execute(text("""
                DELETE FROM user_preferences
                WHERE id NOT IN (
                    SELECT id FROM (
                        SELECT id, 
                               ROW_NUMBER() OVER (
                                   PARTITION BY user_id, preference_key 
                                   ORDER BY updated_at DESC
                               ) as rn
                        FROM user_preferences
                    ) t
                    WHERE t.rn = 1
                )
            """))
            
            conn.commit()
            deleted = result.rowcount
            print(f"\n✅ 清理完成! 共删除 {deleted} 条重复记录")
        
        # 3. 验证
        print("\n验证清理结果...")
        result = conn.execute(text("""
            SELECT user_id, preference_key, COUNT(*) as count
            FROM user_preferences
            GROUP BY user_id, preference_key
            HAVING COUNT(*) > 1
        """))
        
        remaining = result.fetchall()
        if remaining:
            print(f"⚠️  警告: 仍有 {len(remaining)} 组重复记录")
        else:
            print("✅ 验证通过: 没有重复记录了")


def show_constraint_info():
    """显示如何添加唯一约束的信息"""
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


if __name__ == "__main__":
    print("开始清理重复的 user_preferences 记录...\n")
    try:
        clean_duplicates()
        show_constraint_info()
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
