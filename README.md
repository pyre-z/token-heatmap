<h1 align="center">Token Heatmap</h1>

基于 new-api `logs` 表统计的 **Token 用量日历热力图**（SVG 直出，GitHub 贡献图风格）。支持 年 / 月 / 日 三种粒度、多主题（按族收编 day/night 两套配色）、中英双语、深浅色自动切换与背景控制。

## 在线地址

部署后通过反代或端口映射访问（路径均相对于站点根）：

- 配置页: `GET /token/`（可视化调整参数并生成嵌入代码）
- 热力图: `GET /token/@?grain=year&theme=github&lang=zh&darkmode=auto&bg=0&scale=1`

```html
<img src="https://your-host/token/@?grain=year" alt="Token 用量热力图">
```

## 参数

| 参数 | 取值 | 默认 | 说明 |
|---|---|---|---|
| `grain` | `year` / `month` / `day` | `year` | 时间粒度 |
| `year` / `month` / `day` | 数字 | 当前日期 | 目标日期；缺省自动取当天。`grain=month` 需 `year+month`，`grain=day` 需完整日期 |
| `theme` | 主题族名（当前 `github`） | `github` | 主题族，见下方「主题配置」 |
| `lang` | `zh` / `en` | `zh` | 界面语言（月份/星期/图例） |
| `darkmode` | `0` / `1` / `auto` | `auto` | `0`=白天配色、`1`=夜晚配色、`auto`=跟随访问者系统深浅自动切换（内嵌 CSS `prefers-color-scheme`） |
| `bg` | `0` / `1` | `0` | `0`=透明背景、`1`=使用主题 background 色（随 darkmode 取 day/night 对应背景） |
| `scale` | `0.1`–`10` | `1` | 缩放倍数（渲染尺寸乘 scale，viewBox 不变，矢量等比缩放） |

示例：

```
/token/@?grain=month&year=2026&month=9
/token/@?grain=day&theme=github&lang=en&darkmode=1&bg=1
/token/@?grain=year&scale=2
```

## 主题配置

主题在 `app/heatmap.py` 的 `THEMES` 中**按「族」收编**：每个主题族包含 `day`（白天）与 `night`（夜晚）两套配色，由 `darkmode` 参数选择；`darkmode=auto` 时通过内嵌 CSS 变量（`:root` 默认 day，`@media (prefers-color-scheme: dark)` 覆盖为 night）让 SVG 跟随访问者系统深浅自动切换。

```python
THEMES = {
    "github": {
        "day": {
            "colors":     ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],  # 0空~4最高 五档色
            "text":       "#767676",   # 月份/星期/刻度等次要文字
            "title":      "#24292f",   # 标题文字
            "legend":     "#767676",   # 图例「少/更多」文字
            "background": "#ffffff",   # bg=1 时使用
        },
        "night": {
            "colors":     ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
            "text":       "#8b949e",
            "title":      "#c9d1d9",
            "legend":     "#7d8590",
            "background": "#0d1117",
        },
    },
}
```

新增主题时只需在 `THEMES` 加一个族并配齐 `day`/`night` 两套配色（`colors` 必须 5 档）；`theme` 参数即族名。旧版 `github-dark` 已随族收编移除，请改用 `theme=github&darkmode=1`。

## 端点

| 端点 | 说明 |
|---|---|
| `GET /token/@?...` | 年/月/日热力图 SVG（参数见上表），`image/svg+xml`，Cache-Control 600s，服务端另有 60s TTL 内存缓存（`CACHE_TTL_SECONDS` 可配） |
| `GET /token/` | 参数可视化配置页 |
| `GET /token/healthz` | 健康检查 `{"status":"ok"}` |

## 数据口径

- 数据源: 直连 new-api 的 PostgreSQL（只读；根目录 `.env` 提供连接凭据，已 gitignore）
- 统计: `logs` 表 `type=2`（成功请求）的 `prompt_tokens + completion_tokens`，按 **Asia/Shanghai 时区**聚合（年图按自然日，日图按小时）
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
- 服务端 SVG 缓存 TTL 由 `.env` 的 `CACHE_TTL_SECONDS` 控制（默认 60 秒）

## 布局

- 年图: 53 周列 × 7 行（周一~周日），未来日期浅灰占位
- 月图: 按周排列的月历（横向 7 列 = 周一~周日，纵向按周堆叠）
- 日图: 24 小时柱状图，Y 轴以 M（百万）为单位动态取整齐刻度，X 轴 0/6/12/18/24
- 每个格子 `<title>` 内带精确日期与 token 数（浏览器直接打开 SVG 可见 hover）

## 目录结构

```
token-heatmap/
├── app/
│   ├── main.py          # FastAPI 路由和装配（参数校验、TTL 缓存、配置页）
│   ├── cache.py         # 线程安全 TTL 缓存
│   ├── config.py        # 时区、布局常量
│   ├── repository.py    # 只读 PostgreSQL 查询（SQLModel）
│   └── heatmap.py       # 分桶、THEMES 主题配置与 SVG 渲染
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
- `./app:/app` 保持挂载；依赖在镜像 `/opt/venv`，restart 不会再联网安装依赖
