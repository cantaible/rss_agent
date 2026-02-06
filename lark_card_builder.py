from agent_graph import NewsBriefing
import json
from datetime import datetime

def build_cover_card(briefing: NewsBriefing, generated_at: str = None, category: str = "AI") -> str:
    """
    构建飞书早报封面卡片
    """
    
    # 0. 动态标题映射
    title_map = {
        "AI": "🤖 AI 行业早报 | 每日情报",
        "GAMES": "🎮 游戏行业早报 | 玩家必读",
        "MUSIC": "🎵 音乐行业早报 | 听见未来",
        "SHORT_DRAMA": "🎬 短剧行业早报 | 爆款风向"
    }
    # 默认兜底
    card_title = title_map.get(category, f"☕️ {category} 行业早报 | 每日情报")
    
    # 1. 格式化时间字符串
    time_str = datetime.now().strftime('%H:%M')
    if generated_at:
        try:
            # 数据库存的是 datetime 对象或 isoformat 字符串
            # 如果是 str: "2026-02-06 14:00:00.123" -> Parse -> Format
            if isinstance(generated_at, str):
                dt = datetime.fromisoformat(generated_at)
            else:
                dt = generated_at
            time_str = dt.strftime('%H:%M')
        except:
            pass # Parse failed, use now
    
    # 2. 组装 Top News 文本
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

    # 3. 组装 Button Actions
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
    
    # 4. 组装最终 Card JSON
    card = {
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "template": "blue",
            "title": {
                "content": card_title,
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
                        "content": f"⏰ 生成于 {time_str}",
                        "tag": "plain_text"
                    }
                ]
            }
        ]
    }
    
    return json.dumps(card, ensure_ascii=False)
