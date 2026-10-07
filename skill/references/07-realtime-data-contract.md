# 实时行情 MCP 数据契约 v3.4 CLOUD FREE-FIRST

Skill 不产生实时行情；所有价格事实由 `a_share_realtime` MCP 提供。默认数据源为 AKShare，Tushare 仅作为可选后备。

## 1. 通用字段
所有行情工具必须尽量返回：
- `source`：实际完成本次请求的数据源，不写“理论主数据源”。
- `source_endpoint`：实际接口。
- `retrieved_at`：服务端完成请求的时间。
- `as_of`：可验证的市场/Bar 时间；不得直接用 `retrieved_at` 代替。
- `freshness_basis`：时间戳依据。
- `age_minutes`：`as_of` 到当前时间的分钟差。
- `freshness`：LIVE / NEAR_LIVE / STALE / PAUSED / CLOSED / UNKNOWN。
- `warnings`：降级数据源、时间戳限制、单股失败、限流风险等。

`freshness_basis` 重点：
- `row_timestamp`：数据行自身时间戳，可信度最高。
- `bar_timestamp`：分钟K自身时间戳，最终盘中入场优先使用。
- `benchmark_minute_probe`：截面接口本身没有时间戳，以同源上证指数1分钟行情验证“市场时钟”；只证明数据源正在更新，不证明每一行严格同一秒更新。
- `retrieval_only`：无法验证市场时间，盘中不得当成实时依据。

## 2. 默认 Provider 顺序
```text
AKShare
  ├─ 东财全市场/行业截面
  ├─ 东财分钟K
  └─ 东财失败时，部分股票行情降级到新浪
        ↓
Tushare（只有配置 Token 且有权限时才加入后备链）
```

AKShare 无需 Token。Tushare 不再是系统启动前提。

## 3. 工具

### provider_status
检查所有已配置 Provider、核心行情接口、新鲜度和 SQLite 快照状态。不返回密钥。

### get_market_snapshot
全A实时截面聚合：成交额、上涨/下跌/平盘家数、中位涨跌幅等。

AKShare 东财全市场截面没有逐行时间戳，因此 v3.4 使用上证指数1分钟行情作为 market-clock probe。若 probe 失败，`freshness=UNKNOWN`，盘中只能降级分析。

### get_sector_snapshot
默认返回 AKShare/东方财富行业板块实时截面。v3.4 不再把免费数据强行称为“申万一级行业”。

板块改善速度不能由单次截面推断，必须依赖 SQLite 历史快照。

### get_stock_snapshot
批量获取最新价、昨收、OHLC、成交额及可用的5分钟涨跌/涨速等字段。

### get_realtime_universe
应用客观约束减少上下文：价格上限、代码前缀、ST、最低成交额。工具返回顺序不是推荐结果。

### get_realtime_minute_bars
免费模式最多20只/次，优先 AKShare `stock_zh_a_hist_min_em`，失败时可降级到新浪 `stock_zh_a_minute`。必须使用 Bar 自身时间戳判断新鲜度。

### get_intraday_minutes
获取单股当日分钟序列，用于短周期结构、分时高低点、回踩/突破验证。最终“现在能买吗”优先以此工具的 `bar_timestamp` 为准。

### capture_snapshot
将全市场和行业板块截面保存到 SQLite。云端 Worker 默认每300秒在 OPEN 时段自动调用。

### get_acceleration_snapshot
与约5/15/30分钟前快照比较，输出板块/个股 `accel_pct_points`。没有历史快照必须返回 `NO_PRIOR_SNAPSHOT`。

### scan_realtime_candidates
流程：
```text
强/增强行业
→ 行业成分股
→ 用户硬约束
→ 个股相对行业强弱
→ 个股加速度
→ 流动性
→ Discovery Score
```

Discovery Score 只负责发现候选，不是上涨概率，不是当日买入分。

## 4. 新鲜度硬规则
盘中：
- LIVE：<=1分钟
- NEAR_LIVE：>1且<=5分钟
- STALE：>5分钟
- UNKNOWN：无法验证 `as_of`

午间休市：PAUSED；开盘前/收盘后：CLOSED。

使用规则：
1. 市场/行业筛选：LIVE 或 NEAR_LIVE 可用；`benchmark_minute_probe` 置信度中等。
2. 最终候选“现在能买吗”：必须再拉 1MIN/5MIN Bar，优先 `bar_timestamp` 且 LIVE。
3. STALE/UNKNOWN：只给条件式预案，不给伪精确当前买点。
4. `retrieved_at` 永远不能代替 `as_of`。

## 5. 免费源风险
AKShare 聚合公开财经数据源，不提供交易所级 SLA。可能出现源限流、反爬、字段变化或短时不可用。

因此：
- Provider 失败必须显式返回 warning / fallback；
- 不静默把旧缓存当实时数据；
- 候选入场用分钟 Bar 再验证；
- 后续如有稳定付费源，可以无须修改 Skill，只扩展 Provider Router。
