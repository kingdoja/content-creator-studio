"""
清理 user_preferences 表中的重复记录

这个脚本会:
1. 找出所有重复的 (user_id, preference_key) 组合
2. 保留每组中最新的记录 (根据 updated_at)
3. 删除其他重复记录
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.memory import UserPreference


async def find_duplicates(db: AsyncSession):
    """查找重复的记录"""
    stmt = (
        select(
            UserPreference.user_id,
            UserPreference.preference_key,
            func.count(UserPreference.id).label('count')
        )
        .group_by(UserPreference.user_id, UserPreference.preference_key)
        .having(func.count(UserPreference.id) > 1)
    )
    
    result = await db.execute(stmt)
    duplicates = result.all()
    return duplicates


async def clean_duplicates():
    """清理重复记录"""
    async with AsyncSessionLocal() as db:
        # 1. 查找重复记录
        duplicates = await find_duplicates(db)
        
        if not duplicates:
            print("✅ 没有发现重复记录")
            return
        
        print(f"⚠️  发现 {len(duplicates)} 组重复记录:")
        for user_id, pref_key, count in duplicates:
            print(f"  - user_id={user_id}, key={pref_key}, count={count}")
        
        # 2. 对每组重复记录,保留最新的,删除其他的
        total_deleted = 0
        for user_id, pref_key, count in duplicates:
            # 获取该组的所有记录,按更新时间降序排列
            stmt = (
                select(UserPreference)
                .where(
                    UserPreference.user_id == user_id,
                    UserPreference.preference_key == pref_key
                )
                .order_by(UserPreference.updated_at.desc())
            )
            result = await db.execute(stmt)
            records = result.scalars().all()
            
            # 保留第一条(最新的),删除其他的
            if len(records) > 1:
                keep_id = records[0].id
                delete_ids = [r.id for r in records[1:]]
                
                # 删除旧记录
                delete_stmt = delete(UserPreference).where(
                    UserPreference.id.in_(delete_ids)
                )
                result = await db.execute(delete_stmt)
                deleted_count = result.rowcount
                total_deleted += deleted_count
                
                print(f"  ✓ 保留 id={keep_id}, 删除 {deleted_count} 条旧记录")
        
        # 3. 提交事务
        await db.commit()
        
        print(f"\n✅ 清理完成! 共删除 {total_deleted} 条重复记录")
        
        # 4. 验证
        remaining_duplicates = await find_duplicates(db)
        if remaining_duplicates:
            print(f"⚠️  警告: 仍有 {len(remaining_duplicates)} 组重复记录")
        else:
            print("✅ 验证通过: 没有重复记录了")


async def add_unique_constraint_info():
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

然后创建数据库迁移来应用这个约束。
""")


if __name__ == "__main__":
    print("开始清理重复的 user_preferences 记录...\n")
    asyncio.run(clean_duplicates())
    asyncio.run(add_unique_constraint_info())
