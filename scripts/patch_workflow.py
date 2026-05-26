"""Patch n8n workflow JSON with production fixes."""
import json
import uuid
from pathlib import Path

SRC = Path(r"C:\Users\kashy\Downloads\Instagram Influencer Intelligence & Audit (2).json")
OUT = Path(__file__).resolve().parent.parent / "workflows" / "Instagram_Influencer_Intelligence_Audit.json"

# >>> Replace after deploying to Render <<<
XLSX_API_URL = "https://YOUR-SERVICE-NAME.onrender.com/generate"

wf = json.loads(SRC.read_text(encoding="utf-8"))
nodes = {n["name"]: n for n in wf["nodes"]}


def nid():
    return str(uuid.uuid4())


# --- Normalize Input: add xlsx_api_url ---
norm = nodes["Normalize Input"]
norm["parameters"]["jsCode"] = norm["parameters"]["jsCode"].replace(
    "requested_at: new Date().toISOString(),",
    f"requested_at: new Date().toISOString(),\n    xlsx_api_url: '{XLSX_API_URL}',",
)

# --- Compute Analytics: chronological last 10 ---
nodes["Compute Analytics"]["parameters"]["jsCode"] = """// n8n Code node: Compute Analytics + filter window

const ctx = $('Normalize Input').first().json;
const parsed = $('Parse Merged Dataset').first().json;
const profile = parsed.profile;
let posts = [...parsed.posts];

const windowDays = ctx.window_days || 30;
const cutoff = new Date();
cutoff.setDate(cutoff.getDate() - windowDays);

posts = posts
  .filter((p) => {
    if (!p.posted_at) return true;
    return new Date(p.posted_at) >= cutoff;
  });

if (!posts.length) {
  return [{
    json: {
      ok: false,
      error: 'NO_POSTS_IN_WINDOW',
      message: `No posts in last ${windowDays} days.`,
      profile,
    },
  }];
}

function engagementRate(p) {
  const views = Number(p.views) || 0;
  if (views <= 0) return 0;
  return (Number(p.engagement) || 0) / views;
}

function statusLabel(p) {
  const views = Number(p.views) || 0;
  const rate = engagementRate(p);
  if (views >= 500000 && rate >= 0.05) return 'Viral';
  if (views >= 100000 && rate >= 0.03) return 'Strong';
  if (views === 0 && (p.likes || 0) > 50000) return 'Top Performer';
  if (rate < 0.01 && views > 0) return 'Needs Work';
  return 'Average';
}

function viewsDisplayRate(rate, views) {
  if (!views) return '0.0%';
  return `${(rate * 100).toFixed(2)}%`;
}

function captionBucket(caption) {
  const words = (caption || '').trim().split(/\\s+/).filter(Boolean).length;
  if (words < 30) return 'Short (<30w)';
  if (words < 80) return 'Medium (30-80w)';
  return 'Long (80w+)';
}

function weekdayName(dateStr) {
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  return days[new Date(dateStr).getDay()];
}

posts = posts.map((p) => {
  const rate = engagementRate(p);
  return {
    ...p,
    engagement_rate: rate,
    engagement_rate_pct: Math.round(rate * 10000) / 100,
    engagement_rate_display: viewsDisplayRate(rate, p.views),
    status: statusLabel(p),
    topic: p.topic || '',
    hook_type: p.hook_type || '',
    caption_length_bucket: captionBucket(p.caption),
    weekday: p.posted_at ? weekdayName(p.posted_at) : 'Unknown',
  };
});

const totalViews = posts.reduce((s, p) => s + (Number(p.views) || 0), 0);
const totalLikes = posts.reduce((s, p) => s + (Number(p.likes) || 0), 0);
const totalEngagement = posts.reduce((s, p) => s + (Number(p.engagement) || 0), 0);
const postsWithViews = posts.filter((p) => (p.views || 0) > 0);
const avgViews = postsWithViews.length ? totalViews / postsWithViews.length : 0;
const avgLikes = totalLikes / posts.length;
const avgEngagementRate = totalViews > 0 ? totalEngagement / totalViews : 0;

// Chronological last 10 posts (not top-by-views)
const chronoDesc = [...posts].sort((a, b) => {
  const da = a.posted_at ? new Date(a.posted_at).getTime() : 0;
  const db = b.posted_at ? new Date(b.posted_at).getTime() : 0;
  return db - da;
});
const last10Chrono = chronoDesc.slice(0, 10);
const avgViewsLast10 =
  last10Chrono.reduce((s, p) => s + (Number(p.views) || 0), 0) / Math.max(last10Chrono.length, 1);

const reelsOnly = posts.filter((p) => p.type === 'Reel');
const postingFrequencyPerWeek = (posts.length / windowDays) * 7;

const dayMap = {};
for (const p of posts) {
  const d = p.weekday || 'Unknown';
  if (!dayMap[d]) dayMap[d] = { count: 0, views: [], rates: [] };
  dayMap[d].count += 1;
  dayMap[d].views.push(Number(p.views) || 0);
  dayMap[d].rates.push(p.engagement_rate || 0);
}

const postingDayBreakdown = Object.entries(dayMap)
  .map(([day, v]) => {
    const avgV = v.views.reduce((a, b) => a + b, 0) / v.views.length;
    const avgR = v.rates.reduce((a, b) => a + b, 0) / v.rates.length;
    return {
      day,
      count: v.count,
      avg_views: avgV,
      avg_views_display: Math.round(avgV).toLocaleString('en-US'),
      avg_eng_rate_display: `${(avgR * 100).toFixed(2)}%`,
    };
  })
  .sort((a, b) => b.avg_views - a.avg_views);

const sortedByViews = [...posts].sort((a, b) => (b.views || 0) - (a.views || 0));
const topPosts = sortedByViews.slice(0, 5);
const bottomPosts = [...posts]
  .sort((a, b) => {
    const av = a.views || 0;
    const bv = b.views || 0;
    if (av === bv) return (a.engagement_rate || 0) - (b.engagement_rate || 0);
    return av - bv;
  })
  .slice(0, 5);

const lowEngReels = posts.filter(
  (p) => p.type === 'Reel' && (p.engagement_rate || 0) < 0.01
).length;

// Default list order: by views desc for audit table
posts.sort((a, b) => (b.views || 0) - (a.views || 0));

return [{
  json: {
    ok: true,
    meta: {
      username: profile.username,
      window_days: windowDays,
      generated_date: new Date().toISOString().slice(0, 10),
    },
    profile,
    posts,
    metrics: {
      post_count: posts.length,
      reel_count: reelsOnly.length,
      total_views: totalViews,
      total_likes: totalLikes,
      total_engagement: totalEngagement,
      avg_views: Math.round(avgViews),
      avg_likes: Math.round(avgLikes),
      avg_engagement_rate: avgEngagementRate,
      avg_views_last_10: Math.round(avgViewsLast10),
      posting_frequency_per_week: Math.round(postingFrequencyPerWeek * 10) / 10,
      low_engagement_reels: lowEngReels,
    },
    posting_day_breakdown: postingDayBreakdown,
    top_posts: topPosts,
    bottom_posts: bottomPosts,
  },
}];
"""

# --- Parse: private profile continues with warning ---
parse_code = nodes["Parse Merged Dataset"]["parameters"]["jsCode"]
parse_code = parse_code.replace(
    """if (profile.is_private) {
  return [{
    json: {
      ok: false,
      error: 'PRIVATE_PROFILE',
      message: 'Profile is private.',
      profile,
    },
  }];
}""",
    """if (profile.is_private) {
  return [{
    json: {
      ok: true,
      warning: 'PRIVATE_PROFILE',
      message: 'Profile is private — post metrics unavailable; profile fields only.',
      profile,
      posts: [],
    },
  }];
}""",
)
nodes["Parse Merged Dataset"]["parameters"]["jsCode"] = parse_code

# --- Build AI: add language ---
bai = nodes["Build AI Request"]["parameters"]["jsCode"]
bai = bai.replace(
    "Never invent metrics. If unclear, use General and Other.`;",
    "Never invent metrics. If unclear, use General and Other.\\n"
    "Also return primary_language (string, e.g. English, Hindi) inferred only from bio/captions, or empty string if unknown.`;",
)
bai = bai.replace(
    'Return strict JSON: {"posts":[{"index":0,"topic":"...","hook_type":"..."}]}',
    'Return strict JSON: {"posts":[{"index":0,"topic":"...","hook_type":"..."}],"primary_language":"..."}',
)
nodes["Build AI Request"]["parameters"]["jsCode"] = bai

merge_ai = nodes["Merge AI Classifications"]["parameters"]["jsCode"]
merge_ai = merge_ai.replace(
    "let parsed = {};",
    "let parsed = {};\nlet primaryLanguage = '';",
)
merge_ai = merge_ai.replace(
    "  parsed = JSON.parse(aiRaw);",
    "  parsed = JSON.parse(aiRaw);\n  primaryLanguage = parsed.primary_language || '';",
)
merge_ai = merge_ai.replace(
    "return [{\n  json: {\n    ok: true,\n    ...analytics,\n    posts,\n    insights,\n  },\n}];",
    "return [{\n  json: {\n    ok: true,\n    ...analytics,\n    posts,\n    insights,\n    primary_language: primaryLanguage,\n  },\n}];",
)
nodes["Merge AI Classifications"]["parameters"]["jsCode"] = merge_ai

# --- Prepare Whisper: reels only ---
nodes["Prepare Whisper Items"]["parameters"]["jsCode"] = """
const ctx = $('Normalize Input').first().json;
const merged = $('Merge AI Classifications').first().json;
const enable = ctx.enable_whisper !== false;
const reels = (merged.posts || [])
  .filter((p) => p.type === 'Reel' && p.video_url)
  .slice(0, 7);

if (!enable || !reels.length) {
  return [{ json: { skip: true, skip_all: true } }];
}

return reels.map((p) => ({
  json: {
    skip: false,
    skip_all: false,
    url: p.url,
    video_url: p.video_url,
    caption: p.caption,
    posted_at: p.posted_at,
    views: p.views,
  },
}));
"""

# --- Merge Transcripts: reels only + whisper merge ---
nodes["Merge Transcripts"]["parameters"]["jsCode"] = """
const merged = $('Merge AI Classifications').first().json;
const reelPosts = (merged.posts || []).filter((p) => p.type === 'Reel');

const whisperByUrl = {};
try {
  const whisperRows = $('Map Whisper Row').all();
  for (const row of whisperRows) {
    const j = row.json;
    if (j.url && j.text) {
      whisperByUrl[j.url] = { url: j.url, source: j.source || 'Whisper', text: j.text };
    }
  }
} catch (e) {
  // Whisper branch not executed
}

return reelPosts.map((p) => ({
  json: whisperByUrl[p.url] || {
    url: p.url,
    source: 'Caption',
    text: p.caption || '',
    posted_at: p.posted_at,
    views: p.views,
  },
}));
"""

# --- Build Workbook Payload: reels transcripts + language ---
bwp = nodes["Build Workbook Payload"]["parameters"]["jsCode"]
bwp = bwp.replace(
    "const transcripts = posts.map((p, idx) => {",
    "const reelPosts = posts.filter((p) => p.type === 'Reel');\n\nconst transcripts = reelPosts.map((p, idx) => {",
)
bwp = bwp.replace(
    "'Regional/Primary Language': '',",
    "'Regional/Primary Language': merged.primary_language || '',",
)
if "private_warning" not in bwp:
    bwp = bwp.replace(
        "const meta = merged.meta;",
        "const meta = merged.meta;\nconst privateWarning = parsed?.warning === 'PRIVATE_PROFILE' ? parsed.message : '';",
    )
nodes["Build Workbook Payload"]["parameters"]["jsCode"] = bwp

# Fix bwp - parsed variable doesn't exist in Build Workbook Payload, use merged.warning
bwp = nodes["Build Workbook Payload"]["parameters"]["jsCode"]
bwp = bwp.replace(
    "const privateWarning = parsed?.warning === 'PRIVATE_PROFILE' ? parsed.message : '';",
    "const privateWarning = merged.warning === 'PRIVATE_PROFILE' ? merged.message : '';",
)
nodes["Build Workbook Payload"]["parameters"]["jsCode"] = bwp

# --- Generate XLSX URL ---
nodes["Generate XLSX Workbooks"]["parameters"]["url"] = (
    "={{ $('Normalize Input').first().json.xlsx_api_url }}"
)

# --- Attach XLSX: add zip filename hint ---
nodes["Attach XLSX Binaries"]["parameters"]["jsCode"] = """
const payload = $('Build Workbook Payload').first().json;
const gen = $json;
const infB64 = gen.influencer_xlsx_base64;
const audB64 = gen.audit_xlsx_base64;
const username = payload.audit?.meta?.username || 'profile';

if (!infB64 || !audB64) {
  return [{
    json: {
      ok: true,
      warning: 'XLSX_API_UNAVAILABLE',
      has_binaries: false,
      data: payload,
      message: 'Workbook API did not return files. Deploy xlsx-api on Render and set xlsx_api_url in Normalize Input.',
    },
  }];
}

return [{
  json: {
    ok: true,
    has_binaries: true,
    username,
    metrics: payload.audit.metrics,
    influencer_filename: gen.influencer_filename,
    audit_filename: gen.audit_filename,
    zip_filename: `${username}_insta_audit_bundle.zip`,
    field_availability: payload.field_availability,
  },
  binary: {
    influencer_xlsx: {
      data: infB64,
      mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      fileName: gen.influencer_filename,
    },
    audit_xlsx: {
      data: audB64,
      mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      fileName: gen.audit_filename,
    },
  },
}];
"""

# --- Compression node ---
nodes["Compression"]["parameters"] = {
    "operation": "compress",
    "binaryPropertyName": "influencer_xlsx,audit_xlsx",
    "outputFormat": "zip",
    "fileName": "={{ $json.zip_filename || 'insta_audit_bundle.zip' }}",
    "binaryPropertyOutput": "bundle_zip",
}

# --- Respond Success: binary zip ---
nodes["Respond Success"]["parameters"] = {
    "respondWith": "binary",
    "responseDataSource": "bundle_zip",
    "options": {
        "responseCode": 200,
        "responseHeaders": {
            "entries": [
                {
                    "name": "Content-Disposition",
                    "value": "attachment; filename=\"insta_audit_bundle.zip\"",
                }
            ]
        },
    },
}

# Add new nodes for Whisper branch
if_whisper_id = nid()
download_id = nid()
map_whisper_id = nid()
collect_whisper_id = nid()
if_has_zip_id = nid()
respond_json_id = nid()

if_whisper = {
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
            "conditions": [
                {
                    "id": nid(),
                    "leftValue": "={{ $json.skip_all }}",
                    "rightValue": True,
                    "operator": {"type": "boolean", "operation": "notEquals"},
                }
            ],
            "combinator": "and",
        },
        "options": {},
    },
    "id": if_whisper_id,
    "name": "IF Whisper Needed",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2,
    "position": [1520, 0],
}

download_reel = {
    "parameters": {
        "url": "={{ $json.video_url }}",
        "options": {
            "response": {"response": {"responseFormat": "file", "outputPropertyName": "audio"}},
            "timeout": 120000,
        },
    },
    "id": download_id,
    "name": "Download Reel Video",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [1664, -80],
    "onError": "continueRegularOutput",
}

map_whisper = {
    "parameters": {
        "jsCode": """
const prev = $('Download Reel Video').item.json;
const text = $json.text || $json.transcript || '';
return [{
  json: {
    url: prev.url,
    source: text ? 'Whisper' : 'Caption',
    text: text || prev.caption || '',
    posted_at: prev.posted_at,
    views: prev.views,
  },
}];
"""
    },
    "id": map_whisper_id,
    "name": "Map Whisper Row",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [1920, -80],
}

collect_whisper = {
    "parameters": {
        "jsCode": "// Pass-through marker; Merge Transcripts reads Map Whisper Row via $('Map Whisper Row').all()\nreturn [{ json: { whisper_collected: true } }];",
        "mode": "runOnceForAllItems",
    },
    "id": collect_whisper_id,
    "name": "Collect Whisper Results",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [2048, -80],
}

if_has_zip = {
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
            "conditions": [
                {
                    "id": nid(),
                    "leftValue": "={{ $json.has_binaries }}",
                    "rightValue": True,
                    "operator": {"type": "boolean", "operation": "true"},
                }
            ],
            "combinator": "and",
        },
        "options": {},
    },
    "id": if_has_zip_id,
    "name": "IF Has XLSX",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2,
    "position": [2720, 0],
}

respond_json = {
    "parameters": {
        "respondWith": "json",
        "responseBody": "={{ JSON.stringify($json) }}",
        "options": {"responseCode": 200},
    },
    "id": respond_json_id,
    "name": "Respond JSON Fallback",
    "type": "n8n-nodes-base.respondToWebhook",
    "typeVersion": 1.1,
    "position": [3056, 160],
}

# Move Whisper node position
nodes["Whisper Transcribe (Optional)"]["position"] = [1792, -80]

# Add nodes to workflow
for n in [if_whisper, download_reel, map_whisper, collect_whisper, if_has_zip, respond_json]:
    wf["nodes"].append(n)

# Update connections
c = wf["connections"]

# Prepare -> IF Whisper
c["Prepare Whisper Items"] = {
    "main": [[{"node": "IF Whisper Needed", "type": "main", "index": 0}]]
}

c["IF Whisper Needed"] = {
    "main": [
        [{"node": "Download Reel Video", "type": "main", "index": 0}],
        [{"node": "Merge Transcripts", "type": "main", "index": 0}],
    ]
}

c["Download Reel Video"] = {
    "main": [[{"node": "Whisper Transcribe (Optional)", "type": "main", "index": 0}]]
}

c["Whisper Transcribe (Optional)"] = {
    "main": [[{"node": "Map Whisper Row", "type": "main", "index": 0}]]
}

c["Map Whisper Row"] = {
    "main": [[{"node": "Collect Whisper Results", "type": "main", "index": 0}]]
}

c["Collect Whisper Results"] = {
    "main": [[{"node": "Merge Transcripts", "type": "main", "index": 0}]]
}

# Remove old Prepare -> Merge Transcripts direct connection (replaced above)

c["Attach XLSX Binaries"] = {
    "main": [[{"node": "IF Has XLSX", "type": "main", "index": 0}]]
}

c["IF Has XLSX"] = {
    "main": [
        [{"node": "Compression", "type": "main", "index": 0}],
        [{"node": "Respond JSON Fallback", "type": "main", "index": 0}],
    ]
}

# IF Analytics OK should allow private profile with empty posts - add handling in Compute Analytics
# When private, posts empty - Compute Analytics fails NO_POSTS_IN_WINDOW - fix Parse to still pass?
# For private we return posts: [] - Compute Analytics will fail. Add check at start of Compute Analytics

compute = nodes["Compute Analytics"]["parameters"]["jsCode"]
compute = compute.replace(
    "const parsed = $('Parse Merged Dataset').first().json;\nconst profile = parsed.profile;\nlet posts = [...parsed.posts];",
    """const parsed = $('Parse Merged Dataset').first().json;
const profile = parsed.profile;

if (parsed.warning === 'PRIVATE_PROFILE') {
  const ctxPrivate = $('Normalize Input').first().json;
  return [{
    json: {
      ok: true,
      warning: 'PRIVATE_PROFILE',
      message: parsed.message,
      meta: {
        username: profile.username,
        window_days: ctxPrivate.window_days || 30,
        generated_date: new Date().toISOString().slice(0, 10),
      },
      profile,
      posts: [],
      metrics: {
        post_count: 0,
        reel_count: 0,
        total_views: 0,
        total_likes: 0,
        total_engagement: 0,
        avg_views: 0,
        avg_likes: 0,
        avg_engagement_rate: 0,
        avg_views_last_10: 0,
        posting_frequency_per_week: 0,
        low_engagement_reels: 0,
      },
      posting_day_breakdown: [],
      top_posts: [],
      bottom_posts: [],
    },
  }];
}

let posts = [...parsed.posts];""",
)
nodes["Compute Analytics"]["parameters"]["jsCode"] = compute

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(wf, indent=2), encoding="utf-8")
print("Wrote", OUT)
print("Nodes:", len(wf["nodes"]))
