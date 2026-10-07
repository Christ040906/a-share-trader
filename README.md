# A-share Trader v3.4 CLOUD FREE-FIRST

这是 v3.3 Scanner 的云端免费数据优先版本。目标是在 ChatGPT Web 中直接调用远程 MCP，用户不需要在本机长期运行 Python，也不需要先购买 Tushare 实时权限或域名。

## 架构

```text
ChatGPT Web
  ↓ HTTPS /mcp
模块化 Skill
  ↓
Remote MCP（单容器）
  ├─ AKShare Provider【默认免费】
  │   ├─ 东财全A实时截面
  │   ├─ 东财行业板块
  │   ├─ 东财分钟K
  │   └─ 部分路径失败时降级新浪
  ├─ Tushare Provider【可选】
  ├─ Provider Router【方法级自动降级】
  ├─ 5分钟 Snapshot Worker【同进程】
  └─ SQLite /data/ashare_snapshots.sqlite3
```

## v3.4 关键变化

- 默认无需 `TUSHARE_TOKEN`。
- 新增 `AkShareProvider`，全市场实时截面包含涨速/5分钟涨跌等可用字段。
- Provider Router 按方法自动尝试后备数据源，实际来源写入每次响应。
- 东财截面没有逐行时间戳时，以“上证指数1分钟 market-clock probe”验证源是否仍在更新；最终入场仍必须用股票分钟K的 Bar 时间戳确认。
- MCP Server 与 Snapshot Worker 合并为一个云服务，降低部署成本和共享 SQLite 复杂度。
- 新增 `/health`。
- 默认读取 Railway 注入的 `PORT`，无需手配端口。
- 新增 Railway `railway.json`、Volume 部署说明。

## MCP 工具

1. `provider_status`
2. `get_market_snapshot`
3. `get_sector_snapshot`
4. `get_stock_snapshot`
5. `get_realtime_universe`
6. `get_realtime_minute_bars`
7. `get_intraday_minutes`
8. `capture_snapshot`
9. `get_acceleration_snapshot`
10. `scan_realtime_candidates`

## 本地最短验证

```bash
cd mcp
python -m venv .venv
# activate .venv
pip install -e .
python scripts/check_permissions.py
ashare-realtime-mcp
```

无需 Token。

## 云端推荐

第一版优先 Railway：一个 Service + 一个挂载到 `/data` 的 Volume + Railway 自动生成的 HTTPS 域名。

详细步骤见 `deploy/README.md`。

## 仍然保留的边界

免费行情并不是交易所级实时专线。v3.4 的目标是把“网页搜索拿到午盘/昨日行情”升级为可验证的新鲜分钟级数据链，并在数据源失败时明确降级，而不是宣称零延迟或绝对稳定。
