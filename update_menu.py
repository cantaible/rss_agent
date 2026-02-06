import requests
import os
import json
from dotenv import load_dotenv
from config import DAILY_NEWS_CATEGORIES

load_dotenv()

APP_ID = os.getenv("LARK_APP_ID")
APP_SECRET = os.getenv("LARK_APP_SECRET")

def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    req_body = {
        "app_id": APP_ID,
        "app_secret": APP_SECRET
    }
    resp = requests.post(url, json=req_body)
    resp.raise_for_status()
    return resp.json().get("tenant_access_token")

def update_bot_menu():
    token = get_tenant_access_token()
    url = "https://open.feishu.cn/open-apis/application/v6/bot/menu_tree"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Construct Menu Structure
    # Root level menu items
    menu_structure = {
        "menu_tree": {
            "menu_items": [
                {
                    "position": "1",
                    "name": "🔔 订阅配置",
                    "children": [] 
                }
            ]
        }
    }
    
    # Add children (Categories)
    for idx, category in enumerate(DAILY_NEWS_CATEGORIES):
        child_item = {
            "position": str(idx + 1),
            "name": f"{category}",
            "action": {
                "value": f"subscribe:{category}" # event_key
            }
        }
        menu_structure["menu_tree"]["menu_items"][0]["children"].append(child_item)

    print(f"Updating Bot Menu with categories: {DAILY_NEWS_CATEGORIES}...")
    # 修正：创建/更新菜单通常用 POST
    resp = requests.post(url, headers=headers, json=menu_structure)
    
    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 0:
            print("✅ Bot Menu Updated Successfully!")
        else:
            print(f"❌ Failed to update menu: {data}")
    else:
        print(f"❌ HTTP Error: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    update_bot_menu()
