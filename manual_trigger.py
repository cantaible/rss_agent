
import asyncio
from lark_service import generate_news_task, push_delivery_task
from database import init_db

if __name__ == "__main__":
    print("🚀 Manually triggering scheduled tasks...")
    
    # 1. 确保数据库有表
    init_db()
    
    # 2. 模拟 9:00 预生成
    print("\n[Step 1] Running pre-generation...")
    try:
        generate_news_task(force=True)
    except Exception as e:
        print(f"❌ Error in pre-gen: {e}")
        
    # 3. 模拟 10:00 推送 (需要异步运行)
    print("\n[Step 2] Running daily push...")
    try:
        # push_delivery_task 是同步函数，不要用 asyncio.run
        push_delivery_task()
    except Exception as e:
        print(f"❌ Error in push: {e}")
        
    print("\n✅ Done.")
