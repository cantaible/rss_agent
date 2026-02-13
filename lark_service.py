# FastAPI 是 web 框架
from fastapi import FastAPI
import uvicorn
import json
from fastapi import BackgroundTasks, Request
from contextlib import asynccontextmanager

from agent_graph import graph
from langchain_core.messages import HumanMessage
from messaging import reply_message
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date
from database import save_cached_news, get_cached_news, DB_FILE, upsert_preference, init_db
import sqlite3
import asyncio
import threading
from pytz import timezone
from collections import deque

# 事件去重队列
processed_events = deque(maxlen=100)

# 初始化调度器（使用北京时区）
beijing_tz = timezone('Asia/Shanghai')
scheduler = BackgroundScheduler(timezone=beijing_tz)
daily_archive_push_lock = threading.Lock()

# def pre_generate_daily_news():
#     """(已弃用) 每天9点：预生成4个类别的早报"""
#     pass

# --- 任务分离：生成与推送 ---

from config import DAILY_NEWS_CATEGORIES

def generate_news_task(force=True):
    """
    👨‍🍳 厨师任务：每隔2小时（或启动时）生成新闻并存入数据库（不推送）
    
    改进：直接从 config.py 读取类别，作为参数传递给 agent，不依赖数据库查询
    """
    today = date.today().isoformat()
    
    print(f"👨‍🍳 [Chef] Starting news generation (Force={force}) for categories: {DAILY_NEWS_CATEGORIES}...")

    for category in DAILY_NEWS_CATEGORIES:
        # 关键修复：每个类别使用独立的 thread_id，避免 LangGraph state 污染
        # 例如: system_daily_bot_AI, system_daily_bot_GAMES, system_daily_bot_MUSIC
        category_user_id = f"system_daily_bot_{category}"
        
        # 如果不是强制刷新 (即 Startup 模式)，先检查是否已有饭菜
        if not force:
            cached = get_cached_news(category, today)
            if cached:
                print(f"⏩ [Chef] Data exists for {category}, skipping generation (Startup check).")
                continue

        try:
            # 1. 生成新闻
            # 关键改动：直接传入 user_preference=category，跳过 router 解析和数据库查询
            # force_refresh=True 强制重新抓取新闻，不使用缓存
            content, briefing_data = run_agent(
                user_id=category_user_id,  # ← 使用独立的 thread_id
                text="生成日报",  # 文本不再重要，仅作占位
                force_refresh=True,
                user_preference=category  # 直接传入类别！
            )
            
            # 2. 存根
            if briefing_data:
                briefing_data_str = json.dumps(briefing_data, ensure_ascii=False)
                save_cached_news(category, content, today, briefing_data_str)
                print(f"💾 [Chef] Saved cache for {category}. Ready to serve.")
            else:
                print(f"⚠️ [Chef] No data generated for {category}")
                
        except Exception as e:
            print(f"❌ [Chef] Failed for {category}: {e}")

def push_delivery_task():
    """🛵 外卖员任务：推送最新的新闻"""
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_FILE)
    users = conn.execute("SELECT user_id, category FROM user_preferences").fetchall()
    conn.close()
    
    from messaging import send_message
    
    print(f"🛵 [Delivery] Starting daily push dispatch...")
    
    for user_id, category in users:
        # 1. 只是去取货
        cached_data = get_cached_news(category, today)
        
        if cached_data and cached_data.get("content"):
            print(f"📤 [Delivery] Pushing hot news to {user_id}")
            send_message(user_id, cached_data["content"])
        else:
            print(f"⚠️ [Delivery] No food ready for {user_id} (Cache miss)")
            # 可选：这里可以触发一次 generate_news_task() 作为补救

def daily_archive_and_push_job():
    """统一定时任务：先归档，再推送。"""
    if not daily_archive_push_lock.acquire(blocking=False):
        print("⏩ [Scheduler] daily_archive_and_push_job is already running, skipping this trigger.")
        return

    try:
        print("⏰ [Scheduler] Starting daily archive + push job...")
        try:
            asyncio.run(archive_daily_news_to_wiki(user_id=None, notify_user=False))
        except Exception as e:
            print(f"❌ [Scheduler] Archive step failed: {e}")

        push_delivery_task()
        print("✅ [Scheduler] Finished daily archive + push job.")
    finally:
        daily_archive_push_lock.release()

# 使用 FastAPI 推荐的 lifespan 方式（用于优雅关闭和避免重复初始化）
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - 只在 worker 进程中执行（避免 reload 模式下的重复初始化）
    print("📦 Initializing database...")
    init_db()
    
    print("⏰ Starting Scheduler...")
    from datetime import datetime, timedelta
    
    # 1. 厨师任务：北京时间 8:00 - 22:00，每2小时做一次饭
    scheduler.add_job(generate_news_task, 'cron', hour='8-22/2', minute=0, timezone=beijing_tz)
    
    # 2. 也是厨师任务：刚开业（启动服务）时先做一顿
    # 关键：这里 force=False，如果数据库里已经有菜了，就不重做了 (避免热重载时疯狂生成)
    scheduler.add_job(generate_news_task, 'date', run_date=datetime.now(beijing_tz) + timedelta(seconds=5), kwargs={"force": False})
    
    # 3. 统一任务：北京时间每天 09:10，先归档再推送
    scheduler.add_job(
        daily_archive_and_push_job,
        'cron',
        id='daily_archive_and_push_job',
        hour=9,
        minute=10,
        timezone=beijing_tz,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    
    scheduler.start()
    print(f"✅ Scheduler started with timezone: {beijing_tz}")
    
    yield
    
    # Shutdown (优雅关闭调度器)
    print("🛑 Shutting down scheduler...")
    scheduler.shutdown()

# 创建一个 App 实例，使用 lifespan
app = FastAPI(lifespan=lifespan)

def run_agent(user_id, text, message_id=None, force_refresh=False, user_preference=None):
    """
    运行 LangGraph Agent
    
    参数:
        user_id: 用户ID
        text: 用户输入文本
        message_id: 消息ID（用于回复）
        force_refresh: 是否强制刷新缓存
        user_preference: 直接指定用户偏好类别（定时任务专用，跳过 router 和数据库查询）
    """
    config = {"configurable": {"thread_id": user_id}}
    
    # 获取历史消息（用于聊天模式的上下文记忆）
    try:
        previous_state = graph.get_state(config)
        history = previous_state.values.get("messages", []) if previous_state and previous_state.values else []
    except Exception:
        history = []
    
    # 滑动窗口：只保留最近10条消息（约5轮对话），避免超 Token 限额
    recent_history = history[-10:] if len(history) > 10 else history
    
    # 拼接历史 + 新消息
    inputs = {
        "messages": recent_history + [HumanMessage(content=text)], 
        "user_id": user_id,
        "message_id": message_id,
        "force_refresh": force_refresh, # [新增] 控制是否强制刷新
        "user_preference": user_preference # [新增] 直接传入偏好类别
    }
    
    # 传入 thread_id 以启用 state 持久化（每个用户独立存储）
    res = graph.invoke(inputs, config=config)
    
    # 返回 (content, briefing_data)
    content = res["messages"][-1].content
    briefing_data = res.get("briefing_data")
    return content, briefing_data

# 定义一个 GET 接口，访问根路径 "/" 时触发
@app.get("/")
def health_check():
    return {"status": "ok", "message": "Bot is running! (机器人正在运行)"}

# 异步后台任务：AI 思考并回复
def process_lark_message(event_data):
    message_id = event_data["message"]["message_id"]
    content_json = event_data["message"]["content"]
    user_text = json.loads(content_json)["text"]
    
    # 提取发送者 ID
    sender_id = event_data["sender"]["sender_id"]["open_id"]
    
    # AI 思考 (传入 ID 和 Message ID)
    # run_agent 返回 (content, briefing_data)
    ai_reply_content, _ = run_agent(sender_id, user_text, message_id)
    
    # 回复
    reply_message(message_id, ai_reply_content)



@app.post("/api/lark/event")
async def handle_event(request: Request, background_tasks: BackgroundTasks):
    # 解析原始 JSON
    body = await request.json()
    
    # 🔍 调试日志：打印所有收到的请求
    print(f"\n{'='*60}")
    print(f"📨 [DEBUG] Received request")
    print(f"Request type: {body.get('type')}")
    print(f"Event type: {body.get('header', {}).get('event_type')}")
    print(f"Full body keys: {list(body.keys())}")
    print(f"Full body keys: {list(body.keys())}")
    print(f"{'='*60}\n")
    
    # 0. 去重处理 (防止飞书超时重试导致二次触发)
    event_id = body.get("header", {}).get("event_id")
    if event_id and event_id in processed_events:
        print(f"⏩ [Event] Duplicate event {event_id}, skipping.")
        return {"code": 0}
    
    if event_id:
        processed_events.append(event_id)
    
    # 1. 握手验证
    if body.get("type") == "url_verification":
        print("✅ [Verification] Responding to URL verification")
        return {"challenge": body.get("challenge")}
        
    # 2. 处理用户消息 (Event v2 格式)
    if body.get("header", {}).get("event_type") == "im.message.receive_v1":
        print("📧 [Message] Processing user message")
        # 放入后台运行，不阻塞 HTTP 返回
        background_tasks.add_task(process_lark_message, body["event"])

    # [新增] 处理菜单点击事件
    elif body.get("header", {}).get("event_type") == "application.bot.menu_v6":
        event = body.get("event", {})
        event_key = event.get("event_key", "") # e.g. "subscribe:AI"
        operator_id = event.get("operator", {}).get("operator_id", {}).get("open_id")
        
        print(f"🔘 [Menu Event] Key: {event_key}, User: {operator_id}")
        
        if event_key.startswith("subscribe:"):
            category = event_key.split(":")[1]
            upsert_preference(operator_id, category)
            
            # 由于菜单点击没有 message_id 上下文，我们需要主动发消息给用户
            # 但这里没有 reply token，通常直接调 send_message
            from messaging import send_message
            send_message(operator_id, f"✅ 已成功订阅 **{category}** 类别！\n我们将为您推送该类别的每日早报。")

        # 2. 新增：处理手动触发新闻请求
        elif event_key in ["REQUEST_MUSIC_NEWS", "REQUEST_GAMES_NEWS", "REQUEST_AI_NEWS"]:
            # 提取类别: REQUEST_MUSIC_NEWS -> MUSIC
            target_category = event_key.split("_")[1] 
            print(f"🔍 [Menu] 用户 {operator_id} 请求获取：{target_category} 新闻")
            
            from datetime import date
            today = date.today().isoformat()
            cached = get_cached_news(target_category, today)
            
            from messaging import send_message
            if cached and cached.get("content"):
                send_message(operator_id, cached["content"])
            else:
                send_message(operator_id, f"ℹ️ 抱歉，今天的【{target_category}】日报暂未生成。\n请稍后再试，或等待每日定时推送。")

        # 3. 新增：测试归档到 Wiki
        elif event_key == "WRITE_DAILY_NEWS":
             print(f"📝 [Menu] 用户 {operator_id} 请求：归档日报到 Wiki")
             
             from messaging import send_message
             send_message(operator_id, "⏳ 正在将今日多类别日报归档至 Wiki，请稍候...")
             
             background_tasks.add_task(archive_daily_news_to_wiki, operator_id)

    # 3. 处理卡片交互 (Card Action)
    # 当用户点击卡片按钮时触发
    elif body.get("header", {}).get("event_type") == "card.action.trigger":
        # 从 event 对象中获取数据
        event_data = body.get("event", {})
        action_value = event_data.get("action", {}).get("value", {})
        command = action_value.get("command")
        target = action_value.get("target")
        
        # 构造模拟的文本指令，例如 "展开：硬件与算力"
        if command == "expand" and target:
            simulated_text = f"展开：{target}"
            print(f"🃏 [Card Action] Received: {simulated_text}")
            
            # 获取用户和消息上下文信息
            sender_id = event_data.get("operator", {}).get("open_id")
            card_msg_id = event_data.get("context", {}).get("open_message_id")
            
            # 后台处理（不返回 Toast，避免3秒超时限制）
            background_tasks.add_task(handle_card_action_async, sender_id, simulated_text, card_msg_id, target)
            
            # 返回成功响应，不显示 Toast
            # code:0 表示成功，toast.type: info 显示一个小提示
            # 如果不想显示任何提示，可以返回 {"code": 0}，或者 {"toast": {"type": "success", "content": "正在处理..."}}
            return {"toast": {"type": "info", "content": "正在为您加载详情..."}}
    
    return {"code": 0}

async def handle_card_action_async(user_id, text, message_id, target):
    """处理卡片点击后的异步逻辑"""
    print(f"🃏 [Async] Running agent for card action: {text}")
    
    # 立即发送"正在处理"消息，让用户知道系统已响应
    reply_message(message_id, f"⏳ 正在为您展开 **{target}** 的详细内容，请稍候...")
    
    # 后台慢慢处理（无3秒限制）
    ai_reply_content, _ = run_agent(user_id, text, message_id)
    reply_message(message_id, ai_reply_content)

async def archive_daily_news_to_wiki(user_id=None, notify_user=True):
    """
    后台任务：将今日日报归档到 Wiki
    """
    try:
        from doc_writer import FeishuDocWriter
        import os
        from config import WIKI_TOKEN, DAILY_NEWS_CATEGORIES
        
        app_id = os.getenv("LARK_APP_ID")
        app_secret = os.getenv("LARK_APP_SECRET")
        # 目标文档: WIKI_TOKEN 已从 config 导入 
        
        if not app_id or not app_secret:
            print("❌ 缺少 LARK_APP_ID 或 LARK_APP_SECRET 环境变量")
            return

        print(f"📂 [Archiver] Starting archive task for user {user_id}...")
        
        # 1. 准备数据
        today = date.today().isoformat()
        categories = DAILY_NEWS_CATEGORIES
        all_news_data = {}
        
        for cat in categories:
            cached = get_cached_news(cat, today)
            briefing = None
            if cached and cached.get("briefing_data"):
                try:
                    # 数据库里存的是 JSON string
                    parsed = json.loads(cached["briefing_data"])
                    if isinstance(parsed, dict):
                        briefing = parsed
                    else:
                        print(f"⚠️ {cat} briefing_data 不是对象，已降级为暂无数据")
                except Exception as e:
                    print(f"⚠️ 解析 {cat} 数据失败: {e}")
            
            all_news_data[cat] = briefing
            
        # 2. 执行写入
        writer = FeishuDocWriter(app_id, app_secret)
        success = writer.write_daily_news_to_wiki(WIKI_TOKEN, all_news_data)
        
        # 3. 反馈用户（定时任务可关闭通知）
        if success:
            msg = f"✅ 归档成功！\n请查看文档： https://bytedance.larkoffice.com/wiki/{WIKI_TOKEN}"
            print("✅ [Archiver] Archive success.")
        else:
            msg = "❌ 归档失败，请检查后台日志。"
            print("❌ [Archiver] Archive failed.")

        if notify_user and user_id:
            from messaging import send_message
            send_message(user_id, msg)
        elif notify_user and not user_id:
            print("ℹ️ [Archiver] notify_user=True but user_id is empty, skip sending message.")
        
    except Exception as e:
        print(f"❌ [Archiver] Exception: {e}")


if __name__ == "__main__":
    # 启动服务器：
    # "lark_service:app" -> 告诉引擎去 lark_service.py 文件里找 app 这个变量
    # port=8000 -> 监听 8000 端口
    # reload=True -> 你一改代码，服务器自动重启（方便开发）
    uvicorn.run("lark_service:app", host="0.0.0.0", port=36000, reload=True)
