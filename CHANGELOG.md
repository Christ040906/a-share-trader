# Changelog

## v3.4 CLOUD FREE-FIRST
- 默认实时 Provider 从 Tushare 改为 AKShare，无 Token 可启动。
- 新增 AKShare 东财全市场、行业板块、分钟K适配。
- 股票实时截面在东财失败时可降级到 AKShare 新浪接口。
- 新增方法级 `ProviderRouter`；配置 Tushare Token 后可作为额外后备 Provider。
- 引入 `freshness_basis`，区分行时间戳、Bar 时间戳、benchmark minute probe 和 retrieval-only。
- 最终盘中入场要求分钟 Bar 时间戳验证，避免把无时间戳截面伪装成精确实时数据。
- Snapshot Worker 合并进 MCP 主进程，云端只需一个服务。
- 新增 `/health`、Railway `PORT` 支持、`railway.json`、持久 Volume 方案。
- 免费模式分钟批量限制为每次20只，降低公开源限流风险。

## v3.3 SCANNER
- 新增 SQLite 连续快照、Acceleration 和实时候选 Scanner。
