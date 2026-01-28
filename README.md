# Telegram 时政经济监控系统

监听 Telegram 频道的全球时政经济信息，AI 分析对 A股 的影响，推送到邮件/企业微信。

## 功能

- **实时监听**: 监听指定 Telegram 频道消息
- **AI 分析**: 批量分析消息对 A股 的影响（使用 Gemini）
- **智能推送**: 只推送有价值的消息（影响程度 >= 4）
- **每日早报**: 汇总昨日重要消息，生成早报

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入配置
```

### 2. 生成 Telegram Session

```bash
pip install -r requirements.txt
python main.py --generate-session
# 输入验证码，复制 StringSession 到 .env
```

### 3. 启动服务

```bash
# Docker 方式（推荐）
docker compose up -d

# 或直接运行
python main.py --monitor
```

## 命令

| 命令 | 说明 |
|------|------|
| `python main.py --monitor` | 启动实时监听 |
| `python main.py --monitor --interval 10` | 自定义分析间隔（分钟） |
| `python main.py --report` | 生成每日早报 |
| `python main.py --generate-session` | 生成 Telegram Session |
| `python main.py --debug` | 调试模式 |

## Docker 命令

```bash
# 启动监听
docker compose up -d

# 查看日志
docker compose logs -f

# 生成早报
docker compose run --rm daily-report

# 停止
docker compose down
```

## 配置说明

| 变量 | 说明 | 必须 |
|------|------|:----:|
| `TELEGRAM_API_ID` | API ID | ✅ |
| `TELEGRAM_API_HASH` | API Hash | ✅ |
| `TELEGRAM_SESSION` | StringSession | ✅ |
| `TELEGRAM_CHANNELS` | 频道 ID（逗号分隔） | ✅ |
| `GEMINI_API_KEY` | Gemini API Key | ✅ |
| `EMAIL_SENDER` | 发件邮箱 | 推荐 |
| `EMAIL_PASSWORD` | 邮箱授权码 | 推荐 |
| `EMAIL_RECEIVER` | 收件邮箱 | 推荐 |

## 文件结构

```
telegram_monitor_standalone/
├── main.py              # 主入口
├── config.py            # 配置管理
├── client.py            # Telegram 客户端
├── monitor.py           # 监听调度器
├── analyzer.py          # AI 分析器
├── storage.py           # 数据存储
├── daily_report.py      # 每日早报
├── message_filter.py    # 消息过滤
├── notification.py      # 通知服务
├── requirements.txt     # 依赖
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## 每日早报定时任务

```bash
# crontab -e
# 每天早上 8:00 发送早报
0 8 * * * cd /path/to/project && docker compose run --rm daily-report
```
