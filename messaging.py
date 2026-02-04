import requests
import json
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app_id = os.getenv("LARK_APP_ID")
app_secret = os.getenv("LARK_APP_SECRET")

def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = {
        "app_id": app_id.strip() if app_id else "",
        "app_secret": app_secret.strip() if app_secret else ""
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
        # 智能检测：是否为卡片 JSON
        msg_type = "text"
        final_content = content
        
        try:
            # 简单的启发式检查：如果是 JSON 且包含 header/elements，就认为是卡片
            if content.strip().startswith("{") and '"header"' in content and '"elements"' in content:
                msg_type = "interactive"
                # 卡片不需要再包一层 {"text": ...}，直接就是 JSON body
                # 但飞书 API 要求 content 字段本身必须是 stringified json
                final_content = content
            else:
                # 普通文本需要包一层
                final_content = json.dumps({"text": content})
        except:
            final_content = json.dumps({"text": content})

        payload = {
            "content": final_content,
            "msg_type": msg_type
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
                short_content = content[:20].replace('\n', ' ')
                print(f"✅ Reply Sent: {short_content}...")
            
    except Exception as e:
        print(f"❌ Exception in reply_message: {str(e)}")
