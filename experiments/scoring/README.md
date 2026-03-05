# Scoring 功能更新实验报告

## 1. 背景与目标
当前日报流程中，`writer` 节点承担了过多职责（清洗、头条筛选、专题组织），导致提示词复杂、可解释性弱、调优成本高。  
本次改造目标是将“新闻价值判断”前置为独立 `scoring` 模块，并与写作模块解耦。

核心目标：
- 对 dedup 后的 `event` 逐条打分，沉淀结构化结果（主体、分项分、总分）。
- 让 `writer` 只消费“已排序候选”，保持现有输出格式不变。
- 支持实验与线上同一套参数配置，便于灰度和回归。

## 2. 打分体系定义

### 2.1 指标定义与计算
通用分（`CommonScore`）由四项组成：
- `impact`：事件对行业/产品/市场格局的实际影响（LLM 0~5）。
- `controversy`：争议、监管、伦理、舆情冲突强度（LLM 0~5）。
- `prominence`：主体头部性（规则 0~5），按 `validated_tiers` 计算：
  - 命中任一 `tier1` -> `5.0`
  - 否则命中任一 `tier2` -> `4.0`
  - 未命中 tier（但有主体）-> `2.2`
  - 未抽到主体 -> `1.5`
- `heat`：热度（规则 0~5），仅由事件簇大小 `event_size` 决定：  
  `heat = clip(0.8 + 1.5 * ln(event_size), 0, 5)`，并保留 2 位小数。

惩罚分（`PenaltyScore`）：
- `source_volume_penalty`：来源灌水惩罚（规则分）：
  - 若 `source_daily_count <= 3`，惩罚为 `0`
  - 否则 `penalty = clip(0.8 * ln(source_daily_count), 0, 2.5)`，并保留 2 位小数

总分公式：
- `FinalScore = CommonScore - penalty_weight * PenaltyScore`

当前权重（`news_scoring_spec_v2.py`）：
- `common`: impact=0.65, prominence=0.50, heat=0.20, controversy=0.10
- `penalty`: penalty_score=0.75

### 2.2 流程定义
1. 输入：`fetch + dedup` 后的事件集合（每个 event 含 title/summary/url/event_size）。
2. 分类与主体抽取（Step A）：输出事件类别与主体。
3. 通用价值评分（Step B）：输出 `impact`、`controversy`。
4. 规则分计算：程序计算 `prominence`（主体头部性）与 `heat`（热度）。
5. 惩罚分计算（Step D + 规则）：程序计算 `source_volume_penalty`。
6. 合成总分并排序：输出全量 scored events + Top10。

## 3. 分阶段示例与权重迭代
示例（AI，来自 run_20260305_202316 的 Top1）：
- 事件标题：`Google doubles spending..., Alexa + OpenAI...`
- Step A：抽取主体 `Google / Alexa / OpenAI`，分类进入 AI 对应子类。
- Step B（LLM）：impact=3.5，controversy=1.5。
- 规则分：prominence=4.5（命中头部主体），heat=0.8（由 event_size 映射）。
- 惩罚：source_volume_penalty=0。
- 结果：common=4.835，final=4.835。

权重迭代思路：
- 早期版本惩罚过重，出现“高价值新闻被压分”问题。
- 调整后提高 `impact/prominence` 主导性，并降低惩罚系数到 0.75，排序更接近人工编辑直觉。
- 下一步尝试了“原版提示词对齐”方案：先用原版提示词产出基准排序，再将“当前分项结果 + 基准排序差异”喂给 AI 自动给出新权重，目标是让当前评分结果尽量 align with 原版结果。

## 4. 实验结果（run_20260305_202316）

### 4.1 总体性能
- 总耗时：`59.392s`
- 其中：fetch `0.327s`，dedup `7.003s`，score `52.062s`
- Token：`27,064`（prompt `19,108` + completion `7,956`）

### 4.2 分类结果统计
| Category | Raw | Dedup | Scored | Top10 | Score耗时(s) | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| AI | 104 | 83 | 83 | 10 | 19.584 | 19,634 |
| GAMES | 12 | 12 | 12 | 10 | 13.298 | 3,292 |
| MUSIC | 18 | 17 | 17 | 10 | 19.180 | 4,138 |

### 4.3 结论
- 模块化打分已能稳定产出“可解释分项 + 可排序总分”。
- 当前瓶颈在 `score` 阶段（占总耗时约 87.7%），后续优化应聚焦批大小、并发与 prompt 压缩。
- 该版本可用于上线前灰度验证，建议继续用人工 Top10 对照做 1~2 周权重微调。
