import asyncio
import json
import logging
import os
import re
import tempfile
import traceback
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, LLMExtractionStrategy, LLMConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crawl4learn")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", str(Path.home() / "Obsidian" / "知识库")))
INBOX_FOLDER = os.getenv("OBSIDIAN_INBOX", "inbox")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek/deepseek-v4-pro")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
SERVER_PORT = int(os.getenv("SERVER_PORT", "8888"))

app = FastAPI(title="Crawl4Learn", version="0.1.0")

_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "文章/论文标题"},
        "authors": {"type": "string", "description": "作者"},
        "core_ideas": {"type": "string", "description": "核心观点，简洁概括"},
        "key_findings": {"type": "string", "description": "关键发现或数据"},
        "methods": {"type": "string", "description": "方法论或技术方案"},
        "contributions": {"type": "string", "description": "主要贡献或创新点"},
        "limitations": {"type": "string", "description": "局限性或未解决的问题"},
        "tags": {"type": "string", "description": "3-5个标签，逗号分隔"},
    },
}


class ExtractRequest(BaseModel):
    url: str
    instruction: str = "提取核心内容、关键论点和重要数据，用中文输出"


class SaveRequest(BaseModel):
    url: str
    title: str
    markdown: str
    extracted: dict


@app.post("/extract")
async def extract(req: ExtractRequest):
    url = req.url
    is_pdf = url.lower().endswith(".pdf") or "/pdf/" in url

    llm_cfg = LLMConfig(provider=LLM_PROVIDER, api_token=LLM_API_KEY, base_url=LLM_BASE_URL)
    strategy = LLMExtractionStrategy(
        llm_config=llm_cfg,
        instruction=req.instruction,
        schema=_EXTRACTION_SCHEMA,
        extraction_type="schema",
    )

    try:
        if is_pdf:
            result = await _crawl_pdf(url, strategy)
        else:
            async with AsyncWebCrawler(
                config=BrowserConfig(accept_downloads=True)
            ) as crawler:
                result = await crawler.arun(
                    url=url,
                    config=CrawlerRunConfig(extraction_strategy=strategy),
                )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"抓取失败: {str(e)}")

    if not result.success:
        raise HTTPException(status_code=500, detail=f"抓取失败: {result.error_message}")

    raw = result.extracted_content or "{}"
    extracted = _parse_extracted(raw) if result.extracted_content else {}
    # LLM sometimes returns a list; extract first item if so
    if isinstance(extracted, list) and len(extracted) > 0:
        extracted = extracted[0]
    if not isinstance(extracted, dict):
        extracted = {}

    return {
        "title": result.metadata.get("title", "") or extracted.get("title", ""),
        "markdown": result.markdown or "",
        "extracted": extracted,
    }


@app.post("/save")
async def save(req: SaveRequest):
    safe_name = re.sub(r'[\\/*?:"<>|]', "", req.title)[:80] or "untitled"
    inbox = VAULT_PATH / INBOX_FOLDER
    inbox.mkdir(parents=True, exist_ok=True)

    filepath = inbox / f"{safe_name}.md"
    # Avoid overwriting — append a counter if needed
    counter = 1
    while filepath.exists():
        filepath = inbox / f"{safe_name}-{counter}.md"
        counter += 1

    tags = req.extracted.get("tags", "")
    lines = [
        "---",
        f'tags: [{tags}]',
        f"source: {req.url}",
        "---",
        "",
        f"# {req.title}",
        "",
        "## 核心观点",
        req.extracted.get("core_ideas", ""),
        "",
        "## 关键发现",
        req.extracted.get("key_findings", ""),
        "",
        "## 方法",
        req.extracted.get("methods", ""),
        "",
        "## 贡献与创新",
        req.extracted.get("contributions", ""),
        "",
        "## 局限性",
        req.extracted.get("limitations", ""),
        "",
        "---",
        "",
        "## 原文",
        req.markdown,
    ]

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return {"saved": str(filepath.resolve())}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "provider": LLM_PROVIDER,
        "base_url": LLM_BASE_URL,
        "vault": str(VAULT_PATH.resolve()),
        "inbox": INBOX_FOLDER,
    }


def _parse_extracted(raw: str) -> dict:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {}


async def _crawl_pdf(url: str, llm_strategy: LLMExtractionStrategy):
    """Download a PDF directly, extract text, and run LLM extraction on it."""
    import httpx
    from pypdf import PdfReader

    logger.info(f"Downloading PDF: {url}")
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        pdf_bytes = resp.read()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        reader = PdfReader(tmp_path)
        text_parts = []
        for i, page in enumerate(reader.pages):
            t = page.extract_text()
            if t:
                text_parts.append(t)
        pdf_text = "\n\n".join(text_parts)
        if not pdf_text.strip():
            raise HTTPException(status_code=500, detail="PDF 文本提取为空")
    finally:
        os.unlink(tmp_path)

    logger.info(f"PDF text extracted: {len(pdf_text)} chars, sending to LLM...")

    # Write extracted text to a temp HTML file, then use file:// URL
    with tempfile.NamedTemporaryFile(
        suffix=".html", mode="w", encoding="utf-8", delete=False
    ) as tmp:
        tmp.write(f"<html><body><pre>{pdf_text}</pre></body></html>")
        tmp_path = tmp.name

    try:
        async with AsyncWebCrawler(config=BrowserConfig(accept_downloads=True)) as crawler:
            result = await crawler.arun(
                url=f"file://{tmp_path}",
                config=CrawlerRunConfig(extraction_strategy=llm_strategy),
            )
    finally:
        os.unlink(tmp_path)

    title = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return CrawlResultProxy(
        success=result.success,
        error_message=result.error_message,
        markdown=pdf_text,
        metadata={"title": title},
        extracted_content=result.extracted_content,
    )


class CrawlResultProxy:
    """Thin wrapper so _crawl_pdf can return something that looks like a CrawlResult."""
    def __init__(self, success, error_message, markdown, metadata, extracted_content):
        self.success = success
        self.error_message = error_message
        self.markdown = markdown
        self.metadata = metadata or {}
        self.extracted_content = extracted_content


if __name__ == "__main__":
    import uvicorn

    (VAULT_PATH / INBOX_FOLDER).mkdir(parents=True, exist_ok=True)
    uvicorn.run(app, host="127.0.0.1", port=SERVER_PORT)
