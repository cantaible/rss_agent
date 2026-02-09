#!/usr/bin/env python3
"""
数据库查看工具 - 简化版（无外部依赖）
格式化输出 rss_agent.db 中的所有数据
"""

import sqlite3
import json
import os
from datetime import date

# 数据库文件路径（兼容容器内外）
DB_PATHS = [
    "/app/data/rss_agent.db",  # 容器内
    "./data/rss_agent.db",      # 容器外（项目根目录）
    os.path.expanduser("~/Downloads/rss_agent.db")  # 下载到本地
]

def get_db_path():
    """自动检测数据库文件路径"""
    for path in DB_PATHS:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"数据库文件未找到，尝试过的路径: {DB_PATHS}")

def print_header(title):
    """打印标题"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def print_table(headers, rows, col_widths=None):
    """简单的表格打印"""
    if not col_widths:
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
    
    # 打印表头
    print()
    header_line = "  " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    print(header_line)
    print("  " + "-" * (len(header_line) - 2))
    
    # 打印数据
    for row in rows:
        print("  " + " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)))
    print()

def view_user_preferences(conn):
    """查看用户订阅偏好"""
    print_header("📋 用户订阅偏好 (user_preferences)")
    
    cursor = conn.execute("""
        SELECT user_id, category, updated_at 
        FROM user_preferences 
        ORDER BY updated_at DESC
    """)
    
    rows = cursor.fetchall()
    
    if not rows:
        print("\n  ⚠️  暂无订阅用户\n")
        return
    
    headers = ["User ID", "Category", "Updated At"]
    table_data = []
    
    for row in rows:
        user_id = row[0][:35] + "..." if len(row[0]) > 35 else row[0]
        table_data.append([user_id, row[1], row[2]])
    
    print_table(headers, table_data, [38, 10, 25])
    print(f"  总计: {len(rows)} 个订阅\n")

def view_daily_news_cache(conn):
    """查看每日新闻缓存"""
    print_header("📰 每日新闻缓存 (daily_news_cache)")
    
    cursor = conn.execute("""
        SELECT category, date, generated_at, 
               length(content) as content_size,
               length(briefing_data) as briefing_size
        FROM daily_news_cache 
        ORDER BY date DESC, category
    """)
    
    rows = cursor.fetchall()
    
    if not rows:
        print("\n  ⚠️  暂无缓存数据\n")
        return
    
    headers = ["Category", "Date", "Generated At", "Content", "Briefing"]
    table_data = []
    
    for row in rows:
        table_data.append([
            row[0],
            row[1],
            row[2],
            f"{row[3]:,}B" if row[3] else "N/A",
            f"{row[4]:,}B" if row[4] else "N/A"
        ])
    
    print_table(headers, table_data, [8, 12, 25, 12, 12])
    print(f"  总计: {len(rows)} 条缓存\n")

def view_briefing_details(conn, category=None, target_date=None):
    """查看详细的briefing数据"""
    title = f"📊 Briefing 详情"
    if category:
        title += f" - {category}"
    if target_date:
        title += f" - {target_date}"
    
    print_header(title)
    
    query = "SELECT category, date, briefing_data FROM daily_news_cache WHERE 1=1"
    params = []
    
    if category:
        query += " AND category = ?"
        params.append(category)
    
    if target_date:
        query += " AND date = ?"
        params.append(target_date)
    
    query += " ORDER BY date DESC, category"
    
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    
    if not rows:
        print("\n  ⚠️  未找到匹配的数据\n")
        return
    
    for row in rows:
        cat, dt, briefing_json = row
        
        print(f"\n{'─'*80}")
        print(f"  📂 Category: {cat}")
        print(f"  📅 Date: {dt}")
        print(f"{'─'*80}")
        
        if not briefing_json:
            print("\n  ⚠️  无briefing数据\n")
            continue
        
        try:
            briefing = json.loads(briefing_json)
            
            # 输出摘要
            if 'summary' in briefing:
                print(f"\n  📝 Summary:")
                summary = briefing['summary']
                # 分行显示长摘要
                if len(summary) > 70:
                    words = summary.split()
                    line = "     "
                    for word in words:
                        if len(line) + len(word) > 75:
                            print(line)
                            line = "     " + word + " "
                        else:
                            line += word + " "
                    if line.strip():
                        print(line)
                else:
                    print(f"     {summary}")
            
            # 输出聚类
            if 'clusters' in briefing:
                clusters = briefing['clusters']
                print(f"\n  🗂️  Clusters ({len(clusters)}):")
                for i, cluster in enumerate(clusters, 1):
                    if isinstance(cluster, dict):
                        cluster_name = cluster.get('name', cluster.get('title', 'Unknown'))
                    else:
                        cluster_name = str(cluster)
                    print(f"     {i}. {cluster_name}")
            
            print()
            
        except json.JSONDecodeError as e:
            print(f"\n  ❌ JSON 解析失败: {e}\n")

def main():
    """主函数"""
    print("\n" + "═" * 80)
    print("🗄️  RSS Agent 数据库查看器".center(80))
    print("═" * 80)
    
    try:
        db_path = get_db_path()
        print(f"\n📁 数据库路径: {db_path}")
        
        conn = sqlite3.connect(db_path)
        
        # 查看所有表
        view_user_preferences(conn)
        view_daily_news_cache(conn)
        
        # 查看今天的详细briefing
        today = date.today().isoformat()
        view_briefing_details(conn, target_date=today)
        
        conn.close()
        
        print("=" * 80)
        print("✅ 查询完成！".center(80))
        print("=" * 80 + "\n")
        
    except FileNotFoundError as e:
        print(f"\n❌ 错误: {e}\n")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}\n")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
