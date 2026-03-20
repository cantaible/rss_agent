from datetime import datetime
from typing import Dict, List

from pytz import timezone


def _format_window_label(window_start: datetime, window_end: datetime, timezone_name: str) -> str:
    tz = timezone(timezone_name)
    start_local = window_start.astimezone(tz)
    end_local = window_end.astimezone(tz)
    duration_minutes = max(int((window_end - window_start).total_seconds() // 60), 0)

    if duration_minutes and duration_minutes % 60 == 0:
        duration_label = f"过去 {duration_minutes // 60} 小时"
    elif duration_minutes:
        duration_label = f"过去 {duration_minutes} 分钟"
    else:
        duration_label = "当前时间窗"

    if start_local.date() == end_local.date():
        window_label = (
            f"{start_local.strftime('%m-%d %H:%M')} - {end_local.strftime('%H:%M')}"
        )
    else:
        window_label = (
            f"{start_local.strftime('%m-%d %H:%M')} - {end_local.strftime('%m-%d %H:%M')}"
        )

    return f"{duration_label}新闻更新（{window_label}）"


def _format_article_line(article: dict, index: int, timezone_name: str) -> List[str]:
    lines = [f"{index}. {article['title']}"]

    meta_parts = []
    if article.get("sourceName"):
        meta_parts.append(f"来源：{article['sourceName']}")

    published_at = article.get("publishedAt")
    if published_at:
        try:
            parsed = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            local_dt = parsed.astimezone(timezone(timezone_name))
            meta_parts.append(f"时间：{local_dt.strftime('%m-%d %H:%M')}")
        except Exception:
            meta_parts.append(f"时间：{published_at}")

    if meta_parts:
        lines.append(" | ".join(meta_parts))

    summary = (article.get("summary") or "").strip()
    if summary:
        compact_summary = " ".join(summary.split())
        lines.append(f"摘要：{compact_summary}")

    source_url = article.get("sourceURL")
    if source_url:
        lines.append(f"链接：{source_url}")

    return lines


def format_group_news_message(
    news_by_category: Dict[str, List[dict]],
    window_start: datetime,
    window_end: datetime,
    timezone_name: str,
) -> str:
    non_empty_categories = [
        category for category, articles in news_by_category.items() if articles
    ]
    if not non_empty_categories:
        return "\n".join(
            [
                _format_window_label(window_start, window_end, timezone_name),
                "",
                "当前时段暂无相关新闻。",
            ]
        ).strip()

    lines: List[str] = [
        _format_window_label(window_start, window_end, timezone_name),
    ]

    for category in non_empty_categories:
        lines.append("")
        lines.append(f"【{category}】")
        for index, article in enumerate(news_by_category[category], start=1):
            lines.extend(_format_article_line(article, index, timezone_name))
            lines.append("")

        if lines[-1] == "":
            lines.pop()

    return "\n".join(lines).strip()
