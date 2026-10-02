#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Creative Studio provider-neutral job planner.

It creates auditable jobs for text/image/video/music. Actual external generation is
performed only when a provider adapter is configured; no fake generated media is claimed.
"""
import json, os, sqlite3, uuid
from datetime import datetime, timezone

def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

PROVIDERS={"text":"llm","image":"image_provider","video":"video_provider","music":"music_provider"}

def provider_status(kind):
    key={"text":"LLM_API_KEY","image":"IMAGE_API_KEY","video":"VIDEO_API_KEY","music":"MUSIC_API_KEY"}.get(kind)
    base={"text":"LLM_BASE_URL","image":"IMAGE_BASE_URL","video":"VIDEO_BASE_URL","music":"MUSIC_BASE_URL"}.get(kind)
    configured=bool(os.getenv(key or "") and os.getenv(base or ""))
    return {"kind":kind,"configured":configured,"provider":PROVIDERS.get(kind,"unknown"),"mode":"remote" if configured else "plan_only"}

def plan_job(db_path,kind,prompt,title="",metadata=None):
    kind=(kind or "text").strip().lower()
    if kind not in PROVIDERS: raise ValueError("نوع الإبداع غير مدعوم.")
    jid="cr_"+uuid.uuid4().hex[:12]
    status="ready_to_generate" if provider_status(kind)["configured"] else "planned"
    c=sqlite3.connect(db_path,timeout=10)
    c.execute("INSERT INTO creative_jobs(job_id,kind,title,prompt,status,provider,metadata_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",(jid,kind,title.strip(),prompt.strip(),status,PROVIDERS[kind],json.dumps(metadata or {},ensure_ascii=False),now(),now()))
    c.commit(); c.close()
    return {"job_id":jid,"kind":kind,"title":title,"status":status,"provider":PROVIDERS[kind],"provider_status":provider_status(kind),"message":"تم إنشاء خطة إبداعية محلية. لم يتم الادعاء بإنشاء ملف وسائط قبل تهيئة مزود فعلي."}

def list_jobs(db_path,limit=30):
    c=sqlite3.connect(db_path,timeout=10); c.row_factory=sqlite3.Row
    rows=c.execute("SELECT job_id,kind,title,prompt,status,provider,metadata_json,created_at,updated_at FROM creative_jobs ORDER BY id DESC LIMIT ?",(max(1,min(int(limit),100)),)).fetchall(); c.close()
    return [dict(r) for r in rows]
