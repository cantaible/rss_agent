import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from config import (
    DAILY_NEWS_CATEGORIES,
    DEDUP_EXPERIMENT_DATE,
    NEWS_DEDUP_DEBUG,
    NEWS_DEDUP_EMBEDDING_MODEL,
    NEWS_DEDUP_MODE,
    NEWS_DEDUP_THRESHOLD,
    NEWS_SCORING_DEBUG,
    NEWS_SCORING_TOPK,
)
from news_dedup import dedupe_news_payload
from news_scoring_spec_v2 import get_category_strategy, score_events
from simple_bot import llm_reasoning
from tools import fetch_news


def _beijing_window_utc(date_str: str) -> Tuple[datetime, datetime]:
    """
    将北京时间自然日转换为 UTC 窗口，便于实验可复现。
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    beijing_tz = timezone(timedelta(hours=8))
    start_bj = dt.replace(tzinfo=beijing_tz)
    end_bj = start_bj + timedelta(days=1) - timedelta(seconds=1)
    return start_bj.astimezone(timezone.utc), end_bj.astimezone(timezone.utc)


def _save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _escape_md_cell(text: Any) -> str:
    """转义 Markdown 表格单元格中的特殊字符，避免表格断裂。"""
    return str(text or "").replace("\n", " ").replace("|", "\\|").strip()


def _save_markdown_report(
    run_dir: str,
    summary: List[Dict[str, Any]],
    total_timing: Dict[str, int],
    total_tokens: Dict[str, int],
) -> str:
    """
    生成评分实验 Markdown 报告：
    1) 全局耗时/token 概览
    2) 分类汇总
    3) 各分类全量 scored_events 明细（含分数子项）
    """
    report_path = os.path.join(run_dir, "SCORING_REPORT.md")
    lines: List[str] = []
    lines.append("# Scoring Experiment Report")
    lines.append("")
    lines.append(f"- Run Dir: `{run_dir}`")
    lines.append(f"- Date Window: `{DEDUP_EXPERIMENT_DATE} (Beijing)`")
    lines.append("")
    lines.append("## Overall Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| total_ms | {int(total_timing.get('total_ms', 0))} |")
    lines.append(f"| fetch_ms | {int(total_timing.get('fetch_ms', 0))} |")
    lines.append(f"| dedup_ms | {int(total_timing.get('dedup_ms', 0))} |")
    lines.append(f"| score_ms | {int(total_timing.get('score_ms', 0))} |")
    lines.append(f"| total_tokens | {int(total_tokens.get('total_tokens', 0))} |")
    lines.append(f"| prompt_tokens | {int(total_tokens.get('prompt_tokens', 0))} |")
    lines.append(f"| completion_tokens | {int(total_tokens.get('completion_tokens', 0))} |")
    lines.append("")
    lines.append("## Category Summary")
    lines.append("")
    lines.append("| Category | Mode | Raw | Dedup | Scored | Top10 | fetch_ms | dedup_ms | score_ms | total_ms | total_tokens |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in summary:
        lines.append(
            f"| {_escape_md_cell(row.get('category'))} | {_escape_md_cell(row.get('mode'))} | "
            f"{int(row.get('raw_count', 0))} | {int(row.get('dedup_count', 0))} | "
            f"{int(row.get('scored_count', 0))} | {int(row.get('top10_count', 0))} | "
            f"{int(row.get('fetch_ms', 0))} | {int(row.get('dedup_ms', 0))} | "
            f"{int(row.get('score_ms', 0))} | {int(row.get('total_ms', 0))} | "
            f"{int(row.get('total_tokens', 0))} |"
        )
    lines.append("")

    for row in summary:
        category = str(row.get("category") or "").strip()
        if not category:
            continue
        scored_events_path = os.path.join(run_dir, category, "scored_events.json")
        if not os.path.exists(scored_events_path):
            continue
        with open(scored_events_path, "r", encoding="utf-8") as f:
            scored_events = json.load(f)
        if not isinstance(scored_events, list):
            continue

        lines.append(f"## {category} Scored Events ({len(scored_events)})")
        lines.append("")
        lines.append("| Rank | Final | Common | Impact | Prominence | Heat | Controversy | Penalty | SourcePenalty | Subjects | Title |")
        lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|")
        for idx, item in enumerate(scored_events, start=1):
            if not isinstance(item, dict):
                continue
            common = item.get("common") or {}
            penalty = item.get("penalty") or {}
            subjects = item.get("event_subjects") or []
            if not isinstance(common, dict):
                common = {}
            if not isinstance(penalty, dict):
                penalty = {}
            if not isinstance(subjects, list):
                subjects = []

            subject_text = "、".join(str(s) for s in subjects[:4])
            if len(subjects) > 4:
                subject_text += " 等"
            title = _escape_md_cell(item.get("source_title"))

            lines.append(
                f"| {idx} | {float(item.get('final_score', 0.0)):.3f} | "
                f"{float(common.get('common_score', 0.0)):.3f} | "
                f"{float(common.get('impact', 0.0)):.3f} | "
                f"{float(common.get('prominence', 0.0)):.3f} | "
                f"{float(common.get('heat', 0.0)):.3f} | "
                f"{float(common.get('controversy', 0.0)):.3f} | "
                f"{float(penalty.get('penalty_score', 0.0)):.3f} | "
                f"{float(penalty.get('source_volume_penalty', 0.0)):.3f} | "
                f"{_escape_md_cell(subject_text)} | {title} |"
            )
        lines.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return report_path


def run() -> None:
    start_utc, end_utc = _beijing_window_utc(DEDUP_EXPERIMENT_DATE)
    now_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    run_dir = os.path.join(base_dir, "results", f"run_{now_tag}")
    os.makedirs(run_dir, exist_ok=True)

    print(
        f"🧪 Scoring experiment start. date={DEDUP_EXPERIMENT_DATE}, "
        f"window_utc={start_utc.isoformat()}~{end_utc.isoformat()}"
    )

    summary: List[Dict[str, Any]] = []
    total_timing = {"fetch_ms": 0, "dedup_ms": 0, "score_ms": 0, "total_ms": 0}
    total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    for category in DAILY_NEWS_CATEGORIES:
        print(f"\n📥 Running category={category}")
        category_dir = os.path.join(run_dir, category)
        os.makedirs(category_dir, exist_ok=True)

        # 1) 拉取新闻（记录耗时）
        fetch_t0 = time.perf_counter()
        raw_payload = fetch_news(category, start_dt=start_utc, end_dt=end_utc)
        fetch_ms = int((time.perf_counter() - fetch_t0) * 1000)
        _save_json(os.path.join(category_dir, "raw_payload.json"), raw_payload)

        # 2) 去重（复用现有逻辑，记录耗时）
        dedup_t0 = time.perf_counter()
        deduped_payload, dedup_meta, dedup_trace = dedupe_news_payload(
            raw_payload,
            enabled=True,
            mode=NEWS_DEDUP_MODE,
            threshold=NEWS_DEDUP_THRESHOLD,
            debug=NEWS_DEDUP_DEBUG,
            embedding_model=NEWS_DEDUP_EMBEDDING_MODEL,
        )
        dedup_ms = int((time.perf_counter() - dedup_t0) * 1000)
        _save_json(os.path.join(category_dir, "deduped_payload.json"), deduped_payload)

        # 3) 读取策略快照并保存（便于回放）
        strategy = get_category_strategy(category)
        _save_json(os.path.join(category_dir, "strategy_snapshot.json"), strategy)

        # 4) 执行评分（记录耗时）
        score_t0 = time.perf_counter()
        scored_events, scoring_meta = score_events(
            category=category,
            deduped_payload=deduped_payload,
            dedup_trace=dedup_trace,
            llm=llm_reasoning,
            topk=NEWS_SCORING_TOPK,
            debug=NEWS_SCORING_DEBUG,
        )
        score_ms = int((time.perf_counter() - score_t0) * 1000)

        # 5) 保存评分产物
        _save_json(os.path.join(category_dir, "scored_events.json"), scored_events)
        _save_json(os.path.join(category_dir, "top10.json"), scored_events[:NEWS_SCORING_TOPK])

        # 6) 记录 step_trace：每个事件是否执行了 A2/C/D（由策略决定）
        step_trace = {
            "category": category,
            "mode": strategy.get("mode"),
            "flags": {
                "use_entity_tier_mapping": bool(strategy.get("use_entity_tier_mapping")),
                "use_penalty": bool(strategy.get("use_penalty")),
            },
            "event_ids": [x.get("event_id") for x in scored_events],
        }
        _save_json(os.path.join(category_dir, "step_trace.json"), step_trace)

        # 7) 统计 timing / token（token 优先使用 scoring_meta 返回）
        token_usage = ((scoring_meta or {}).get("token_usage") or {}).get("overall", {})
        prompt_tokens = int(token_usage.get("prompt_tokens", 0))
        completion_tokens = int(token_usage.get("completion_tokens", 0))
        total_tokens_cat = int(token_usage.get("total_tokens", 0))

        timing_metrics = {
            "category": category,
            "fetch_ms": fetch_ms,
            "dedup_ms": dedup_ms,
            "score_ms": score_ms,
            "score_detail_ms": (scoring_meta or {}).get("timing_ms", {}),
            "total_ms": fetch_ms + dedup_ms + score_ms,
        }
        token_metrics = {
            "category": category,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens_cat,
            "by_step": ((scoring_meta or {}).get("token_usage") or {}).get("by_step", {}),
        }
        _save_json(os.path.join(category_dir, "timing_metrics.json"), timing_metrics)
        _save_json(os.path.join(category_dir, "token_metrics.json"), token_metrics)

        row = {
            "category": category,
            "mode": strategy.get("mode"),
            "raw_count": len(raw_payload.get("data", [])) if isinstance(raw_payload, dict) else 0,
            "dedup_count": len(deduped_payload.get("data", [])) if isinstance(deduped_payload, dict) else 0,
            "scored_count": len(scored_events),
            "top10_count": len(scored_events[:NEWS_SCORING_TOPK]),
            "fetch_ms": fetch_ms,
            "dedup_ms": dedup_ms,
            "score_ms": score_ms,
            "total_ms": fetch_ms + dedup_ms + score_ms,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens_cat,
            "fail_open": (scoring_meta or {}).get("fail_open", False),
            "warnings": (scoring_meta or {}).get("warnings", []),
        }
        summary.append(row)

        total_timing["fetch_ms"] += fetch_ms
        total_timing["dedup_ms"] += dedup_ms
        total_timing["score_ms"] += score_ms
        total_timing["total_ms"] += row["total_ms"]
        total_tokens["prompt_tokens"] += prompt_tokens
        total_tokens["completion_tokens"] += completion_tokens
        total_tokens["total_tokens"] += total_tokens_cat

    # 8) 保存全局汇总
    _save_json(os.path.join(run_dir, "summary.json"), summary)
    _save_json(os.path.join(run_dir, "timing_metrics.json"), total_timing)
    _save_json(os.path.join(run_dir, "token_metrics.json"), total_tokens)
    report_path = _save_markdown_report(run_dir, summary, total_timing, total_tokens)

    print(f"\n✅ Done. Results saved to: {run_dir}")
    print(f"📝 Report saved to: {report_path}")
    print("\n=== Summary ===")
    for row in summary:
        print(
            f"{row['category']:>6} | mode={row['mode']:<6} "
            f"raw={row['raw_count']:<4} dedup={row['dedup_count']:<4} "
            f"scored={row['scored_count']:<4} "
            f"ms={row['total_ms']:<6} tokens={row['total_tokens']:<8}"
        )


if __name__ == "__main__":
    run()
