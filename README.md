# ArXiv Industry Paper Tracker

自动化从 ArXiv 获取推荐系统相关论文，过滤大厂论文，下载并可选调用 LLM 生成摘要。

## 快速开始
python3 -m venv .venv
source .venv/bin/activate

1. 安装依赖（建议使用虚拟环境）：
   ```bash
   pip install -r requirements.txt
   ```
2. 运行：  
   ```bash
PYTHONPATH=src python -m arxiv_paper_hunter.main \
  --last-n-days 1 \
  --max-results 300 \
  --use-llm-filter \
  --limit 20 \
  --categories cs.IR cs.LG cs.AI stat.ML cs.CL \
  --require-keyword-match \
  --skip-gatekeeper \
  --no-summary \
  --translate-abstracts \
  --telegram
# 如需跨领域：添加 --no-category-filter
# 说明：行尾不要在反斜线后写注释，以免 shell 把后续行当作命令。
   ```
   - 默认关键词：`recommendation system`, `recommender`, `CTR prediction`, `LLM for rec`
- 默认日期：包含最近 `--last-n-days` 天到今天（避免时区导致漏当天更新，1 表示昨天+今天）。
   - 日志等级可用 `--log-level DEBUG` 调试。

生成文件将保存在 `downloads/YYYY-MM-DD/`：
- PDF 重命名规则：`{Date}_{Company}_{FirstAuthor}_{Title_Slug}.pdf`
- 同目录下生成同名 `.md` 摘要文件，并追加到 `Summary.md`

## 功能概览
- **Harvester** (`harvester.py`): 使用 ArXiv API 按关键词+时间范围分页抓取，按提交时间倒序。
- **Gatekeeper** (`gatekeeper.py`): 三层过滤，大厂白名单正则（元数据）、可选邮箱文本、可选 LLM 兜底。
- **Archivist** (`archivist.py`): 按规则命名并下载 PDF，写入摘要 Markdown 与每日汇总。
- **Analyst** (`analyst.py`): 读取 PDF 前几页调用 DeepSeek/OpenAI 兼容接口生成 JSON 摘要；可提供 LLM 过滤投票；支持摘要 EN->ZH 翻译输出。
- **CLI** (`main.py`): 串联上述模块，先批量下载，再可选批量调用 LLM 生成摘要；支持关键词/日期/数量/LLM 过滤/跳过摘要等参数；支持将摘要翻译推送到 Telegram。

## 配置与环境变量
- `DEEPSEEK_API_KEY`（必需）：用于摘要/LLM 过滤/摘要翻译；如果只下载或设置 `--no-summary` 可为空。
- `LLM_BASE_URL`（可选）：OpenAI 兼容接口，默认 `https://api.deepseek.com/v1/chat/completions`。如果只给到域名 `https://api.deepseek.com` 会自动补上 `/v1/chat/completions`。请避免缺少 `/v1` 的 `.../chat/completions`。
- `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID`：开启 `--telegram` 推送时必需。`chat_id` 可为个人 ID 或群 ID（群需先邀请 bot）。

## PDF 图片处理说明
- 使用 `pymupdf`（fitz）渲染 PDF 首页图片，无需 `poppler`。
- 仍会尝试从 PDF 中抽取内嵌图片（如有），失败时不会中断。
- `LLM_BASE_URL`（可选）：OpenAI 兼容的 chat-completions 接口地址，默认 `https://api.deepseek.com/v1/chat/completions`。
- `LLM_MODEL`（可选）：模型名称，默认 `deepseek-chat`。
- 白名单、默认关键词、默认领域（cs.IR/cs.LG/cs.AI/stat.ML/cs.CL）位于 `src/arxiv_paper_hunter/config.py`，可按需修改。

## 注意事项
- 需要外网访问 ArXiv 与 LLM 接口。
- `pypdf` 用于 PDF 文本提取；如未安装会提示安装。
- 当前未实现自动解析论文邮箱，LLM 过滤为可选兜底。
