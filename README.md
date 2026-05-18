# LET Telegram Bot

抓取 LowEndTalk offers，新帖经 AI 结构化后推送到 Telegram 频道。

## 配置

首次运行不需要 `.env`，启动后可在管理前端填写模型和 Telegram 配置。

如果你希望用环境变量预置配置，可以复制 `.env.example` 为 `.env`，填写实际值：

```env
AI_API_KEY=你的中转或模型供应商 API Key
AI_BASE_URL=https://你的-openai-compatible-endpoint/v1
AI_MODEL=你的模型名

TG_BOT_TOKEN=你的 Telegram Bot Token
TG_CHAT_ID=你的频道或群 ID
ADMIN_HOST=127.0.0.1
ADMIN_PORT=2918
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-this-admin-password
```

AI 接口使用 OpenAI-compatible Chat Completions 协议。SiliconFlow、OpenRouter、One API、New API、LiteLLM、自建反代等中转，只要兼容 `/chat/completions`，都可以通过 `AI_BASE_URL` 和 `AI_MODEL` 切换。

硅基流动示例：

```env
AI_BASE_URL=https://api.siliconflow.cn/v1
AI_MODEL=Qwen/Qwen2.5-7B-Instruct
AI_MODEL_FALLBACKS=Qwen/Qwen3-8B
AI_TIMEOUT=45
AI_MAX_RETRIES=0
AI_CONTENT_LIMIT=8000
```

如果日志出现 `Model does not exist`，说明 `.env` 里的 `AI_MODEL` 不是当前账号可用模型名。先改 `.env`，再重启容器。
如果日志出现 `APITimeoutError`，先把 `AI_TIMEOUT` 控制在 30-60 秒，并保持 `AI_MAX_RETRIES=0`，避免 SDK 一条帖子重试多次拖慢全局扫描。

扫描间隔可以按风控情况调整：

```env
SCAN_INTERVAL_MIN=90
SCAN_INTERVAL_MAX=180
BLOCKED_SLEEP_SECONDS=1800
```

不建议低于 30 秒。程序会强制把普通扫描最小间隔钳制到 30 秒，被 403/429/503 限流时仍进入单独冷却。

## 运行

```bash
docker compose up -d --build
```

管理前端默认地址：

```text
http://localhost:2918
```

默认只绑定宿主机本机地址 `127.0.0.1`。如果需要远程访问，建议用 Nginx/Caddy 反代并启用 HTTPS 和 IP 白名单；不建议直接把后台暴露到公网。临时外网直连可设置 `ADMIN_HOST=0.0.0.0`。

首次运行若没有设置 `ADMIN_USERNAME` / `ADMIN_PASSWORD`，系统会自动生成管理员账号密码。查看命令：

```bash
docker logs let_bot_admin | grep LET_ADMIN
```

只有首次生成时会在日志里打印密码。后续重启只会提示账号，忘记密码请用下面的重置命令。
把输出里的账号和密码填到管理台后再保存配置。
管理台现在是独立登录页，登录成功后才会进入配置页面；账号不存在或密码错误会直接显示原因。

如果提示密码不正确，可以直接重置管理员密码：

```bash
docker exec let_bot_admin python reset_admin.py --username admin --password 'new-strong-password'
docker restart let_bot_admin
```

然后使用新密码登录。

前端支持设置大模型供应商、第三方中转 Base URL、API KEY、主模型、备用模型、扫描间隔和 Telegram 配置；也可以查看运行日志并一键清空日志。

配置会保存到 Docker 数据卷里的 `/app/data/config.json`。Bot 每次调用 AI、发送 TG 或进入下一轮扫描前都会重新读取最新配置，不缓存旧配置；修改模型、KEY、扫描间隔后不用重建镜像。配置文件使用原子替换写入，避免保存时被 bot 读到半截 JSON。

发布 Docker Hub：

```bash
docker login
docker compose build
docker compose push
```

默认使用 Docker named volume 保存 SQLite 数据，避免宿主机 `./data` 目录权限导致 `sqlite3.OperationalError: unable to open database file`。

如果你改回 bind mount，例如 `./data:/app/data`，需要先让容器用户可写：

```bash
mkdir -p data
chown -R 1000:1000 data
```

本地调试：

```bash
pip install -r requirements.txt
python main.py
```

## 推送格式

Telegram 默认使用 `MarkdownV2`，消息按以下四块排版：

- 商家、类型、优惠码、来源
- 精选方案
- 优缺点评价
- 支付方式
- 频道

只有“点击订阅”、`LowEndTalk 原贴` 和频道名保留可点击跳转。商品方案名、商家名、优惠码、`#64`、`/64` 这类编号都会按纯文本输出，避免触发 Telegram 自动跳转。优缺点评价固定为三行短句，每项尽量控制在 30 字内：

```text
优势：EPYC+NVMe，充值送25%
不足：仅德国，亚洲延迟高
适合：欧洲用户、德国节点需求者
```
