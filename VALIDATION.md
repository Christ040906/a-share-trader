# Validation status — v3.4 CLOUD FREE-FIRST

## Completed
- Python syntax compilation: PASS.
- Unit tests: 11 PASS.
- Tests cover filtering, freshness, SQLite history, source-matched snapshots, discovery ranking, AKShare Eastmoney normalization, Eastmoney→Sina fallback, and provider-router fallback.
- MCP SDK v2 `MCPServer.run(streamable-http, host, port, streamable_http_path, stateless_http, json_response)` shape checked against current official SDK documentation.
- MCP `custom_route('/health')` pattern checked against current official SDK documentation.
- AKShare current interfaces checked against current project documentation/source: `stock_zh_a_spot_em`, `stock_zh_a_spot`, `stock_zh_a_hist_min_em`, `stock_zh_a_minute`, `stock_board_industry_name_em`, `stock_board_industry_cons_em`, `index_zh_a_hist_min_em`.
- Current dependency ranges set for October 2026: MCP SDK v2.x and AKShare 1.19.x.

## Not completed in this environment
This execution environment cannot resolve PyPI/data hosts from the container, so it was not possible to install the live dependencies and make an actual AKShare network request here.

Therefore the next acceptance gate is a real deployment/local run:
1. install dependencies;
2. run `python scripts/check_permissions.py`;
3. confirm `provider_status`;
4. verify `/health`;
5. verify market/sector `as_of` during A-share trading hours;
6. verify a stock 1MIN/5MIN bar has `bar_timestamp` within the freshness threshold;
7. let the worker collect at least two snapshots and test acceleration/candidate scanning.

Do not tune strategy weights before this data-chain acceptance passes.
