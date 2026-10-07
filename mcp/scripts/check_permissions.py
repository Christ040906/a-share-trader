from __future__ import annotations

import json
from ashare_realtime_mcp.server import service

print(json.dumps(service().provider_status(), ensure_ascii=False, indent=2, default=str))
