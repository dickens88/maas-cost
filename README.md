# MaaS Token 用量看板

实时查询华为云 ModelArts Studio (MaaS) 的调用统计，按 API Key / 模型展示 Token 用量。本地不存数据，只有进程内的短时缓存。

## 快速开始

```bash
cp .env.example .env        # 填 HW_AK / HW_SK
docker compose up -d --build
# 打开 http://localhost:8765
```

本地开发：

```bash
cd backend && uv venv .venv && uv pip install -r requirements.txt pytest httpx
.venv/bin/uvicorn app.main:app --port 8765
cd frontend && npm install && npm run dev      # http://localhost:5178，/api 代理到 8765
cd backend && .venv/bin/python -m pytest -q
```

## 凭据

AK/SK 对应的 IAM 用户需要 ModelArts MaaS 监控只读与 `modelarts:apiKey:list`。统计接口仅在西南-贵阳一（`cn-southwest-2`）可用。

## 查询方式与限制

| 页面区块 | 调用的接口 | 每次调用数 |
|---|---|---|
| KPI、Key 排行、模型分布、Key × 模型 | 每个 Key 标签 + `""` 各一次 `list-service-statistics` | Key 数 + 1（共用缓存） |
| KPI 环比 | 上一周期全量一次 | 1 |
| 趋势（按模型堆叠） | 每个时间桶一次 | 小时 ≤ 48 / 天 ≤ 30 / 周 ≤ 5 |
| Key 明细抽屉的趋势 | 每个时间桶带该标签一次 | 同上 |

- 只能查最近 30 天（MaaS 保留约 31 天，跨度 > 30 天会被拒绝）；上一周期超出保留期时环比显示"超出保留期"。
- 趋势不按 Key 堆叠：每个 Key 每个时间桶都要单独调用，30 天 × N 个 Key 会超过 200 次/分钟限流。
- 缓存：包含"现在"的窗口缓存 5 分钟（结束时间取整到 5 分钟，看到的数据最多晚 5 分钟），已结束超过 1 小时的窗口缓存 1 小时。重启即清空。
- 限流：全局 `RATE_LIMIT_PER_MIN`（默认 150，平台上限 200/分钟/用户），并发 `API_CONCURRENCY`（默认 4，实测 8 并发时服务端排队反而更慢）。
- 没有单价：MaaS 不提供模型单价接口，BSS 询价接口需要未公开的计费项编码，所以只展示用量不展示花费。

## 已实测的 MaaS 接口行为（与文档不一致或文档未写）

- AK/SK 签名可直接调用统计接口，无需 IAM Token。
- `prompt_token` **包含** `cache_token`；`total = prompt + completion`；单位千 tokens。
- `cache_hit_ratio` 是百分数（0-100），不是文档写的 0-1。
- 时间窗口可任意切分且严格可加（分钟级聚合），最近 1 分钟内的调用即可查到。
- `api_keys` 只认标签；按 Key ID 查**返回 200 且为 0**，不会报错。
- Σ 各标签 + `""` = 全量。`""` 包含在线体验 **以及所有未设置标签的 Key**，无法再拆。
- `show-statistics` 默认只统计 Text Generation，不含 Rerank / Embedding 等。
- 限流：统计接口 200 次/分钟/用户（429 返回 `limit:200,time:1 minute`）；`show-detail-chart` 为 20 秒 1 次。

## REST API

| 方法 | 路径 | 参数 |
|---|---|---|
| GET | `/api/overview` | `start`、`end`、`model` |
| GET | `/api/trend` | `start`、`end`、`granularity=hour\|day\|week`、`metric=tokens\|requests`、`label`、`model` |
| GET | `/api/usage/keys` | `start`、`end`、`model` |
| GET | `/api/usage/models` | `start`、`end`、`label` |
| GET | `/api/usage-matrix` | `start`、`end`、`model` |

`start`/`end` 为本地日期（含），默认近 7 天；`label=""` 表示未归属桶。超出 30 天返回 400，MaaS 出错返回 502。
