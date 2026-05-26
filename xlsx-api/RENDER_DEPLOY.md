# Fix Render 503 / "Application loading"

## Most common cause (503 even with `/generate` correct)

**Root Directory is wrong.** If Root Directory is empty, Render runs `uvicorn app:app` from the repo root, but `app.py` lives in `xlsx-api/` → deploy never becomes healthy → endless **503 Application loading**.

### Fix in Render Dashboard (do this first)

1. Open [Render Dashboard](https://dashboard.render.com) → service **instagram-audit**
2. **Settings** → **Root Directory** → set exactly: `xlsx-api`
3. **Settings** → **Start Command** → `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. **Settings** → **Build Command** → `pip install -r requirements.txt`
5. **Settings** → **Health Check Path** → `/health`
6. **Manual Deploy** → Deploy latest commit
7. Open **Logs** — you must see: `Uvicorn running on http://0.0.0.0:XXXX`

If logs show `ModuleNotFoundError: No module named 'app'` → Root Directory is still wrong.

## 1) Correct URL in n8n (most common)

In **Normalize Input**, `xlsx_api_url` must include **`/generate`**:

```
https://instagram-audit.onrender.com/generate
```

NOT:

```
https://instagram-audit.onrender.com
```

## 2) Render service settings

| Setting | Value |
|---------|--------|
| **Root Directory** | `xlsx-api` (if repo is `insta-influencer-audit`) OR leave blank if repo is only `xlsx-api` |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
| **Health Check Path** | `/health` |

## 3) Templates must be in the repo

Ensure these exist in Git and are deployed:

```
xlsx-api/templates/influencer_template.xlsx
xlsx-api/templates/audit_template.xlsx
```

If missing, `/health` returns `"influencer": false` and `/generate` returns 500.

## 4) Verify before n8n

Open in browser:

1. `https://instagram-audit.onrender.com/` → JSON with `"status": "ok"`
2. `https://instagram-audit.onrender.com/health` → `"influencer": true`, `"audit": true`

If you see **404** or HTML "Application loading" for minutes, the deploy failed — open **Render → Logs** and fix the Python error.

## 5) Free tier cold start

First request after idle can return **503** for 30–60s. In n8n **Generate XLSX Workbooks**:

- **Options → Retry On Fail**: ON  
- **Max Tries**: 3  
- **Wait Between Tries**: 15000 ms  

Or wake the service once: `GET https://instagram-audit.onrender.com/health` then run the workflow.

## 6) Redeploy checklist

1. Push latest `xlsx-api/` to GitHub  
2. Render → Manual Deploy  
3. Wait until status **Live**  
4. Test `/health`  
5. Re-run n8n workflow  
