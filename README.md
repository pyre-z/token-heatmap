<h1 align="center">Token Heatmap</h1>

<p align="center">
    <img src="https://count.pyre-z.me/token/@?scale=1.5" height="150" alt="Token Heatmap" />
    <br>
    <a href="https://github.com/pyre-z/token-heatmap"><img alt="GitHub" src="https://img.shields.io/badge/GitHub-pyre--z%2Ftoken--heatmap-181717?logo=github&logoColor=white"></a>
    <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/License-GPL--3.0-blue.svg"></a>
    <img alt="Python" src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white">
</p>

基于 **AI API Gateway 日志**统计的 **Token 用量日历热力图**（SVG 直出，GitHub 贡献图风格）。支持滚动年 / 年 / 月 / 日四种粒度、主题族（day/night 配色）、中英双语、深浅色自动切换与背景控制。

## 在线地址

部署后通过反代或端口映射访问（路径均相对于站点根）：

- 配置页: `GET /token/`（可视化调整参数并生成嵌入代码）
- 热力图: `GET /token/@?grain=auto&theme=github&lang=zh&darkmode=auto&bg=0&scale=1`

```html
<img src="https://your-host/token/@?grain=auto" alt="Token 用量热力图">
```

## 参数

| 参数                     | 取值                                     | 默认     | 说明                                                                                                                         |
| ------------------------ | ---------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `grain`                  | `auto` / `year` / `month` / `day`        | `auto`   | 时间粒度：`auto`=滚动年（今日往前一年，GitHub 原版效果）、`year`=自然年、`month`=月、`day`=日（24 小时柱状）                 |
| `year` / `month` / `day` | 数字                                     | 当前日期 | 目标日期；缺省自动取当天。`grain=month` 需 `year+month`，`grain=day` 需完整日期。`grain=auto` 忽略日期参数（区间由今天决定） |
| `theme`                  | 主题族名（内置 `github`，另有 `sakura`） | `github` | 主题族，见下方「主题配置」                                                                                                   |
| `lang`                   | `zh` / `en`                              | `zh`     | 界面语言（月份/星期/图例/统计标签）；zh 统计用 万/亿，en 用 K/M/B                                                            |
| `darkmode`               | `0` / `1` / `auto`                       | `auto`   | `0`=白天配色、`1`=夜晚配色、`auto`=跟随访问者系统深浅自动切换（内嵌 CSS `prefers-color-scheme`）                             |
| `bg`                     | `0` / `1`                                | `0`      | `0`=透明背景、`1`=使用主题 background 色（随 darkmode 取 day/night 对应背景）                                                |
| `scale`                  | `0.1`–`10`                               | `1`      | 缩放倍数（渲染尺寸乘 scale，viewBox 不变，矢量等比缩放）                                                                     |

示例：

```
/token/@?grain=auto
/token/@?grain=month&year=2026&month=9
/token/@?grain=day&theme=github&lang=en&darkmode=1&bg=1
/token/@?grain=year&scale=2
```

## 主题配置

主题以 **JSON 文件**形式放在项目根 `themes/` 文件夹（文件名 = 主题族名，如 `themes/github.json`），每个文件包含 `day`（白天）与 `night`（夜晚）两套配色，由 `darkmode` 参数选择；`darkmode=auto` 时通过内嵌 CSS 变量（`:root` 默认 day，`@media (prefers-color-scheme: dark)` 覆盖为 night）让 SVG 跟随访问者系统深浅自动切换。

### 内置主题

| 主题     | 风格      | day 色阶（空 → 满）   | night 色阶（空 → 满） |
| -------- | --------- | --------------------- | --------------------- |
| `github` | GitHub 绿 | `#ebedf0` → `#216e39` | `#161b22` → `#39d353` |
| `sakura` | 樱花粉    | `#f4e9ee` → `#cd3c6d` | `#241b20` → `#ff93b6` |

示例：`/token/@?grain=auto&theme=sakura&bg=1`（`bg=1` 使用主题背景色，深浅切换更自然）

```json
{
  "day": {
    "colors": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
    "text": "#767676",
    "title": "#24292f",
    "legend": "#767676",
    "background": "#ffffff"
  },
  "night": {
    "colors": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
    "text": "#8b949e",
    "title": "#c9d1d9",
    "legend": "#7d8590",
    "background": "#0d1117"
  }
}
```

**热更新（watchdog）**：服务启动后用 watchdog 监听 `themes/` 目录，新增 / 修改 / 删除任意 `*.json` 都会自动重载主题表，**无需重启容器**。主题表带单调递增的「主题版本」，重载会使旧 SVG 缓存立即失效；动态 SVG 响应改为 `Cache-Control: public, no-cache` + 内容 `ETag`（客户端可重新验证），因此宿主编辑 JSON 后立即生效，不再有长浏览器缓存。容器内主题目录 = 宿主 `themes/`（bind mount，`THEMES_DIR=/themes` 可覆盖；生产镜像默认 `/app/themes`）。

新增主题只需在 `themes/` 放一个 `名字.json`（族名即文件名，配齐 `day`/`night` 两套配色，`colors` 必须 5 档、每个颜色严格为 6 位十六进制 `#[0-9A-Fa-f]{6}`），`theme` 参数即族名。删除文件即移除该主题。

- 内置 `github` 兜底：`themes/` 目录不存在 / 为空 / 全部删除时仍可用 `theme=github`（内置配色与 `themes/github.json` 同构）；同名文件存在时以文件内容覆盖内置。
- 非法 JSON / 结构不完整（缺 `day`/`night`、`colors` 不足 5 档、颜色不是严格 6 位十六进制等）自动跳过并告警，不影响其余主题。
- 旧版 `github-dark` 已随族收编移除，请改用 `theme=github&darkmode=1`。

## 端点

| 端点                 | 说明                                                                                                                                                              |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /token/@?...`   | 热力图 SVG（参数见上表），`image/svg+xml`，`Cache-Control: public, no-cache` + 内容 `ETag`（可重新验证）；服务端另有 60s TTL 内存缓存（`CACHE_TTL_SECONDS` 可配） |
| `GET /token/`        | 参数可视化配置页                                                                                                                                                  |
| `GET /token/healthz` | 存活检查（liveness）：仅表示进程可响应，不查数据库，固定返回 `{"status":"ok"}`                                                                                    |
| `GET /token/readyz`  | 就绪检查（readiness）：配置有效且所选 `SOURCE` 数据源已配置；否则返回 503（不泄露连接信息）                                                                       |

## 多数据源（Source 架构）

服务端通过 `SOURCE` 环境变量选择数据源（不改 URL），实现 `Source` 抽象接口即可扩展新网关：

- `new-api`（默认）— 直连 new-api 的 PostgreSQL `logs` 表
- `sub2api` — 直连 sub2api 的 PostgreSQL `usage_logs` 表（token 口径含缓存，官方口径）

### 数据口径

| 数据源    | 表 / 口径                                                                           | 环境变量（前缀 `PG*` 同款）                                                          |
| --------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `new-api` | `logs` 表 `type=2`（成功请求）的 `prompt_tokens + completion_tokens`                | `PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD`                                         |
| `sub2api` | `usage_logs` 表 `input + output + cache_creation + cache_read tokens`（无状态过滤） | `SUB2API_PGHOST/SUB2API_PGPORT/SUB2API_PGDATABASE/SUB2API_PGUSER/SUB2API_PGPASSWORD` |

- 统计均按 **Asia/Shanghai 时区**聚合（年图按自然日，日图按小时）
- 不含计费额度（quota）；`new-api` 只统计成功请求（`type=2`），`sub2api` 无状态过滤，包含所有上报 token 的调用（含部分失败）
- 色阶: 5 档，配色由 `theme` 决定（`github` 绿 / `sakura` 粉），按 **分位数分桶**（rank-based；相同 token 值保持同档）
- 多源并存时部署多实例，各实例 `.env` 指定 `SOURCE`（+ 各自独立连接变量）；`SUB2API_PGPORT` 可选（默认 5432），host/database/user/password 必填

## 部署

```bash
# 1. 复制模板并填写真实数据源连接凭据
cp .env.template .env

# 2. 开发/常规部署（bind mount 源码与主题，改代码后 restart）
docker compose up -d --build

# 3. 生产部署（镜像内置 app/ 与 themes/，只读根文件系统 + 非 root）
docker compose -f docker-compose.prod.yml up -d --build
```

- 镜像 `token-heatmap:uv`（FastAPI + uvicorn，依赖预装在 `/opt/venv`）。`Dockerfile` 已 `COPY app/` 与 `themes/`，镜像可独立运行。
- `docker-compose.yml`（开发/常规部署）：挂载 `./app:/app`、`./themes:/themes`，`THEMES_DIR=/themes`，容器内命令 `uvicorn main:app --host 0.0.0.0 --port 8000`；容器端口映射到宿主回环 `127.0.0.1:${HOST_PORT:-3004}`，对外访问请走反向代理。
- `docker-compose.prod.yml`（生产）：不挂载宿主源码，`THEMES_DIR=/app/themes`，`read_only: true` + `/tmp` tmpfs，非 root，`no-new-privileges`。
- ⚠️ compose 默认项目名为 `token-heatmap`——**不要删**；多实例可用 `docker compose -p <项目名>`（或 `COMPOSE_PROJECT_NAME`）覆盖，并为每个实例设置不同的 `HOST_PORT`（与 `.env` 中的 `SOURCE`）。
- 外部网络由 `.env` 的 `NETWORK_NAME` 指定（默认 `proxy-network`）。部署前确认已存在：`docker network create proxy-network`（或按环境改 `.env` 后重建）。
- 两个 compose 的 healthcheck 均探测 `/token/readyz`：配置或数据源不可用会标记为 unhealthy。
- 数据库账号建议最小权限只读：`CONNECT` + schema `USAGE` + 目标表 `SELECT`；服务只执行 SELECT。
- TLS：本地/Unix socket 无需配置；生产建议 `PGSSLMODE=verify-full`（或 `SUB2API_PGSSLMODE`）并挂载 CA（`PGSSLROOTCERT`），未知取值启动即报错。

### 环境变量

| 变量                                                                                                 | 默认             | 说明                                                                                              |
| ---------------------------------------------------------------------------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------- |
| `SOURCE`                                                                                             | `new-api`        | 数据源：`new-api` / `sub2api`；未识别值启动失败                                                   |
| `PGHOST` / `PGPORT` / `PGDATABASE` / `PGUSER` / `PGPASSWORD`                                         | —                | new-api 连接（`PGPORT` 默认 5432，其余必填）                                                      |
| `SUB2API_PGHOST` / `SUB2API_PGPORT` / `SUB2API_PGDATABASE` / `SUB2API_PGUSER` / `SUB2API_PGPASSWORD` | —                | sub2api 连接（`SUB2API_PGPORT` 可选，默认 5432）                                                  |
| `DB_STATEMENT_TIMEOUT_MS`                                                                            | `5000`           | 单条查询最大执行毫秒数，超时由 PostgreSQL 取消                                                    |
| `PGSSLMODE` / `PGSSLROOTCERT`                                                                        | 未设置           | new-api 可选 TLS（生产建议 `verify-full` + CA）                                                   |
| `SUB2API_PGSSLMODE` / `SUB2API_PGSSLROOTCERT`                                                        | 未设置           | sub2api 可选 TLS                                                                                  |
| `CACHE_TTL_SECONDS`                                                                                  | `60`             | 服务端 SVG 缓存 TTL（正数）                                                                       |
| `CACHE_MAX_ENTRIES`                                                                                  | `2000`           | 缓存最大条目数（正整数）                                                                          |
| `MAX_RENDER_CONCURRENCY`                                                                             | `4`              | 每进程同时渲染/查询上限（保护数据库）                                                             |
| `NETWORK_NAME`                                                                                       | `proxy-network`  | compose 外部网络名                                                                                |
| `HOST_PORT`                                                                                          | `3004`           | compose 宿主监听端口                                                                              |
| `THEMES_DIR`                                                                                         | 项目根 `themes/` | 主题目录；本地若在 `.env` 中设置会覆盖默认值，容器内由 compose 指定（`/themes` 或 `/app/themes`） |

## 布局

- 滚动年(`auto`): ~53 周 × 7 行，**周日开头**，未来日期不画格子；左侧只标注 周一/周三/周五；月份标签按列首月变化标注；底部一行统计（今日/本月/今年，标签粗体）
- 年图(`year`): 自然年 53 周列 × 7 行（周日开头），未来日期浅灰占位
- 月图(`month`): 按周排列的月历（横向 7 列 = 周日~周六，纵向按周堆叠）
- 日图(`day`): 24 小时柱状图，Y 轴以 M（百万）为单位动态取整齐刻度，X 轴 0/6/12/18/24
- 底部统计行: 今日/本月/今年（截至当天），zh 用 万/亿 中文单位，en 用 K/M/B；图例整组右对齐
- 每个格子 `<title>` 内带精确日期与 token 数（浏览器直接打开 SVG 可见 hover）

## 目录结构

```
token-heatmap/
├── main.py              # 本地启动器（Click：--reload / --port）
├── app/
│   ├── main.py          # FastAPI 路由和装配（参数校验、TTL 缓存、配置页、lifespan）
│   ├── cache.py         # 线程安全 TTL 缓存 + 同 key single-flight / 并发上限
│   ├── config.py        # 时区、布局常量、环境变量解析与校验
│   ├── heatmap.py       # 分档与年/滚动年/月/日 SVG 渲染编排
│   ├── heatmap_stats.py # 统计单位格式化 + 今日/本月/今年累计
│   ├── heatmap_svg.py   # SVG 文档组装、图例与星期标签
│   ├── theme_loader.py  # 主题加载器：themes/*.json + watchdog 热更新 + 版本号 + 内置 github 兜底
│   └── sources/         # 多数据源（Source 抽象 + 各网关实现）
│       ├── base.py      # Source ABC + 时区日期区间 helper
│       ├── pg.py        # 共享 PostgreSQL connect_args（statement_timeout / TLS）
│       ├── newapi.py    # new-api logs 表实现
│       └── sub2api_db.py# sub2api usage_logs 表实现
├── themes/              # 主题 JSON 文件（文件名 = 主题族名，watchdog 热更新）
│   ├── github.json      # GitHub 绿
│   └── sakura.json      # 樱花粉
├── tests/               # 不访问真实数据库的 pytest 回归测试
│   ├── test_routes.py      # 路由、参数校验、缓存与 ETag
│   ├── test_cache.py       # TTL 缓存、single-flight 并发
│   ├── test_heatmap.py     # 四种粒度 SVG 渲染
│   ├── test_theme_loader.py# 主题校验、版本号、watchdog 生命周期
│   ├── test_config.py      # 配置解析与数据源选择
│   ├── test_repository.py  # 数据源查询窗口（mock Session）
│   ├── test_pg_engine.py   # 引擎 connect_args（超时/TLS）
│   └── test_launcher.py    # 本地启动器 CLI
├── pyproject.toml       # uv 项目与依赖定义（dev: pytest/httpx2/ruff；Ruff 配置）
├── uv.lock              # 锁定依赖
├── .env.template        # 连接凭据模板（复制为 .env 后填写）
├── .github/workflows/ci.yml  # CI：Ruff + pytest + 锁文件 + Compose 校验
├── LICENSE              # GPL-3.0
├── Dockerfile           # 构建独立镜像（COPY app/ 与 themes/，非 root）
├── docker-compose.yml   # 开发/常规部署（bind mount 源码与主题）
└── docker-compose.prod.yml  # 生产部署（只读根文件系统，不挂载源码）
```

## 开发与测试（uv）

```bash
# 首次或依赖变更后创建/同步 .venv（开发依赖包含 pytest、httpx2、ruff）
uv sync
uv run pytest -q
uv run ruff check .

# 修改依赖后更新锁文件
uv lock
```

本地启动（无需 Docker；会加载项目根 `.env`，默认仅监听 `127.0.0.1:8000`）：

```bash
uv run main.py                  # 本地启动，默认 127.0.0.1:8000
uv run main.py --reload         # 代码变更自动重载
uv run main.py --port 9000      # 自定义端口（1-65535）
```

- 修改 `app/` 代码后：本地用 `--reload`；容器需 `docker compose restart token-heatmap`。`./app:/app` 保持挂载，依赖在镜像 `/opt/venv`，restart 不会重新联网安装依赖。
- CI（`.github/workflows/ci.yml`）执行 `uv sync --locked`、`ruff check`、`pytest`、`uv lock --check` 与 Compose 配置校验。

## License

[GPL-3.0](LICENSE) © pyre-z
