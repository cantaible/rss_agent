from lark_service import generate_news_task
from database import init_db

if __name__ == "__main__":
    print("🚀 Manually triggering cache refresh task...")
    
    # 1. 确保数据库有表
    init_db()
    
    # 2. 强制刷新当日新闻缓存（不执行推送）
    print("\n[Step 1] Refreshing daily news cache...")
    try:
        generate_news_task(force=True)
    except Exception as e:
        print(f"❌ Error while refreshing cache: {e}")
        raise
        
    print("\n✅ Cache refresh completed. No push has been sent.")
