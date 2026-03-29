"""
YouTube AI Digest v2
--------------------
支援 Claude / Gemini / OpenAI 三個 AI，可透過環境變數切換。
頻道用 YouTube URL 格式輸入，自動解析 Channel ID。
使用 YouTube Data API v3 抓取影片���
Gemini 模式：用 yt-dlp 下載音訊 → 上傳 Gemini File API → 只分析音訊（省 88% token）。

環境變數（GitHub Secrets）:
  AI_PROVIDER         - 選擇 AI：claude / gemini / openai（預設 claude）
  ANTHROPIC_API_KEY   - Claude API key（AI_PROVIDER=claude 時需要）
  GEMINI_API_KEY      - Gemini API key（AI_PROVIDER=gemini 時需要）
  OPENAI_API_KEY      - OpenAI API key（AI_PROVIDER=openai 時需要）
  YOUTUBE_API_KEY     - YouTube Data API v3 key（必填）
  GOOGLE_CREDENTIALS  - Google Service Account JSON（base64 編碼）
  SPREADSHEET_ID      - Google Sheet 的 ID
"""

import os
import sys
import re
import json
import base64
import logging
import time
import tempfile
import subprocess
from datetime import datetime, timezone, timedelta

import requests
import gspread
from google.oauth2.service_account import Credentials

# ── 設定 ──────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── 頻道清單（用 YouTube URL 格式）──────────────────────────────────────────
CHANNELS = [
    {"name": "向陽說", "url": "https://www.youtube.com/channel/UCsvKtMVSJfdFBc1BtsayIJw"},
]

FETCH_DAYS            = int(os.environ.get("FETCH_DAYS", "1"))
MAX_VIDEOS_PER_CHANNEL = 3
SHEET_NAME            = "AI摘要"
HEADERS = ["頻道", "標題", "發布日期", "影片連結", "一句摘要", "重點條列", "AI來源", "分析時間"]

# ── Channel ID 解析 ────────────────────────────────────────────────────────────

def resolve_channel_id(url: str) -> str | None:
    """從各種 YouTube URL 格式解析出 Channel ID (UCxxxxxxxx)。"""
    m = re.search(r"/channel/(UC[\w-]{22})", url)
    if m:
        return m.group(1)

    yt_key = os.environ.get("YOUTUBE_API_KEY", "")
    if yt_key:
        handle_match = re.search(r"/@([^/?]+)", url)
        if handle_match:
            handle = handle_match.group(1)
            api_url = (
                f"https://www.googleapis.com/youtube/v3/channels"
                f"?part=id&forHandle={handle}&key={yt_key}"
            )
            try:
                resp = requests.get(api_url, timeout=15)
                resp.raise_for_status()
                items = resp.json().get("items", [])
                if items:
                    return items[0]["id"]
            except requests.RequestException as e:
                log.warning(f"YouTube API 解析 handle 失敗: {e}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        m = re.search(r'"channelId":"(UC[\w-]{22})"', resp.text)
        if m:
            return m.group(1)
        m = re.search(r'"externalId":"(UC[\w-]{22})"', resp.text)
        if m:
            return m.group(1)
    except requests.RequestException as e:
        log.warning(f"無法解析 URL {url}: {e}")
    return None

# ── YouTube Data API v3 抓取影片 ──────────────────────────────────────────────

def fetch_channel_videos(channel_id: str, days: int = 1) -> list[dict]:
    """用 YouTube Data API v3 的 search endpoint 抓取頻道最新影片。"""
    yt_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not yt_key:
        log.error("YOUTUBE_API_KEY 未設定")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    published_after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    search_url = (
        f"https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&channelId={channel_id}&type=video"
        f"&order=date&maxResults={MAX_VIDEOS_PER_CHANNEL}"
        f"&publishedAfter={published_after}&key={yt_key}"
    )
    try:
        resp = requests.get(search_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        log.warning(f"YouTube API 搜尋失敗 {channel_id}: {e}")
        return []

    items = data.get("items", [])
    if not items:
        return []

    video_ids = [item["id"]["videoId"] for item in items]
    videos_url = (
        f"https://www.googleapis.com/youtube/v3/videos"
        f"?part=snippet&id={','.join(video_ids)}&key={yt_key}"
    )
    try:
        resp = requests.get(videos_url, timeout=15)
        resp.raise_for_status()
        details = {v["id"]: v["snippet"] for v in resp.json().get("items", [])}
    except requests.RequestException as e:
        log.warning(f"YouTube API 影片詳情失敗: {e}")
        details = {}

    videos = []
    for item in items:
        vid = item["id"]["videoId"]
        snippet = details.get(vid, item.get("snippet", {}))
        published_str = snippet.get("publishedAt", "")
        try:
            published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except ValueError:
            published = datetime.now(timezone.utc)

        desc = snippet.get("description", "")
        videos.append({
            "video_id":    vid,
            "title":       snippet.get("title", ""),
            "url":         f"https://www.youtube.com/watch?v={vid}",
            "published":   published.strftime("%Y-%m-%d"),
            "description": desc,
        })

    return videos

# ── 音訊下載與上傳 ────────────────────────────────────────────────────────────

def download_audio(video_url: str) -> str | None:
    """用 yt-dlp 下載 YouTube 影片的純音訊（m4a），回傳檔案路徑。"""
    tmp_dir = tempfile.mkdtemp()
    output_path = os.path.join(tmp_dir, "audio.m4a")
    cmd = [
        "yt-dlp",
        "-x",                          # 只抽音訊
        "--audio-format", "m4a",       # 輸出 m4a
        "--audio-quality", "5",        # 中等品質（省空間）
        "-o", output_path,
        "--no-playlist",
        "--quiet",
        video_url,
    ]
    try:
        subprocess.run(cmd, check=True, timeout=300)
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        log.info(f"   音訊下載完成：{size_mb:.1f} MB")
        return output_path
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        log.warning(f"   音訊下載失敗: {e}")
        return None

def upload_to_gemini(file_path: str, api_key: str) -> str | None:
    """上傳音訊到 Gemini File API，回傳 file URI。"""
    file_size = os.path.getsize(file_path)
    mime_type = "audio/mp4"

    # Step 1: 開始 resumable upload
    init_url = (
        f"https://generativelanguage.googleapis.com/upload/v1beta/files"
        f"?key={api_key}"
    )
    init_headers = {
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(file_size),
        "X-Goog-Upload-Header-Content-Type": mime_type,
        "Content-Type": "application/json",
    }
    init_body = {"file": {"display_name": os.path.basename(file_path)}}

    resp = requests.post(init_url, headers=init_headers, json=init_body, timeout=30)
    resp.raise_for_status()
    upload_url = resp.headers.get("X-Goog-Upload-URL")
    if not upload_url:
        log.error("   無法取得上傳 URL")
        return None

    # Step 2: 上傳檔案
    with open(file_path, "rb") as f:
        upload_headers = {
            "X-Goog-Upload-Command": "upload, finalize",
            "X-Goog-Upload-Offset": "0",
            "Content-Length": str(file_size),
        }
        resp = requests.post(upload_url, headers=upload_headers, data=f, timeout=300)
        resp.raise_for_status()

    file_info = resp.json().get("file", {})
    file_uri = file_info.get("uri", "")
    file_name = file_info.get("name", "")
    log.info(f"   上傳完成：{file_name}")

    # Step 3: 等待處理完成
    check_url = (
        f"https://generativelanguage.googleapis.com/v1beta/{file_name}"
        f"?key={api_key}"
    )
    for _ in range(60):  # 最多等 5 分鐘
        resp = requests.get(check_url, timeout=15)
        resp.raise_for_status()
        state = resp.json().get("state", "")
        if state == "ACTIVE":
            log.info(f"   檔案已就緒")
            return file_uri
        elif state == "FAILED":
            log.error(f"   檔案處理失敗")
            return None
        time.sleep(5)

    log.error("   檔案處理超時")
    return None

def delete_gemini_file(file_uri: str, api_key: str):
    """刪除 Gemini File API 上的檔案。"""
    # file_uri 格式: https://generativelanguage.googleapis.com/v1beta/files/xxxxx
    # 需要取出 files/xxxxx 的部分
    m = re.search(r"(files/[^?]+)", file_uri)
    if not m:
        return
    file_name = m.group(1)
    delete_url = (
        f"https://generativelanguage.googleapis.com/v1beta/{file_name}"
        f"?key={api_key}"
    )
    try:
        requests.delete(delete_url, timeout=15)
        log.info(f"   已清理遠端檔案")
    except Exception:
        pass

# ── AI 分析（Claude / Gemini / OpenAI 三選一）─────────────────────────────────

PROMPT_TEMPLATE = """\
你是一位專業的財經/知識型內容分析師。請根據這支 YouTube 影片的完整音訊內容進行系統化深度分析。

頻道：{channel}
標題：{title}
影片描述：{desc}

請用繁體中文回覆，格式嚴格如下（不要加其他文字）：

一句摘要：（用一句話說明這支影片的核心內容，不超過 50 字）

重點條列：
• （重點一：影片討論的核心議題，引用具體數據或指標）
• （重點二：提及的關鍵人物、機構報告或市場事件）
• （重點三：影片中的具體分析邏輯或論證過程）
• （重點四：給出的投資建議、操作策略或行動指南）
• （重點五：總結觀點或風險提醒）

注意：請基於影片音訊的實際內容分析，引用具體數據和觀點，不要泛泛而談。每個重點都要有實質內容。"""

PROMPT_TEXT_ONLY = """\
你是一位專業的內容摘要助手。請根據以下 YouTube 影片資訊進行分析。

頻道：{channel}
標題：{title}
影片描述：{desc}

請用繁體中文回覆，格式嚴格如下（不要加其他文字）：

一句摘要：（用一句話說明這支影片的核心內容，不超過 50 字）

重點條列：
• （重點一）
• （重點二）
• （重點三）
• （重點四）
• （重點五）

注意：僅基於標題與描述分析。"""

def _parse_ai_output(raw: str) -> dict:
    """解析 AI 回傳的固定格式，支援各種 AI 的格式差異"""
    clean = raw.replace("**", "")
    summary, bullets = "", ""
    if "一句摘要" in clean:
        lines       = clean.split("\n")
        in_bullets  = False
        bullet_lines = []
        for line in lines:
            t = line.strip()
            if "一句摘要" in t:
                summary = re.sub(r"^.*?一句摘要[：:]?\s*", "", t).strip()
            elif "重點條列" in t:
                in_bullets = True
            elif in_bullets and (t.startswith("•") or t.startswith("-") or t.startswith("*") or re.match(r"^\d+[.、]", t)):
                cleaned = re.sub(r"^[-*•]\s*", "", t)
                cleaned = re.sub(r"^\d+[.、]\s*", "", cleaned)
                bullet_lines.append(f"• {cleaned}")
        bullets = "\n".join(bullet_lines)
    else:
        summary = clean[:100]
    return {"summary": summary, "bullets": bullets}

def analyze_claude(title: str, desc: str, channel: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": PROMPT_TEXT_ONLY.format(
            channel=channel, title=title, desc=desc or "（無描述）"
        )}],
    )
    return _parse_ai_output(msg.content[0].text.strip())

def analyze_gemini(title: str, desc: str, channel: str, video_url: str = "") -> dict:
    """Gemini 分析：下載音訊 → 上傳 File API → 分析 → 清理"""
    api_key = os.environ["GEMINI_API_KEY"]
    generate_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )

    file_uri = None
    audio_path = None

    # 嘗試下載音訊並上傳
    if video_url:
        audio_path = download_audio(video_url)
        if audio_path:
            file_uri = upload_to_gemini(audio_path, api_key)
            # 刪除本地暫存
            try:
                os.remove(audio_path)
                os.rmdir(os.path.dirname(audio_path))
            except OSError:
                pass

    # 組裝 payload
    if file_uri:
        prompt_text = PROMPT_TEMPLATE.format(
            channel=channel, title=title, desc=desc or "（無描述）"
        )
        parts = [
            {"fileData": {"fileUri": file_uri, "mimeType": "audio/mp4"}},
            {"text": prompt_text},
        ]
    else:
        log.warning("   無法取得音訊，改用純文字分析")
        parts = [{"text": PROMPT_TEXT_ONLY.format(
            channel=channel, title=title, desc=desc or "（無描述）"
        )}]

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"maxOutputTokens": 4096},
    }

    try:
        for attempt in range(3):
            resp = requests.post(generate_url, json=payload, timeout=600)
            if resp.status_code == 429:
                wait = 15 * (attempt + 1)
                log.warning(f"   Gemini 速率限制，等待 {wait} 秒後重試...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return _parse_ai_output(raw.strip())
        resp.raise_for_status()
        return {"summary": "重試失敗", "bullets": ""}
    finally:
        # 清理 Gemini 遠端檔案
        if file_uri:
            delete_gemini_file(file_uri, api_key)

def analyze_openai(title: str, desc: str, channel: str) -> dict:
    import openai
    client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=2048,
        messages=[{"role": "user", "content": PROMPT_TEXT_ONLY.format(
            channel=channel, title=title, desc=desc or "（無描述）"
        )}],
    )
    return _parse_ai_output(resp.choices[0].message.content.strip())

ANALYZERS = {
    "claude": analyze_claude,
    "gemini": analyze_gemini,
    "openai": analyze_openai,
}

def analyze(title: str, desc: str, channel: str, video_url: str = "") -> tuple[dict, str]:
    """根據 AI_PROVIDER 環境變數選擇 AI，回傳 (結果, provider名稱)"""
    provider = os.environ.get("AI_PROVIDER", "claude").lower()
    if provider not in ANALYZERS:
        log.warning(f"未知的 AI_PROVIDER '{provider}'，改用 claude")
        provider = "claude"
    try:
        if provider == "gemini":
            result = ANALYZERS[provider](title, desc, channel, video_url=video_url)
        else:
            result = ANALYZERS[provider](title, desc, channel)
        log.info(f"   摘要: {result['summary'][:80]}")
        log.info(f"   條列: {len(result['bullets'])} 字")
        return result, provider
    except Exception as e:
        log.error(f"[{provider}] 分析失敗: {e}")
        return {"summary": f"分析失敗（{e}）", "bullets": ""}, provider

# ── Google Sheets ──────────────────────────────────────────────────────────────

def get_sheet():
    creds_b64 = os.environ.get("GOOGLE_CREDENTIALS", "")
    if not creds_b64:
        raise EnvironmentError("GOOGLE_CREDENTIALS 未設定")
    creds_json = json.loads(base64.b64decode(creds_b64).decode())
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    gc    = gspread.authorize(creds)
    sh    = gc.open_by_key(os.environ["SPREADSHEET_ID"])
    try:
        ws = sh.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=SHEET_NAME, rows=2000, cols=len(HEADERS))
        ws.append_row(HEADERS)
        log.info(f"建立新頁籤：{SHEET_NAME}")
    return ws

def get_existing_urls(ws) -> set[str]:
    try:
        col_idx  = HEADERS.index("影片連結") + 1
        existing = ws.col_values(col_idx)
        return set(existing[1:])
    except Exception:
        return set()

# ── 主程式 ─────────────────────────────────────────────────────────────────────

def main():
    provider = os.environ.get("AI_PROVIDER", "claude").lower()
    log.info(f"=== YouTube AI Digest v2 | AI: {provider.upper()} ===")
    log.info(f"抓取範圍：過去 {FETCH_DAYS} 天，每頻道最多 {MAX_VIDEOS_PER_CHANNEL} 支")

    ws           = get_sheet()
    existing     = get_existing_urls(ws)
    log.info(f"Sheet 已有 {len(existing)} 筆記錄")

    tw_tz  = timezone(timedelta(hours=8))
    now_str = datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M")
    new_rows = []

    for ch in CHANNELS:
        log.info(f"── {ch['name']}  {ch['url']}")

        channel_id = resolve_channel_id(ch["url"])
        if not channel_id:
            log.warning(f"   無法取得 Channel ID，跳過")
            continue
        log.info(f"   Channel ID: {channel_id}")

        videos = fetch_channel_videos(channel_id, days=FETCH_DAYS)
        log.info(f"   找到 {len(videos)} 支新影片")

        for v in videos:
            if v["url"] in existing:
                log.info(f"   跳過（已存在）：{v['title'][:40]}")
                continue

            log.info(f"   分析：{v['title'][:50]}")
            if new_rows:
                time.sleep(5)
            result, used_provider = analyze(
                v["title"], v["description"], ch["name"], video_url=v["url"]
            )

            new_rows.append([
                ch["name"],
                v["title"],
                v["published"],
                v["url"],
                result["summary"],
                result["bullets"],
                used_provider.upper(),
                now_str,
            ])
            existing.add(v["url"])

    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")
        log.info(f"✅ 寫入 {len(new_rows)} 筆")
    else:
        log.info("今日無新影片或全部已存在")

    log.info("=== 完成 ===")

if __name__ == "__main__":
    main()
