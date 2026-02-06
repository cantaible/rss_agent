# FastAPI 是 web 框架
from fastapi import FastAPI
import uvicorn
import json
from fastapi import BackgroundTasks, Request

from agent_graph import graph
from langchain_core.messages import HumanMessage
from messaging import reply_message
from apscheduler.schedulers.background import BackgroundScheduler

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date
from database import save_cached_news, get_cached_news, DB_FILE, upsert_preference
import sqlite3
import asyncio

# 初始化调度器
scheduler = BackgroundScheduler()

# def pre_generate_daily_news():
#     """(已弃用) 每天9点：预生成4个类别的早报"""
#     pass

# --- 任务分离：生成与推送 ---

from config import DAILY_NEWS_CATEGORIES

def generate_news_task(force=True):
    """👨‍🍳 厨师任务：每隔2小时（或启动时）生成新闻并存入数据库（不推送）"""
    today = date.today().isoformat()
    # conn = sqlite3.connect(DB_FILE)
    # users = conn.execute("SELECT user_id, category FROM user_preferences").fetchall()
    # conn.close()
    
    print(f"👨‍🍳 [Chef] Starting news generation (Force={force}) for categories: {DAILY_NEWS_CATEGORIES}...")
    
    # 之前是遍历所有用户 user_preferences，现在改为遍历固定的类别
    # 使用一个固定的 system_daily_bot 作为 user_id，确保生成逻辑一致
    system_user_id = "system_daily_bot"

    for category in DAILY_NEWS_CATEGORIES:
        # 如果不是强制刷新 (即 Startup 模式)，先检查是否已有饭菜
        if not force:
            cached = get_cached_news(category, today)
            if cached:
                print(f"⏩ [Chef] Data exists for {category}, skipping generation (Startup check).")
                continue

        try:
            # 1. 生成 (模仿用户指令)
            # 关键：传入 force_refresh=True，强制厨师炒新菜，不要吃剩饭
            content, briefing_data = run_agent(system_user_id, f"看关于{category}的新闻", force_refresh=True)
            
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
    """🛵 外卖员任务：每天10:10准时推送最新的新闻"""
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

# 创建一个 App 实例
app = FastAPI()

@app.on_event("startup")
def start_scheduler():
    print("⏰ Starting Scheduler...")
    
    # 1. 厨师任务：8:00 - 22:00，每2小时做一次饭
    scheduler.add_job(generate_news_task, 'cron', hour='8-22/2', minute=0)
    
    # 2. 也是厨师任务：刚开业（启动服务）时先做一顿
    # 关键：这里 force=False，如果数据库里已经有菜了，就不重做了 (避免热重载时疯狂生成)
    from datetime import datetime, timedelta
    scheduler.add_job(generate_news_task, 'date', run_date=datetime.now() + timedelta(seconds=5), kwargs={"force": False})
    
    # 3. 外卖员任务：每天 10:10 准时送餐
    scheduler.add_job(push_delivery_task, 'cron', hour=17, minute=46)
    
    scheduler.start()

def run_agent(user_id, text, message_id=None, force_refresh=False):
    """运行 LangGraph Agent"""
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
        "force_refresh": force_refresh # [新增] 控制是否强制刷新
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
    print(f"{'='*60}\n")
    
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

if __name__ == "__main__":
    # 启动服务器：
    # "lark_service:app" -> 告诉引擎去 lark_service.py 文件里找 app 这个变量
    # port=8000 -> 监听 8000 端口
    # reload=True -> 你一改代码，服务器自动重启（方便开发）
    uvicorn.run("lark_service:app", host="0.0.0.0", port=36000, reload=True)

