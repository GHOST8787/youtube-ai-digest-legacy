# YouTube AI Digest v2

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-ready-2088FF?logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![n8n](https://img.shields.io/badge/n8n-ready-EA4B71?logo=n8n&logoColor=white)](https://n8n.io/)

自動抓取 YouTube 頻道最新影片，用 AI（Claude / Gemini / OpenAI 三選一）產生一句話摘要和重點條列，並寫入 Google Sheet。

- 支援 **GitHub Actions 排程** 或 **n8n workflow** 兩種部署方式
- 一鍵切換 AI 供應商，同一份資料可比較不同模型的結果
- 每月成本約 $0〜$1 USD

---

## 🚀 快速開始

### 選項 A — GitHub Actions（推薦，最簡單）

1. Fork 此 repo
2. 到 Settings → Secrets and variables → Actions，設定必填 Secrets（見下方表）
3. 編輯 `scripts/digest.py` 開頭的 `CHANNELS` 清單，填入要追蹤的頻道
4. Actions → 手動執行一次 **或** 等排程觸發（預設每天早上一次）

### 選項 B — n8n

1. 在 n8n 匯入 `n8n-workflow.json`
2. 設定下方的 n8n Credentials
3. 編輯「頻道設定 & AI 選擇」節點中的 `CHANNELS` 和 `AI_PROVIDER`
4. 啟用 workflow

---

## 📺 頻道 URL 格式

修改 `scripts/digest.py`（或 n8n 的「頻道設定」節點）：

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

## 🔄 切換 AI 供應商

### GitHub Actions

**手動觸發時**：Actions → Run workflow → 下拉選 claude / gemini / openai

**排程預設**：修改 `.github/workflows/digest.yml` 第 18 行：

```yaml
AI_PROVIDER: ${{ github.event.inputs.ai_provider || 'claude' }}
#                                                   ↑ 改這裡
```

### n8n

在「頻道設定 & AI 選擇」節點第一行改：

```javascript
const AI_PROVIDER = 'claude';  // 改成 gemini 或 openai
```

---

## 🔑 GitHub Secrets 設定

| 名稱 | 說明 | 必填 |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API Key | 用 Claude 時 |
| `GEMINI_API_KEY` | Gemini API Key | 用 Gemini 時 |
| `OPENAI_API_KEY` | OpenAI API Key | 用 OpenAI 時 |
| `GOOGLE_CREDENTIALS` | Service Account JSON（base64） | ✅ 必填 |
| `SPREADSHEET_ID` | Google Sheet ID | ✅ 必填 |

**base64 轉換指令：**

```powershell
# Windows PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("your-key.json")) | clip

# macOS / Linux
base64 -i your-key.json | pbcopy
```

**Spreadsheet ID 位置：**

```
https://docs.google.com/spreadsheets/d/【這裡是 ID】/edit
```

---

## 🔑 n8n Credentials 設定

匯入 workflow 後，需設定下列 credentials：

| Credential 名稱 | 類型 | 欄位 |
|---|---|---|
| Claude API Key | Header Auth | Name: `x-api-key`, Value: 你的 key |
| Gemini API Key | Query Auth | Name: `key`, Value: 你的 key |
| OpenAI API Key | Header Auth | Name: `Authorization`, Value: `Bearer 你的 key` |

---

## 📊 Google Sheet 欄位

| 欄位 | 說明 |
|---|---|
| 頻道 | 你設定的頻道名稱 |
| 標題 | 影片標題 |
| 發布日期 | YYYY-MM-DD |
| 影片連結 | 點擊直接開影片 |
| 一句摘要 | AI 生成（50 字內） |
| 重點條列 | AI 生成（3〜5 個 bullet） |
| AI 來源 | CLAUDE / GEMINI / OPENAI |
| 分析時間 | 台灣時間 |

---

## 💰 費用比較

以「5 頻道、每天跑一次」估算：

| AI | 模型 | 估計月費 |
|---|---|---|
| Claude | Haiku | ~$0.5 〜 $1 USD |
| Gemini | 1.5 Flash | 免費額度內幾乎 $0 |
| OpenAI | GPT-4o mini | ~$0.5 〜 $1 USD |

Gemini 每月有 15 RPM 免費額度，個人使用幾乎不會超過。

---

## 📂 專案結構

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

## 📄 授權

個人專案，可自由 fork 修改使用。
