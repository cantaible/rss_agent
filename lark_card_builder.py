from agent_graph import NewsBriefing
import json
from datetime import datetime

def build_cover_card(briefing: NewsBriefing, generated_at: str = None, category: str = "AI") -> str:
    """
    构建飞书早报封面卡片
    新结构：今日头条 + 深度专题按钮
    """
    
    # 0. 动态标题映射
    title_map = {
        "AI": "AI每日新闻",
        "GAMES": "游戏每日新闻",
        "MUSIC": "音乐每日新闻",
        "SHORT_DRAMA": "短剧每日新闻"
    }
    # 默认兜底
    card_title = title_map.get(category, f"☕️ {category} 行业早报")
    
    # 1. 格式化时间字符串
    time_str = datetime.now().strftime('%H:%M')
    if generated_at:
        try:
            if isinstance(generated_at, str):
                dt = datetime.fromisoformat(generated_at)
            else:
                dt = generated_at
            time_str = dt.strftime('%H:%M')
        except:
            pass
    
    # 2. 组装今日头条文本（来自 headlines）
    headlines_md = "**🔥 今日头条**\n"
    for i, headline in enumerate(briefing.headlines, 1):
        headlines_md += f"{i}. [{headline.title}]({headline.url})\n"

    # 3. 组装深度专题按钮（每个 Cluster 一个按钮）
    actions = []
    for cluster in briefing.clusters:
        btn_text = f"👉 {cluster.name} ({len(cluster.items)})"
        action_btn = {
            "tag": "button",
            "text": {
                "tag": "plain_text",
                "content": btn_text
            },
            "type": "default",
            "value": {"command": "expand", "target": cluster.name, "category": category}
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
                    "content": headlines_md,
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
