-- 清理 user_preferences 表中的重复记录
-- 保留每组 (user_id, preference_key) 中 updated_at 最新的记录

-- 1. 查看重复记录
SELECT user_id, preference_key, COUNT(*) as count
FROM user_preferences
GROUP BY user_id, preference_key
HAVING COUNT(*) > 1;

-- 2. 删除重复记录 (保留最新的)
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
);

-- 3. 验证清理结果
SELECT user_id, preference_key, COUNT(*) as count
FROM user_preferences
GROUP BY user_id, preference_key
HAVING COUNT(*) > 1;
