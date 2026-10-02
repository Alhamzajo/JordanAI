#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only Meta Graph API integration.

Tokens are accepted only for the duration of a request and are never stored.
The module imports public/page-authorized post data into the local content_metrics
schema. It does not publish, like, comment, follow, or otherwise act on Facebook.
"""
import json, re, sqlite3, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone

GRAPH_VERSION = "v26.0"
GRAPH_BASE = "https://graph.facebook.com/" + GRAPH_VERSION
UA = "Jordan-AI-Local/3.0"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _request(path, token, params=None, timeout=25):
    params = dict(params or {})
    params["access_token"] = token
    url = GRAPH_BASE + path
    url += ("?" + urllib.parse.urlencode(params, doseq=True))
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except Exception:
            data = {"error": {"message": raw or str(exc), "code": exc.code}}
        raise RuntimeError(_error_text(data)) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("تعذر الاتصال بـ Meta: " + str(exc.reason)) from exc


def _error_text(data):
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        msg = err.get("message") or "Meta Graph API error"
        code = err.get("code")
        sub = err.get("error_subcode")
        bits = [str(msg)]
        if code is not None: bits.append("code=" + str(code))
        if sub is not None: bits.append("subcode=" + str(sub))
        return " | ".join(bits)
    return "Meta Graph API error"


def verify_token(token):
    if not token or len(token) < 10:
        raise ValueError("التوكن غير صالح أو فارغ.")
    return _request("/me", token, {"fields": "id,name"})


def list_pages(user_token):
    data = _request("/me/accounts", user_token, {
        "fields": "id,name,access_token,tasks",
        "limit": "100",
    })
    return data.get("data", []) if isinstance(data, dict) else []


def resolve_page(page_id, token, user_token=None):
    """Return page metadata and a usable page token, without persisting it."""
    if page_id and user_token:
        for page in list_pages(user_token):
            if str(page.get("id")) == str(page_id):
                return page, page.get("access_token") or user_token
    if page_id:
        page = _request("/" + urllib.parse.quote(str(page_id), safe=""), token, {"fields": "id,name"})
        return page, token
    me = verify_token(token)
    return me, token


def _summary(obj, key):
    value = obj.get(key)
    if isinstance(value, dict):
        s = value.get("summary")
        if isinstance(s, dict):
            return int(s.get("total_count") or 0)
        return int(value.get("count") or 0)
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def _post_type(post):
    att = post.get("attachments") or {}
    rows = att.get("data") if isinstance(att, dict) else None
    if rows:
        a = rows[0] or {}
        media = str(a.get("media_type") or "").lower()
        typ = str(a.get("type") or "").lower()
        if "video" in media or "video" in typ: return "video"
        if "photo" in media or "photo" in typ: return "photo"
        if "link" in media or "link" in typ: return "link"
    return "text"


def _hashtags(text):
    return " ".join(re.findall(r"#[\w\u0600-\u06ff_]+", text or ""))


def _insights(post_id, token):
    metrics = "post_impressions,post_reach,post_engaged_users,post_clicks,post_reactions_by_type_total"
    try:
        data = _request("/" + urllib.parse.quote(str(post_id), safe="") + "/insights", token, {
            "metric": metrics,
            "period": "lifetime",
        })
    except Exception:
        return {}
    out = {}
    for item in data.get("data", []) if isinstance(data, dict) else []:
        name = item.get("name")
        vals = item.get("values") or []
        if not name or not vals: continue
        value = vals[-1].get("value")
        if isinstance(value, dict): value = sum(int(v or 0) for v in value.values() if isinstance(v, (int, float)))
        try: out[name] = int(value or 0)
        except Exception: pass
    return out


def _row(post, token):
    pid = str(post.get("id") or "").strip()
    text = (post.get("message") or post.get("story") or "").strip()
    insight = _insights(pid, token) if pid else {}
    likes = _summary(post, "likes")
    comments = _summary(post, "comments")
    shares = _summary(post, "shares")
    reactions = _summary(post, "reactions")
    likes = max(likes, reactions)
    return {
        "external_id": pid,
        "published_at": post.get("created_time") or "",
        "content_type": _post_type(post),
        "content_text": text,
        "reach": insight.get("post_reach", 0),
        "impressions": insight.get("post_impressions", 0),
        "views": 0,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "saves": 0,
        "followers_delta": 0,
        "link_clicks": insight.get("post_clicks", 0),
        "hashtags": _hashtags(text),
        "country": "Jordan",
        "governorate": "",
        "city": "",
        "topic": "",
        "created_at": _now(),
    }


def fetch_page_posts(page_id, token, limit=100, max_pages=10):
    fields = "id,message,story,created_time,permalink_url,attachments{media_type,type},likes.limit(0).summary(true),comments.limit(0).summary(true),shares,reactions.limit(0).summary(true)"
    rows, errors = [], []
    url_path = "/" + urllib.parse.quote(str(page_id), safe="") + "/feed"
    params = {"fields": fields, "limit": str(max(1, min(int(limit), 100)))}
    for _ in range(max(1, min(int(max_pages), 20))):
        try:
            data = _request(url_path, token, params)
        except Exception as exc:
            errors.append(str(exc)); break
        for post in data.get("data", []) if isinstance(data, dict) else []:
            try:
                row = _row(post, token)
                if row["external_id"]: rows.append(row)
            except Exception as exc:
                errors.append("منشور لم يُحلل: " + str(exc))
        paging = data.get("paging") if isinstance(data, dict) else None
        next_url = paging.get("next") if isinstance(paging, dict) else None
        if not next_url or len(rows) >= int(limit) * max(1, int(max_pages)): break
        parsed = urllib.parse.urlparse(next_url)
        qs = urllib.parse.parse_qs(parsed.query)
        qs.pop("access_token", None)
        url_path = parsed.path
        params = {k: v[-1] for k, v in qs.items()}
    return rows[: int(limit) * max(1, int(max_pages))], errors


def import_rows(db_path, rows):
    c = sqlite3.connect(db_path, timeout=10)
    count = 0
    try:
        for r in rows:
            c.execute("""INSERT INTO content_metrics(external_id,published_at,content_type,content_text,reach,impressions,views,likes,comments,shares,saves,followers_delta,link_clicks,created_at,hashtags,country,governorate,city,topic)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(external_id) DO UPDATE SET published_at=excluded.published_at,content_type=excluded.content_type,content_text=excluded.content_text,reach=excluded.reach,impressions=excluded.impressions,views=excluded.views,likes=excluded.likes,comments=excluded.comments,shares=excluded.shares,saves=excluded.saves,followers_delta=excluded.followers_delta,link_clicks=excluded.link_clicks,hashtags=excluded.hashtags,country=excluded.country,governorate=excluded.governorate,city=excluded.city,topic=excluded.topic""",
            (r["external_id"],r["published_at"],r["content_type"],r["content_text"],r["reach"],r["impressions"],r["views"],r["likes"],r["comments"],r["shares"],r["saves"],r["followers_delta"],r["link_clicks"],r["created_at"],r["hashtags"],r["country"],r["governorate"],r["city"],r["topic"]))
            count += 1
        c.commit()
    finally:
        c.close()
    return count


def sync_page(db_path, page_id, token, user_token=None, limit=100, max_pages=5):
    page, page_token = resolve_page(page_id, token, user_token=user_token)
    actual_id = str(page.get("id") or page_id or "")
    if not actual_id:
        raise RuntimeError("تعذر تحديد Page ID.")
    rows, errors = fetch_page_posts(actual_id, page_token, limit=limit, max_pages=max_pages)
    imported = import_rows(db_path, rows)
    return {
        "page": {"id": actual_id, "name": page.get("name", "")},
        "fetched": len(rows), "imported": imported, "errors": errors,
        "synced_at": _now(),
        "token_stored": False,
        "note": "قراءة فقط. لم يتم حفظ التوكن ولم يتم تنفيذ أي تفاعل خارجي."
    }
