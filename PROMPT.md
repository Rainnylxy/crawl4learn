# PROMPT.md

## Goal

构建一个 Chrome 浏览器插件 + 本地 Python (FastAPI) 后端服务，用户浏览网页或学术 PDF 时，一键通过 Crawl4AI 抓取内容、LLM 提取结构化知识，并将原文和提取结果自动存入 Obsidian Vault。

## Done when

1. **Python 后端可启动** — `python server.py` 在 `http://127.0.0.1:8888` 启动，提供 `/extract` 和 `/save` 两个 API。
2. **`/extract` API 可用** — 接收 `{url, instruction}`，调用 Crawl4AI 抓取网页/PDF 并用 `LLMExtractionStrategy` 提取结构化信息，返回 `{title, markdown, extracted}`。
3. **`/save` API 可用** — 接收提取结果，格式化为 Obsidian 笔记（YAML frontmatter + 要点 + 原文），写入配置的 Obsidian Vault 路径。
4. **Chrome 插件可加载** — 在 `chrome://extensions` 开发者模式下可加载，弹出窗口有"提取并保存"按钮。
5. **端到端走通** — 打开一个网页 → 点击插件按钮 → 几秒后 Obsidian Vault 中出现新 .md 笔记，包含提取的知识和原文。
6. **PDF 支持** — 对 `.pdf` URL 同样能处理。

## Never touch

- 不修改 `crawl4ai/` 目录下的任何 Crawl4AI 源码
- 不修改 `deploy/`、`docs/`、`tests/`、`.github/`

## Stop if

- 超过 12 个新文件被创建
- 任何已有文件的测试开始失败
- Crawl4AI 版本不兼容导致 `AsyncWebCrawler.arun()` 签名变化
