# YouTube AI Digest v2

支援 Claude / Gemini / OpenAI 三個 AI 可切換，頻道用 YouTube URL 格式輸入。

---

## 頻道 URL 格式說明

修改 `scripts/digest.py`（或 n8n 的「頻道設定」節點）：

```python
CHANNELS = [
    # 格式1：@handle（最常見）
    {"name": "頻道名稱", "url": "https://www.youtube.com/@channelHandle"},

    # 格式2：直接用 channel ID
    {"name": "頻道名稱", "url": "https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxx"},

    # 格式3：舊版 /c/ 路徑也支援
    {"name": "頻道名稱", "url": "https://www.youtube.com/c/channelName"},
]
```

---

## 切換 AI

### GitHub Actions

**手動觸發時**：Actions → Run workflow → 下拉選 claude / gemini / openai

**排程預設**：修改 `.github/workflows/digest.yml` 第 18 行：
```yaml
AI_PROVIDER: ${{ github.event.inputs.ai_provider || 'claude' }}
#                                                     ↑ 改這裡
```

### n8n

在「頻道設定 & AI選擇」節點第一行改：
```javascript
const AI_PROVIDER = 'claude';  // 改成 gemini 或 openai
```

---

## GitHub Secrets 設定

| 名稱 | 說明 | 必填 |
|------|------|------|
| `ANTHROPIC_API_KEY` | Claude API Key | 用 Claude 時 |
| `GEMINI_API_KEY` | Gemini API Key | 用 Gemini 時 |
| `OPENAI_API_KEY` | OpenAI API Key | 用 OpenAI 時 |
| `GOOGLE_CREDENTIALS` | Service Account JSON（base64）| ✅ 必填 |
| `SPREADSHEET_ID` | Google Sheet ID | ✅ 必填 |

**base64 轉換指令：**
```powershell
# Windows PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("your-key.json")) | clip

# Mac / Linux
base64 -i your-key.json | pbcopy
```

**Spreadsheet ID 位置：**
```
https://docs.google.com/spreadsheets/d/【這裡是ID】/edit
```

---

## n8n Credentials 設定

匯入 workflow 後，需設定以下 credentials：

| Credential 名稱 | 類型 | 欄位 |
|----------------|------|------|
| Claude API Key | Header Auth | Name: `x-api-key`, Value: 你的 key |
| Gemini API Key | Query Auth | Name: `key`, Value: 你的 key |
| OpenAI API Key | Header Auth | Name: `Authorization`, Value: `Bearer 你的key` |

---

## Google Sheet 欄位

| 欄位 | 說明 |
|------|------|
| 頻道 | 你設定的頻道名稱 |
| 標題 | 影片標題 |
| 發布日期 | YYYY-MM-DD |
| 影片連結 | 點擊直接開影片 |
| 一句摘要 | AI 生成（50字內）|
| 重點條列 | AI 生成（3-5個bullet）|
| AI來源 | CLAUDE / GEMINI / OPENAI |
| 分析時間 | 台灣時間 |

---

## 費用比較（每月，5頻道每天跑）

| AI | 模型 | 估計月費 |
|----|------|---------|
| Claude | Haiku | ~$0.5-1 USD |
| Gemini | 1.5 Flash | 免費額度內幾乎 $0 |
| OpenAI | GPT-4o mini | ~$0.5-1 USD |

Gemini 每月有 15 RPM 免費額度，個人使用幾乎不會超過。
