---
name: a-share-sector-rotation-trend-system
version: "3.4-cloud-free-first"
description: >
  A股短线至波段的板块轮动、全市场候选发现、单股诊断与持仓管理 Skill。
  盘中任务必须先调用实时行情 MCP，并以行情时间戳、新鲜度和市场/板块/个股共振为前提进行判断。
---

# A股板块轮动与趋势交易 Skill v3.4 CLOUD FREE-FIRST

## 1. 目标
默认服务于：盘中/盘后选股、单股诊断、多股比较、持仓管理。
默认持有周期：2个交易日至数周。

核心闭环：
> 实时数据 → 市场状态 → 板块强度/改善 → 核心股/相对强弱 → 结构/Setup → 风险过滤 → 触发/失效/盈亏比

不要预测必涨，不猜最低点，不用公司故事替代价格行为。

## 2. 盘中实时行情是硬依赖
用户出现“今天、现在、截至目前、盘中、刚刚、目前价、能不能买、接不接回”等表达时，必须先使用 `a_share_realtime` MCP。

优先工具顺序：
1. `provider_status`
2. `get_market_snapshot`
3. `get_sector_snapshot`
4. 选股时再调用 `get_realtime_universe` 或 `get_stock_snapshot`
5. 有连续快照时调用 `get_acceleration_snapshot` / `scan_realtime_candidates`
6. 最终候选调用 `get_realtime_minute_bars` / `get_intraday_minutes`

硬规则：
- 行情工具回答“价格发生了什么”；Web/新闻/公告回答“为什么可能发生”。二者不得互相替代。
- 任何价格结论先检查 `as_of`、`age_minutes`、`freshness`。
- `LIVE`：<=1分钟；`NEAR_LIVE`：>1且<=5分钟；盘中 `STALE`：>5分钟。
- 市场/板块截面若 `freshness_basis=benchmark_minute_probe`，可用于候选发现但置信度降一级；最终候选入场必须再用分钟K的 `bar_timestamp` 验证。
- 候选最终入场判断优先要求 LIVE；市场/板块判断允许 NEAR_LIVE。
- MCP不可用、时间戳缺失或 STALE 时，必须写明“非实时/数据不足”，只给条件计划，不给伪精确当前买点。
- `retrieved_at` 不是行情时间，不能用它冒充 `as_of`。
- Web 搜索到的盘口页面、新闻快照、午盘摘要不得覆盖 MCP 返回的更新行情。

数据契约见 `references/07-realtime-data-contract.md`。

## 3. 默认交易约束
读取 `config/defaults.yaml`。当轮用户明确修改时，以用户最新要求为准。

## 4. 按任务加载 references
不要默认读取全部文件。

- “截至目前有什么推荐 / 今天有什么机会”
  - `01-market-sector.md`
  - `02-stock-discovery-ranking.md`
  - `04-risk-events.md`
  - `06-output-formats.md`
  - `07-realtime-data-contract.md`
- “XX现在能买吗 / 要不要接回 / 什么位置买”
  - `01-market-sector.md`
  - `03-entry-execution.md`
  - `04-risk-events.md`
  - `06-output-formats.md`
  - `07-realtime-data-contract.md`
- “这几只哪个好”
  - `02-stock-discovery-ranking.md`
  - `03-entry-execution.md`
  - `04-risk-events.md`
  - `06-output-formats.md`
- “公司基本面 / 长期价值 / 财报 / 估值”
  - `05-company-research.md`
  - 如同时问交易，再补 `03-entry-execution.md`
- “复盘 / 验证策略”
  - `08-review-validation.md`

## 5. 全市场选股总流程
```text
provider_status
→ get_market_snapshot
→ get_sector_snapshot
→ 应用用户约束
→ 判断市场状态
→ 找“当前强”与“正在改善”的板块
→ 有连续快照时优先 `scan_realtime_candidates`
→ 无连续快照时退回 `get_realtime_universe` 客观预筛
→ 每个强方向找龙头/趋势核心/次核心
→ 同板块替代检查
→ 结构与Setup筛选
→ get_realtime_minute_bars / get_intraday_minutes 验证Top候选
→ 公告/新闻风险过滤
→ 跨板块排序
→ Top3去同质化
```

必须同时回答：
> 谁最强？谁正在变强？谁的位置最好？

`get_realtime_universe` 只是数据预筛，不是最终推荐器。不得把工具返回顺序直接当作Top3。

## 6. 单股交易总流程
```text
get_stock_snapshot
+ get_intraday_minutes(1MIN或5MIN)
+ get_sector_snapshot
+ get_market_snapshot
→ 检查 freshness
→ 板块是否仍可交易
→ 个股是否仍是核心/强势股
→ 日线/盘中结构是否健康
→ 当前是否出现有效Setup
→ 同板块是否有明显更优替代
→ 失效位是否清楚
→ 第一目标是否有足够空间
→ A/B/C/D/BLOCK
```

## 7. 硬性禁止
- 用旧价格、昨日价格或午盘摘要冒充当前价。
- 用网页新闻搜索替代实时行情源。
- 把 `retrieved_at` 当成行情 `as_of`。
- 搜到几只股票就称为“全市场Top3”。
- 把预筛分数解释为上涨概率。
- 业绩好=短期会上涨；低PE=短线机会；热门题材=龙头。
- 涨幅最大=龙头；突破前高=机械追；跌到MA20=机械买。
- 单一MACD/RSI/KDJ给买卖结论。
- 没有失效位就给具体买点。
- 为凑Top3加入弱票。
- 因用户点名而忽略同板块明显更优替代。

## 8. 数据不足时的固定降级
若实时工具不可用、权限不足、行情时间戳缺失或盘中关键数据 >5分钟：
> 当前缺少满足实时性要求的行情，以下仅做结构性/条件式分析，不把旧行情当作当前行情。

随后可以给触发条件，但不要生成伪精确当前价、买点或盘中强弱结论。
