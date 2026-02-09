#!/usr/bin/env python3
"""
飞书 Webhook 测试脚本
用于测试飞书机器人能否正常接收和回复消息
"""

import requests
import json

# 配置
WEBHOOK_URL = "http://localhost:36000/api/lark/event"

def test_url_verification():
    """测试 URL 验证握手"""
    print("=" * 60)
    print("1️⃣ 测试 URL 验证握手")
    print("=" * 60)
    
    payload = {
        "type": "url_verification",
        "challenge": "test_challenge_string_12345"
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=5)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        
        if response.status_code == 200 and response.json().get("challenge") == "test_challenge_string_12345":
            print("✅ URL 验证测试通过！")
            return True
        else:
            print("❌ URL 验证测试失败！")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def test_message_receive():
    """测试消息接收"""
    print("\n" + "=" * 60)
    print("2️⃣ 测试消息接收（模拟飞书发送消息）")
    print("=" * 60)
    
    # 模拟飞书 Event v2 格式的消息
    payload = {
        "schema": "2.0",
        "header": {
            "event_id": "test_event_12345",
            "event_type": "im.message.receive_v1",
            "create_time": "1234567890",
            "token": "test_token",
            "app_id": "cli_test",
            "tenant_key": "test_tenant"
        },
        "event": {
            "sender": {
                "sender_id": {
                    "union_id": "test_union_id",
                    "user_id": "test_user_id",
                    "open_id": "test_open_id_123"
                },
                "sender_type": "user",
                "tenant_key": "test_tenant"
            },
            "message": {
                "message_id": "test_msg_001",
                "root_id": "",
                "parent_id": "",
                "create_time": "1234567890",
                "chat_id": "test_chat_001",
                "chat_type": "p2p",
                "message_type": "text",
                "content": json.dumps({"text": "你好，这是一条测试消息"}),
                "mentions": []
            }
        }
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        
        if response.status_code == 200:
            print("✅ 消息接收测试通过！")
            print("⚠️  注意: 由于没有真实的飞书 API 凭证，机器人无法实际回复消息")
            print("         但如果服务正常，你应该能在日志中看到处理记录")
            return True
        else:
            print("❌ 消息接收测试失败！")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def test_health_check():
    """测试健康检查接口"""
    print("\n" + "=" * 60)
    print("0️⃣ 测试健康检查接口")
    print("=" * 60)
    
    try:
        response = requests.get("http://localhost:36000/", timeout=5)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        
        if response.status_code == 200:
            print("✅ 健康检查通过！")
            return True
        else:
            print("❌ 健康检查失败！")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False

def main():
    print("\n🧪 飞书服务测试工具")
    print("=" * 60)
    print("")
    
    results = []
    
    # 健康检查
    results.append(test_health_check())
    
    # URL 验证
    results.append(test_url_verification())
    
    # 消息接收
    results.append(test_message_receive())
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    total = len(results)
    passed = sum(results)
    print(f"总测试数: {total}")
    print(f"通过: {passed}")
    print(f"失败: {total - passed}")
    
    if all(results):
        print("\n✅ 所有测试通过！Lark Service 工作正常")
    else:
        print("\n❌ 部分测试失败，请检查服务日志")
        print("   运行 'docker logs rss-agent' 查看详细日志")

if __name__ == "__main__":
    main()
