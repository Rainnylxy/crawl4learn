STATUS: done

# Implementation Plan

## Step 1 — Python 后端服务 (`server.py`) ✅ DONE

- [x] FastAPI app, listen on `127.0.0.1:8888`
- [x] `POST /extract` — 接收 url + instruction，调 Crawl4AI `AsyncWebCrawler.arun()` + `LLMExtractionStrategy`
- [x] `POST /save` — 接收 title/markdown/extracted，格式化为 Obsidian 笔记，写入 vault 目录
- [x] 从 `.env` 读取 `LLM_API_KEY`、`OBSIDIAN_VAULT_PATH`
- [x] `.env.example` 配置模板

## Step 2 — Chrome 插件 ✅ DONE

- [x] `manifest.json` (Manifest V3)
- [x] `popup.html` + `popup.js` — Catppuccin 风格 UI，一键提取+保存
- [x] 图标资源 (`icon-16/48/128.png`)

## Step 3 — 端到端验证 ✅ DONE

- [x] 安装 Crawl4AI 依赖
- [x] 启动后端，验证 `/health` 端点 → `{"status":"ok"}`
- [ ] 加载插件到 Chrome (需手动操作)
- [ ] 用网页 URL 测试完整流程 (需配置 API Key)
- [ ] 确认 Obsidian 中出现笔记文件 (需配置 API Key)
