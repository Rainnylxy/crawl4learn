const API = "http://127.0.0.1:8888";
const statusEl = document.getElementById("status");
const goBtn = document.getElementById("goBtn");

function setStatus(msg, cls) {
  statusEl.textContent = msg;
  statusEl.className = cls || "";
}

(async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  document.getElementById("url").textContent = tab.url;
})();

goBtn.addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const instruction =
    document.getElementById("instruction").value.trim() ||
    "提取核心内容、关键论点和重要数据，用中文输出";
  const autoSave = document.getElementById("autoSave").checked;

  goBtn.disabled = true;
  setStatus("正在提取...", "loading");

  try {
    const extractResp = await fetch(API + "/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: tab.url, instruction }),
    });

    if (!extractResp.ok) {
      const err = await extractResp.json();
      throw new Error(err.detail || `HTTP ${extractResp.status}`);
    }

    const data = await extractResp.json();
    setStatus("提取完成" + (autoSave ? "，正在存入 Obsidian..." : ""), "ok");

    if (autoSave) {
      const saveResp = await fetch(API + "/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: tab.url,
          title: data.title,
          markdown: data.markdown,
          extracted: data.extracted,
        }),
      });

      if (!saveResp.ok) {
        const err = await saveResp.json();
        throw new Error(err.detail || `保存失败 HTTP ${saveResp.status}`);
      }

      const saveResult = await saveResp.json();
      setStatus("已存入: " + saveResult.saved, "ok");
    } else {
      setStatus("提取完成（未自动保存）", "ok");
    }
  } catch (e) {
    setStatus("失败: " + e.message, "err");
  } finally {
    goBtn.disabled = false;
  }
});
