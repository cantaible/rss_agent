import sqlite3
from datetime import datetime
import os
from typing import List, Tuple

# 使用 volume 挂载的 data 目录，确保数据持久化
DB_FILE = os.path.join("/app/data", "rss_agent.db")

def init_db():
    """初始化数据库，创建必要的表"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 创建用户偏好表
    # user_id: 你的 open_id
    # category: AI / GAMES / MUSIC
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            updated_at TIMESTAMP
        )
    ''')
    
    # 缓存新闻内容的表（每天每个类别生成一次）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_news_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            generated_at TIMESTAMP,
            date TEXT NOT NULL,
            UNIQUE(category, date)
        )
    ''')

    # 用户多类别订阅表（允许一个用户关注多个类别）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_subscriptions (
            user_id TEXT NOT NULL,
            category TEXT NOT NULL,
            updated_at TIMESTAMP,
            UNIQUE(user_id, category)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # 尝试添加 briefing_data 列 (如果已存在则忽略)
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute('ALTER TABLE daily_news_cache ADD COLUMN briefing_data TEXT')
        print("✅ Added column 'briefing_data' to daily_news_cache.")
    except sqlite3.OperationalError:
        pass # 列已存在
    conn.close()

    # 幂等迁移：将旧的单值偏好补录到新的多订阅表
    migrate_preferences_to_subscriptions()
    print("✅ Database initialized.")

def migrate_preferences_to_subscriptions():
    """将 user_preferences 的历史数据迁移到 user_subscriptions（幂等）。"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO user_subscriptions (user_id, category, updated_at)
        SELECT user_id, category, COALESCE(updated_at, ?)
        FROM user_preferences
    ''', (datetime.now(),))
    conn.commit()
    conn.close()

def upsert_preference(user_id: str, category: str):
    """更新或插入用户偏好"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_preferences (user_id, category, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            category=excluded.category,
            updated_at=excluded.updated_at
    ''', (user_id, category, datetime.now()))
    conn.commit()
    conn.close()
    return f"Saved: {category}"

def get_preference(user_id: str):
    """查询用户偏好"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT category FROM user_preferences WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def add_subscription(user_id: str, category: str):
    """新增用户订阅（重复订阅同一类别会被忽略）。"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO user_subscriptions (user_id, category, updated_at)
        VALUES (?, ?, ?)
    ''', (user_id, category, datetime.now()))
    inserted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return inserted

def remove_subscription(user_id: str, category: str):
    """取消用户对某类别的订阅。"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        'DELETE FROM user_subscriptions WHERE user_id = ? AND category = ?',
        (user_id, category)
    )
    removed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return removed

def get_subscriptions(user_id: str) -> List[str]:
    """查询用户当前订阅的全部类别。"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT category FROM user_subscriptions WHERE user_id = ? ORDER BY category',
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def list_all_subscriptions() -> List[Tuple[str, str]]:
    """列出所有用户订阅关系（供推送任务遍历）。"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT user_id, category FROM user_subscriptions ORDER BY user_id, category'
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def replace_subscriptions(user_id: str, categories: List[str]):
    """整体替换用户订阅列表。"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now()
    try:
        cursor.execute('BEGIN')
        cursor.execute('DELETE FROM user_subscriptions WHERE user_id = ?', (user_id,))
        cursor.executemany(
            '''
            INSERT OR IGNORE INTO user_subscriptions (user_id, category, updated_at)
            VALUES (?, ?, ?)
            ''',
            [(user_id, category, now) for category in categories]
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def save_cached_news(category, content, date_str, briefing_data=None):
    """保存新闻缓存 (含原始数据)"""
    conn = sqlite3.connect(DB_FILE)
    # Note: briefing_data might be None if saving from legacy logic, handle gracefully?
    # Actually we should enforce it ideally, but let's default to empty JSON '{}' or None
    if briefing_data is None: 
        briefing_data = "{}"
        
    conn.execute('''
        INSERT OR REPLACE INTO daily_news_cache (category, content, generated_at, date, briefing_data)
        VALUES (?, ?, ?, ?, ?)
    ''', (category, content, datetime.now(), date_str, briefing_data))
    conn.commit()
    conn.close()

def get_cached_news(category, date_str):
    """读取新闻缓存 -> (content, briefing_data)"""
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute(
        'SELECT content, briefing_data, generated_at FROM daily_news_cache WHERE category = ? AND date = ?',
        (category, date_str)
    ).fetchone()
    conn.close()
    if row:
        return {
            "content": row[0],
            "briefing_data": row[1],
            "generated_at": row[2] # 新增
        }
    return None

if __name__ == "__main__":
    init_db()
