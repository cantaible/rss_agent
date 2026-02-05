import sqlite3
from datetime import datetime

DB_FILE = "rss_agent.db"

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
    
    conn.commit()
    conn.close()
    print("✅ Database initialized.")

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

def save_cached_news(category, content, date_str):
    """保存新闻缓存"""
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''
        INSERT OR REPLACE INTO daily_news_cache (category, content, generated_at, date)
        VALUES (?, ?, ?, ?)
    ''', (category, content, datetime.now(), date_str))
    conn.commit()
    conn.close()

def get_cached_news(category, date_str):
    """读取新闻缓存"""
    conn = sqlite3.connect(DB_FILE)
    row = conn.execute(
        'SELECT content FROM daily_news_cache WHERE category = ? AND date = ?',
        (category, date_str)
    ).fetchone()
    conn.close()
    return row[0] if row else None

if __name__ == "__main__":
    init_db()
