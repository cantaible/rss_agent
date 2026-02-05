
from messaging import send_message
import os

# 这是从您刚才日志里提取的真实 User ID
USER_ID = "ou_24dd616626616b8b26e55cbc6e03a1d3"

if __name__ == "__main__":
    print(f"🚀 Testing push to: {USER_ID}")
    
    # 1. 发送普通文本
    print("1️⃣ Sending Text Message...")
    try:
        send_message(USER_ID, "🔔 这是一条测试消息 (Text)")
    except Exception as e:
        print(f"❌ Text failed: {e}")

    # 2. 发送简单卡片
    print("\n2️⃣ Sending Card Message...")
    card_content = """
    {
      "config": {
        "wide_screen_mode": true
      },
      "header": {
        "template": "blue",
        "title": {
          "content": "测试卡片",
          "tag": "plain_text"
        }
      },
      "elements": [
        {
          "tag": "div",
          "text": {
            "content": "这是一条测试卡片消息",
            "tag": "lark_md"
          }
        }
      ]
    }
    """
    try:
        send_message(USER_ID, card_content)
    except Exception as e:
        print(f"❌ Card failed: {e}")
        
    print("\n✅ Test script finished.")
