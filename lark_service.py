# FastAPI 是 web 框架，负责定义有什么接口 (URL)
from fastapi import FastAPI
# Uvicorn 是服务器引擎，负责把代码跑起来
import uvicorn
import lark_oapi as lark
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app_id = os.getenv("LARK_APP_ID")
app_secret = os.getenv("LARK_APP_SECRET")
print(f"DEBUG: AppID={app_id}, Secret={'*' * len(app_secret) if app_secret else 'None'}")

# 初始化飞书客户端
lark_client = lark.Client.builder() \
    .app_id(app_id.strip()) \
    .app_secret(app_secret.strip()) \
    .log_level(lark.LogLevel.DEBUG) \
    .build()



# 创建一个 App 实例
app = FastAPI()

import json
from agent_graph import graph
from langchain_core.messages import HumanMessage

def run_agent(user_id, text):
    """运行 LangGraph Agent"""
    inputs = {"messages": [HumanMessage(content=text)], "user_id": user_id}
    res = graph.invoke(inputs)
    return res["messages"][-1].content


import requests

def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = {
        "app_id": app_id.strip(),
        "app_secret": app_secret.strip()
    }
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code == 200:
        return resp.json().get("tenant_access_token")
    else:
        print(f"❌ Failed to get token: {resp.text}")
        return None

def reply_message(message_id, content):
    """
    调用飞书 API 回复用户 (Raw HTTP)
    """
    try:
        token = get_tenant_access_token()
        if not token:
            print("❌ Cannot send message without token")
            return
            
        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        payload = {
            "content": json.dumps({"text": content}),
            "msg_type": "text"
        }
        
        resp = requests.post(url, headers=headers, json=payload)
        
        if resp.status_code != 200:
            print(f"❌ Lark API Error: {resp.text}")
        else:
            # 飞书 API 即使 200 也可能在 body 里报错
            res_json = resp.json()
            if res_json.get("code") != 0:
                print(f"❌ Lark Logic Error: {res_json}")
            else:
                print(f"✅ Reply Sent: {content[:20]}...")
            
    except Exception as e:
        print(f"❌ Exception in reply_message: {str(e)}")



# 定义一个 GET 接口，访问根路径 "/" 时触发
# 比如你在浏览器访问 http://localhost:8000/ 就会看到这里的返回值
@app.get("/")
def health_check():
    return {"status": "ok", "message": "Bot is running! (机器人正在运行)"}

from fastapi import BackgroundTasks, Request

# 异步后台任务：AI 思考并回复
def process_lark_message(event_data):
    message_id = event_data["message"]["message_id"]
    content_json = event_data["message"]["content"]
    user_text = json.loads(content_json)["text"]
    
    # 提取发送者 ID
    sender_id = event_data["sender"]["sender_id"]["open_id"]
    
    # AI 思考 (传入 ID)
    ai_reply = run_agent(sender_id, user_text)
    # 回复
    reply_message(message_id, ai_reply)


@app.post("/api/lark/event")
async def handle_event(request: Request, background_tasks: BackgroundTasks):
    # 解析原始 JSON
    body = await request.json()
    
    # 1. 握手验证
    if body.get("type") == "url_verification":
        return {"challenge": body.get("challenge")}
        
    # 2. 处理用户消息 (Event v2 格式)
    if body.get("header", {}).get("event_type") == "im.message.receive_v1":
        # 放入后台运行，不阻塞 HTTP 返回
        background_tasks.add_task(process_lark_message, body["event"])
    
    return {"code": 0}

if __name__ == "__main__":
    # 启动服务器：
    # "lark_service:app" -> 告诉引擎去 lark_service.py 文件里找 app 这个变量
    # port=8000 -> 监听 8000 端口
    # reload=True -> 你一改代码，服务器自动重启（方便开发）
    uvicorn.run("lark_service:app", host="0.0.0.0", port=36000, reload=True)

