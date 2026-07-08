[繁體中文](./README.md) | **English**

> ⚠️ **Legacy / Archived**: This project is no longer maintained and has been superseded by the next-generation private project yt-digest (Next.js + Firebase + local daemon architecture). The content below is kept for reference.

# YouTube AI Digest v2

> 📅 Project started: 2026-03

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-ready-2088FF?logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![n8n](https://img.shields.io/badge/n8n-ready-EA4B71?logo=n8n&logoColor=white)](https://n8n.io/)

Automatically fetches the latest videos from YouTube channels, uses AI (choose one of Claude / Gemini / OpenAI) to generate a one-sentence summary and bullet-point highlights, and writes them into a Google Sheet.

- Supports two deployment methods: **GitHub Actions scheduling** or **n8n workflow**
- One-click switching of AI provider — the same data can be used to compare results from different models
- Monthly cost of roughly $0–$1 USD

---

## 🚀 Quick start

### Option A — GitHub Actions (recommended, easiest)

1. Fork this repo
2. Go to Settings → Secrets and variables → Actions and set the required Secrets (see the table below)
3. Edit the `CHANNELS` list at the top of `scripts/digest.py` to fill in the channels you want to track
4. Actions → run manually once **or** wait for the scheduled trigger (default: once every morning)

### Option B — n8n

1. Import `n8n-workflow.json` into n8n
2. Set up the n8n Credentials described below
3. Edit `CHANNELS` and `AI_PROVIDER` in the "頻道設定 & AI 選擇" node
4. Activate the workflow

---

## 📺 Channel URL formats

Edit `scripts/digest.py` (or the "頻道設定" node in n8n):

```python
CHANNELS = [
    # 格式一：@handle（最常見）
    {"name": "頻道名稱", "url": "https://www.youtube.com/@channelHandle"},

    # 格式二：直接用 channel ID
    {"name": "頻道名稱", "url": "https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxx"},

    # 格式三：舊版 /c/ 路徑也支援
    {"name": "頻道名稱", "url": "https://www.youtube.com/c/channelName"},
]
```

---

## 🔄 Switching AI provider

### GitHub Actions

**On manual trigger**: Actions → Run workflow → select claude / gemini / openai from the dropdown

**Scheduled default**: edit line 18 of `.github/workflows/digest.yml`:

```yaml
AI_PROVIDER: ${{ github.event.inputs.ai_provider || 'claude' }}
#                                                   ↑ 改這裡
```

### n8n

Change the first line of the "頻道設定 & AI 選擇" node:

```javascript
const AI_PROVIDER = 'claude';  // 改成 gemini 或 openai
```

---

## 🔑 GitHub Secrets setup

| Name | Description | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API Key | When using Claude |
| `GEMINI_API_KEY` | Gemini API Key | When using Gemini |
| `OPENAI_API_KEY` | OpenAI API Key | When using OpenAI |
| `GOOGLE_CREDENTIALS` | Service Account JSON (base64) | ✅ Required |
| `SPREADSHEET_ID` | Google Sheet ID | ✅ Required |

**base64 conversion commands:**

```powershell
# Windows PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("your-key.json")) | clip

# macOS / Linux
base64 -i your-key.json | pbcopy
```

**Spreadsheet ID location:**

```
https://docs.google.com/spreadsheets/d/【這裡是 ID】/edit
```

---

## 🔑 n8n Credentials setup

After importing the workflow, you need to set up the following credentials:

| Credential name | Type | Fields |
|---|---|---|
| Claude API Key | Header Auth | Name: `x-api-key`, Value: your key |
| Gemini API Key | Query Auth | Name: `key`, Value: your key |
| OpenAI API Key | Header Auth | Name: `Authorization`, Value: `Bearer your key` |

---

## 📊 Google Sheet columns

| Column | Description |
|---|---|
| 頻道 | The channel name you set |
| 標題 | Video title |
| 發布日期 | YYYY-MM-DD |
| 影片連結 | Click to open the video directly |
| 一句摘要 | AI-generated (within 50 characters) |
| 重點條列 | AI-generated (3–5 bullets) |
| AI 來源 | CLAUDE / GEMINI / OPENAI |
| 分析時間 | Taiwan time |

---

## 💰 Cost comparison

Estimated for "5 channels, run once per day":

| AI | Model | Estimated monthly cost |
|---|---|---|
| Claude | Haiku | ~$0.5 – $1 USD |
| Gemini | 1.5 Flash | Almost $0 within the free tier |
| OpenAI | GPT-4o mini | ~$0.5 – $1 USD |

Gemini has a free tier of 15 RPM per month, which personal use will almost never exceed.

---

## 📂 Project structure

```
youtube-ai-digest/
├── scripts/
│   └── digest.py        ← 主程式（抓頻道、產摘要、寫 Sheet）
├── n8n-workflow.json    ← n8n workflow 匯入檔
├── requirements.txt     ← Python 套件
└── .github/workflows/
    └── digest.yml       ← GitHub Actions 排程
```

---

## 📄 License

Personal project, free to fork and modify.
