from agent_graph import graph, AgentState
from langchain_core.messages import HumanMessage, AIMessage
import json
import time

def print_separator(title):
    print(f"\n{'='*20} {title} {'='*20}")

def run_test():
    print("🚀 Starting Interactive News Feed Test...")
    
    # 模拟用户 ID
    user_id = "test_user_001"
    
    # ==========================================
    # Phase 1: 订阅 (Write Intent)
    # ==========================================
    print_separator("Phase 1: Subscription")
    inputs = {
        "messages": [HumanMessage(content="订阅 AI 人工智能")],
        "user_id": user_id
    }
    
    # 运行图谱
    for event in graph.stream(inputs):
        for key, value in event.items():
            print(f"  Thinking: [{key}]...")
            
    print("✅ Phase 1 Complete. Preference saved.")

    # ==========================================
    # Phase 2: 看新闻 (Read Intent -> Writer -> Card)
    # 模拟 Fetcher 成功抓取到了数据，直接测试 Writer
    # ==========================================
    print_separator("Phase 2: Fetch News & Generate Card (With Mock Data)")
    
    # 模拟的一坨新闻数据
    mock_news = [
        {"title": "DeepSeek 发布新一代推理模型 R1", "summary": "性能超越 O1，开源社区沸腾。", "link": "https://example.com/1", "published": "2025-01-20"},
        {"title": "OpenAI 宣布降价", "summary": "GPT-4o API 价格下调 50%。", "link": "https://example.com/2", "published": "2025-01-21"},
        {"title": "NVIDIA 股价创新高", "summary": "受 AI 算力需求推动，市值突破 4 万亿。", "link": "https://example.com/3", "published": "2025-01-22"},
        {"title": "Python 3.14 发布预览版", "summary": "吉特编译器性能提升显著。", "link": "https://example.com/4", "published": "2025-01-23"},
        {"title": "特斯拉展示 Optimus 二代", "summary": "动作更灵活，可完成精细操作。", "link": "https://example.com/5", "published": "2025-01-24"}
    ]
    
    inputs = {
        "messages": [HumanMessage(content="看新闻")],
        "user_id": user_id,
        "news_content": json.dumps(mock_news, ensure_ascii=False), # 注入模拟新闻
        "user_preference": "科技与AI" # 注入模拟偏好
    }
    
    final_briefing_data = None
    
    # 我们只想测 Writer，可以直接调用 writer_node (但这需要构造完整的 state)，
    # 或者运行 graph，但我们通过 inputs 提供了 news_content，graph 里的 fetcher 会覆盖它吗？
    # 也就是 fetcher_node 会重新抓取。
    # 为了测试，我们最好直接测 writer_node 函数，或者临时让 fetcher 既然有了 content 就不抓了。
    # 不过简单点，我们假设 fetcher 会失败或者我们改一下 graph?
    # 不，最简单的办法是：直接 invoke writer_node。
    
    from agent_graph import writer_node, detail_node
    
    # 手动构造 State
    state_mock = {
        "messages": [HumanMessage(content="看新闻")],
        "user_id": user_id,
        "news_content": json.dumps(mock_news, ensure_ascii=False),
        "user_preference": "科技与AI",
        "message_id": "mock_msg_id" 
    }
    
    print("  Running writer_node directly...")
    writer_output = writer_node(state_mock)
    
    if "messages" in writer_output:
        content = writer_output["messages"][0].content
        if "header" in content:
            print("  🃏 [Result] Lark Card JSON Generated!")
            print(f"  Preview: {content[:100]}...")
            
            # 保存 briefing data for Phase 3
            final_briefing_data = writer_output.get("briefing_data")
        else:
            print(f"  📝 [Result] Text Content: {content[:50]}")
    else:
        print("❌ Writer output no messages.")

    if not final_briefing_data:
        print("❌ Phase 2 Failed: No briefing data generated.")
        # 如果 Writer 失败，可能也是因为 LLM 404。
        # 如果 Writer 的 Reasoning LLM 也挂了，那我们得修 LLM 配置。
        return
                        
    if not final_briefing_data:
        print("❌ Phase 2 Failed: No briefing data generated.")
        return

    # 这里我们需要手动模拟 State 的持久化
    # 因为 graph.stream 默认是无状态的（除非配置 checkpointer），
    # 但我们的业务逻辑依赖 state["briefing_data"] 传递给下一轮。
    # 为了测试，我们手动把 briefing_data 塞进下一轮的 input state。
    
    # ==========================================
    # Phase 3: 交互 (Detail Intent)
    # ==========================================
    # 模拟从卡片里拿到的第一个 Cluster 名字
    cluster_name = final_briefing_data["clusters"][0]["name"]
    print_separator(f"Phase 3: Verify Detail (Input: '展开：{cluster_name}')")
    
    inputs = {
        "messages": [HumanMessage(content=f"展开：{cluster_name}")],
        "user_id": user_id,
        "briefing_data": final_briefing_data, # 模拟历史状态记忆
        "user_preference": "AI", # 模拟历史偏好 (长期)
        "selected_cluster": cluster_name # 模拟 Router 刚刚提取出的短期目标
    }
    
    # 注意：在真实 Graph 运行中，selected_cluster 是由 Router 产生的。
    # 这里我们直接喂给 detail_node 之前的状态，
    # 或者我们运行完整的 graph (从 router 开始)。
    # 如果运行 graph，inputs 里只需要 messages，Router 会自动设 selected_cluster。
    # 让我们试着让 Router 自己跑出来，验证 Router 的正则逻辑。
    
    inputs_real = {
        "messages": [HumanMessage(content=f"展开：{cluster_name}")],
        "user_id": user_id,
        "briefing_data": final_briefing_data,
        "user_preference": "AI"
    }

    print(f"  Input Message: 展开：{cluster_name}")
    
    for event in graph.stream(inputs_real):
        for key, value in event.items():
            print(f"  Thinking: [{key}]...")
            if "selected_cluster" in value:
                 print(f"  🎯 [Router] Set selected_cluster: {value['selected_cluster']}")
            
            if key == "detail":
                 messages = value.get("messages", [])
                 if messages:
                     print(f"  📄 [Result] Detail Content:\n{messages[0].content[:200]}...")

if __name__ == "__main__":
    run_test()
