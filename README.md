# Token Heatmap

基于 new-api `logs` 表统计的 **Token 用量日历热力图**（SVG 直出，GitHub 贡献图风格）。

## 在线地址

部署后通过反代或端口映射访问（路径均相对于站点根）：

- 热力图: `GET /token/2026.svg`（年份可换 2000-2100）
- 直接 `<img src="/token/2026.svg">` 即可嵌入任意页面

## 数据口径

- 数据源: 直连 new-api 的 PostgreSQL（只读；根目录 `.env` 提供连接凭据，已 gitignore）
- 统计: `logs` 表 `type=2`（成功请求）的 `prompt_tokens + completion_tokens`，按 **Asia/Shanghai 时区**聚合到自然日
- 不含计费额度（quota）、不含失败请求
- 色阶: 5 级绿（GitHub 绿），按 **分位数分桶**（rank-based；相同 token 值保持同档，对数映射会把高基数数据全挤进最深档）

## 部署

```bash
# 1. 复制模板并填写 new-api 的真实 PostgreSQL 凭据
cp .env.template .env

# 2. 构建并启动（镜像内依赖已预装，运行时不会安装依赖）
docker compose up -d --build
```

- 容器: `token-heatmap`（FastAPI + uvicorn，依赖预装在镜像 `/opt/venv`），端口映射按 `docker-compose.yml` 配置（默认 `127.0.0.1:3004:8000`）
- ⚠️ compose 有 `name: token-heatmap` 固定项目名——**不要删**，否则 `docker compose down` 会因目录名撞车误伤其他 compose 项目
- 容器挂载的外部网络由 `.env` 的 `NETWORK_NAME` 指定（默认 `proxy-network`；1Panel 等环境设为对应外部网络名）。部署前确认该外部网络已存在：`docker network create proxy-network`（或按环境改 `.env` 后重建）

## 端点

| 端点 | 说明 |
|---|---|
| `GET /token/{year}.svg` | 某年热力图（2000-2100），`image/svg+xml`，Cache-Control 600s |
| `GET /healthz` | 健康检查 `{"status":"ok"}` |

## 布局

- 53 周列 × 7 行（周一~周日），未来日期浅灰占位
- 每个格子 `<title>` 内带精确日期与 token 数（浏览器直接打开 SVG 可见 hover）

## 目录结构

```
token-heatmap/
├── app/
│   ├── main.py          # FastAPI 路由和装配
│   ├── config.py        # 时区、布局与颜色常量
│   ├── repository.py    # 只读 PostgreSQL 查询
│   └── heatmap.py       # 分桶与 SVG 渲染
├── tests/               # 不访问真实数据库的 pytest 回归测试
├── pyproject.toml       # uv 项目与依赖定义
├── uv.lock              # 锁定依赖
├── .env.template        # PostgreSQL 凭据模板（复制为 .env 后填写）
├── Dockerfile
└── docker-compose.yml
```

## 开发与测试（uv）

```bash
# 首次或依赖变更后创建/同步 .venv（开发依赖包含 pytest、httpx）
uv sync
uv run pytest -q

# 修改依赖后更新锁文件
uv lock
```

- 改 `app/` 代码后容器需重启加载（uvicorn 无 auto-reload）：`docker compose restart token-heatmap`
- `./app:/app` 保持挂载；依赖在镜像 `/opt/venv`，restart 不会再联网安装依赖。
