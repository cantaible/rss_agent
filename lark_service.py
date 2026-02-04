# FastAPI 是 web 框架
from fastapi import FastAPI
import uvicorn
import json
from fastapi import BackgroundTasks, Request

from agent_graph import graph
from langchain_core.messages import HumanMessage
from messaging import reply_message

# 创建一个 App 实例
app = FastAPI()

def run_agent(user_id, text, message_id=None):
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
        "message_id": message_id
    }
    
    # 传入 thread_id 以启用 state 持久化（每个用户独立存储）
    res = graph.invoke(inputs, config=config)
    return res["messages"][-1].content

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
    ai_reply = run_agent(sender_id, user_text, message_id)
    
    # 回复
    reply_message(message_id, ai_reply)



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
            return {"code": 0}
    
    return {"code": 0}

async def handle_card_action_async(user_id, text, message_id, target):
    """处理卡片点击后的异步逻辑"""
    print(f"🃏 [Async] Running agent for card action: {text}")
    
    # 立即发送"正在处理"消息，让用户知道系统已响应
    reply_message(message_id, f"⏳ 正在为您展开 **{target}** 的详细内容，请稍候...")
    
    # 后台慢慢处理（无3秒限制）
    ai_reply = run_agent(user_id, text, message_id)
    reply_message(message_id, ai_reply)

if __name__ == "__main__":
    # 启动服务器：
    # "lark_service:app" -> 告诉引擎去 lark_service.py 文件里找 app 这个变量
    # port=8000 -> 监听 8000 端口
    # reload=True -> 你一改代码，服务器自动重启（方便开发）
    uvicorn.run("lark_service:app", host="0.0.0.0", port=36000, reload=True)

