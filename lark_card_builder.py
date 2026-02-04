from agent_graph import NewsBriefing
import json

def build_cover_card(briefing: NewsBriefing) -> str:
    """
    构建飞书早报封面卡片
    UI 结构:
    1. 标题 (蓝色背景)
    2. 全局综述 (文本)
    3. 分割线
    4. Top 5 新闻列表 (Markdown)
    5. 分割线
    6. 专题按钮区 (Action Layout)
    """
    
    # 1. 组装 Top News 文本
    # 我们假设 Top 5 是 clusters 中 score 最高的，或者直接取 clusters 的前几条混合
    # 这里简单处理：扁平化所有新闻，按 score 排序，取前 5
    all_items = []
    for cluster in briefing.clusters:
        all_items.extend(cluster.items)
    
    # 排序：分数降序
    top_items = sorted(all_items, key=lambda x: x.score, reverse=True)[:5]
    
    top_news_md = "**🔥 今日必读 Top 5**\n"
    for i, item in enumerate(top_items, 1):
        top_news_md += f"{i}. [{item.title}]({item.url})\n"

    # 2. 组装 Button Actions
    # 每个 Cluster 一个按钮
    actions = []
    for cluster in briefing.clusters:
        # 按钮文本： "🛠️ 硬件与算力 (8)"
        btn_text = f"👉 {cluster.name} ({len(cluster.items)})"
        
        # 按钮交互：触发回调并传递 value
        action_btn = {
            "tag": "button",
            "text": {
                "tag": "plain_text",
                "content": btn_text
            },
            "type": "default",  # 默认灰色，primary 为蓝色
            # 关键：点击后回传 value 到服务器回调地址
            "value": {"command": "expand", "target": cluster.name} 
        }
        actions.append(action_btn)
    
    # 3. 组装最终 Card JSON
    card = {
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "template": "blue",
            "title": {
                "content": "☕️ AI 行业早报 | 每日情报",
                "tag": "plain_text"
            }
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "content": f"**今日综述**：\n{briefing.global_summary}",
                    "tag": "lark_md"
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "div",
                "text": {
                    "content": top_news_md,
                    "tag": "lark_md"
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "div",
                "text": {
                    "content": "👇 **深度专题 (点击下方按钮展开)**",
                    "tag": "lark_md"
                }
            },
            {
                "tag": "action",
                "actions": actions
            },
            {
                "tag": "note",
                "elements": [
                    {
                        "content": "由 DeepSeek R1 提供深度分析",
                        "tag": "plain_text"
                    }
                ]
            }
        ]
    }
    
    return json.dumps(card, ensure_ascii=False)
