# Instagram Influencer Intelligence & Audit

Production stack:
- **n8n** — orchestration (webhook, Apify, analytics, AI, optional Whisper)
- **Apify** — Instagram profile + posts scraping
- **OpenRouter** — topic / hook / language classification
- **Render** — hosts the XLSX generator API (`xlsx-api/`)
- **Postman** — trigger webhook and download ZIP with both workbooks

## Project layout

```
insta-influencer-audit/
├── workflows/Instagram_Influencer_Intelligence_Audit.json   # Import this in n8n
├── xlsx-api/                    # Deploy to Render
│   ├── app.py
│   ├── requirements.txt
│   └── render.yaml
├── templates/                   # Excel templates (from assignment)
│   ├── influencer_template.xlsx
│   └── audit_template.xlsx
└── scripts/patch_workflow.py    # Regenerate workflow after edits
```

## Step 1 — Deploy XLSX API on Render

1. Push this repo to GitHub (folder `insta-influencer-audit` or whole repo).
2. On [render.com](https://render.com) → **New** → **Web Service** → connect repo.
3. Settings:
   - **Root Directory:** `xlsx-api` (if repo is monorepo) OR deploy only `xlsx-api` folder as its own repo.
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. After deploy, copy your URL, e.g. `https://insta-xlsx-api.onrender.com`
5. Test health: `GET https://insta-xlsx-api.onrender.com/health`
6. Test generate: `POST https://insta-xlsx-api.onrender.com/generate` with JSON body (see below).

**Important:** Copy `templates/` next to `xlsx-api` on Render. Easiest approach: put templates inside `xlsx-api/templates/` and update `app.py` paths, OR set repo root so `templates/` is at `../templates` from `xlsx-api` (current layout expects repo root deploy with both folders).

For Render with **root = repo root**:
- Start command: `cd xlsx-api && uvicorn app:app --host 0.0.0.0 --port $PORT`

## Step 2 — Point n8n at Render URL

1. Import `workflows/Instagram_Influencer_Intelligence_Audit.json` into n8n Cloud.
2. Open **Normalize Input** code node.
3. Find line `xlsx_api_url:` and replace placeholder:

```javascript
xlsx_api_url: 'https://YOUR-SERVICE-NAME.onrender.com/generate',
```

4. Re-save workflow and **Activate**.

Or re-run patch script after editing `XLSX_API_URL` in `scripts/patch_workflow.py`.

## Step 3 — Credentials in n8n

| Node | Credential |
|------|------------|
| Apify Profile Run / Post Run / Fetch | Header Auth: `Authorization: Bearer <APIFY_TOKEN>` |
| OpenAI Classify Posts | Header Auth: OpenRouter key |
| Whisper Transcribe (Optional) | OpenAI API credential |
| Generate XLSX Workbooks | None (public Render URL) |

## Step 4 — Postman: trigger audit & download files

**Request**

- Method: `POST`
- URL: your n8n production webhook, e.g.  
  `https://<instance>.app.n8n.cloud/webhook/instagram-influencer-audit`
- Headers: `Content-Type: application/json`
- Body:

```json
{
  "instagram_url": "https://www.instagram.com/chennaiipl/",
  "window_days": 30,
  "max_posts": 50,
  "enable_whisper": false
}
```

**Response (success)**

- HTTP 200
- **Content-Type:** `application/zip` (binary)
- File: `insta_audit_bundle.zip` containing:
  - `influencer_<username>_<timestamp>.xlsx`
  - `insta_audit_<username>_<timestamp>.xlsx`

In Postman: **Send and Download** → save ZIP → unzip both workbooks.

**Response (XLSX API down)**

- JSON with `"warning": "XLSX_API_UNAVAILABLE"` and full payload in `data` (no ZIP).

## What the updated workflow fixes

| Issue | Fix |
|-------|-----|
| `$env.XLSX_API_URL` denied on Cloud | Hardcoded `xlsx_api_url` in **Normalize Input** |
| Webhook returned JSON only | **Compression** + **Respond Success** returns ZIP binary |
| Whisper node orphaned | **IF Whisper Needed** → Download → Whisper → Map → Collect → Merge Transcripts |
| Last 10 avg views wrong | Chronological last 10 posts, not top-by-views |
| Transcripts sheet | **Reels only**; photos/carousels keep captions in **All Reels** |
| Private profiles | Continues with profile row + warning (no hard fail) |
| Language column blank | AI returns `primary_language` → **Regional/Primary Language** |

## Transcripts behavior

- **Reels:** Whisper when `enable_whisper: true` and `video_url` exists; else Instagram **caption**.
- **Photos / Carousels:** Caption in **All Reels** sheet only (not on Transcripts sheet).

## Local XLSX API (optional)

```bash
cd xlsx-api
pip install -r requirements.txt
cd ..
uvicorn xlsx-api.app:app --reload --port 8765
```

Then set `xlsx_api_url` to `http://127.0.0.1:8765/generate` (local n8n only).

## Regenerate workflow JSON

```bash
python scripts/patch_workflow.py
```

Copies to `workflows/Instagram_Influencer_Intelligence_Audit.json`.

## Assignment deliverables checklist

- [x] n8n workflow export
- [x] XLSX generator source (`xlsx-api/`)
- [x] Setup docs (this README)
- [ ] Run 3 sample profiles and save outputs
- [ ] Short limitations note (private accounts, missing video URLs, Apify rate limits)
