#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared social-media knowledge layer over local content metrics."""
import sqlite3
from datetime import datetime, timezone

def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

def snapshot(db_path="manager.db"):
    c=sqlite3.connect(db_path,timeout=10); c.row_factory=sqlite3.Row
    total=c.execute("SELECT COUNT(*) n FROM content_metrics").fetchone()["n"]
    types=[dict(r) for r in c.execute("SELECT content_type,COUNT(*) n,ROUND(AVG(reach),1) avg_reach,ROUND(AVG(likes+comments+shares+saves),1) avg_interactions FROM content_metrics GROUP BY content_type ORDER BY n DESC").fetchall()]
    top=[dict(r) for r in c.execute("SELECT external_id,content_type,reach,likes,comments,shares,saves,substr(content_text,1,180) text FROM content_metrics ORDER BY (likes+comments+shares+saves) DESC,reach DESC LIMIT 10").fetchall()]
    c.close(); return {"total":total,"types":types,"top":top,"generated_at":now()}
