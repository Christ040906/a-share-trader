# v3.4 部署：Railway 优先

目标：只部署一个常驻服务，同时运行 MCP HTTP endpoint 与 5 分钟快照线程。默认不需要 Tushare Token，不需要购买域名。

## 本地验证

```bash
cd mcp
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e .
python scripts/check_permissions.py
ashare-realtime-mcp
```

本地地址：
- MCP: `http://127.0.0.1:8000/mcp`
- Health: `http://127.0.0.1:8000/health`

## Railway 部署

1. 将整个项目放入 GitHub 仓库。
2. Railway 新建 Project，选择该仓库。
3. Railway 会读取根目录 `railway.json` 并使用 `deploy/Dockerfile`。
4. 给服务添加一个 Volume，挂载到 `/data`。
5. Variables 最少设置：

```text
MARKET_DATA_PROVIDER_ORDER=akshare,tushare
ENABLE_SNAPSHOT_WORKER=true
SNAPSHOT_INTERVAL_SECONDS=300
SNAPSHOT_DB_PATH=/data/ashare_snapshots.sqlite3
SNAPSHOT_RETENTION_DAYS=3
```

`TUSHARE_TOKEN` 可以完全不填。只有以后主动购买 Tushare 实时权限时再配置。

6. Networking → Public Networking → Generate Domain。
7. 得到类似 `https://xxxx.up.railway.app` 的 HTTPS 地址。
8. 检查：
   - `https://xxxx.up.railway.app/health`
   - MCP URL：`https://xxxx.up.railway.app/mcp`
9. Railway 的 Serverless/App Sleeping 建议关闭。我们的快照线程需要交易时段持续运行。

## ChatGPT Web 连接

在 ChatGPT Web 的 Plugins 中创建 Custom MCP Server，Server URL 填：

```text
https://xxxx.up.railway.app/mcp
```

第一轮只测试：
1. `provider_status`
2. `get_market_snapshot`
3. `get_sector_snapshot`
4. 等快照积累至少两个采样点后测试 `get_acceleration_snapshot`
5. 最后测试 `scan_realtime_candidates`

## 数据与密钥

- AKShare 不需要 Token。
- Tushare Token 只允许放 Railway Variables / 本机环境变量。
- 不要写入 Skill、Git、ZIP、日志和 MCP 返回值。
- SQLite 必须放 `/data`，否则容器重启后快照会丢失。

## 为什么 v3.4 不再使用两个容器

v3.3 把 MCP 与 snapshot-worker 分成两个服务。云端个人使用时这样会增加费用、部署步骤和共享 SQLite 的复杂度。v3.4 把快照 Worker 作为 MCP 进程中的 daemon thread 启动：一个服务、一个 Volume、一个 HTTPS 地址即可。

## SQLite 容量
默认只保留 3 天全市场快照。Acceleration 实际只需要最近 5–120 分钟，3 天已经足够覆盖跨交易日边界，同时更适合 Railway Free/低价 Volume。策略长期复盘以后单独保存“候选/决策结果”，不建议永久保存每个5分钟的全市场原始截面。
