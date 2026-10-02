# -*- coding: utf-8 -*-
"""Operational AI signals for the local manager: health, workload and data quality."""
import sqlite3
from analytics_core import DB, confidence_for_count


def _open(db_path):
    c=sqlite3.connect(db_path); c.row_factory=sqlite3.Row; return c

def analyze_manager(db_path=DB):
    c=_open(db_path); counts={t:c.execute(f"SELECT COUNT(*) n FROM {t}").fetchone()["n"] for t in ("participants","accounts","campaigns","tasks","content_metrics")}
    tasks={s:c.execute("SELECT COUNT(*) n FROM tasks WHERE status=?",(s,)).fetchone()["n"] for s in ("queued","processing","completed")}
    missing_geo=c.execute("SELECT COUNT(*) n FROM content_metrics WHERE COALESCE(country,'')='' AND COALESCE(governorate,'')='' AND COALESCE(city,'')=''").fetchone()["n"]
    missing_time=c.execute("SELECT COUNT(*) n FROM content_metrics WHERE COALESCE(published_at,'')=''").fetchone()["n"]
    c.close(); posts=counts["content_metrics"]; warnings=[]
    if posts and missing_geo: warnings.append(f"{missing_geo} منشورًا بلا موقع جغرافي واضح")
    if posts and missing_time: warnings.append(f"{missing_time} منشورًا بلا وقت نشر")
    if not posts: warnings.append("لا توجد بيانات محتوى بعد")
    return {"status":"ok","counts":counts,"tasks":tasks,"data_quality":{"warnings":warnings,"confidence":confidence_for_count(posts)},"message":"مؤشرات محلية لوصف صحة البيانات وسير العمل؛ لا تنفذ إجراءات خارجية."}

def account_insights(db_path=DB):
    c=_open(db_path); total=c.execute("SELECT COUNT(*) n FROM accounts").fetchone()["n"]; active=c.execute("SELECT COUNT(*) n FROM accounts WHERE status='active'").fetchone()["n"]; countries=c.execute("SELECT COUNT(DISTINCT NULLIF(country,'')) n FROM accounts").fetchone()["n"]; c.close()
    return {"total":total,"active":active,"inactive":max(0,total-active),"countries":countries,"message":"تغطية الحسابات تعتمد على البيانات المدخلة؛ لا يوجد اتصال تلقائي بحسابات خارجية."}

def campaign_insights(db_path=DB):
    c=_open(db_path); total=c.execute("SELECT COUNT(*) n FROM campaigns").fetchone()["n"]; queued=c.execute("SELECT COUNT(*) n FROM tasks WHERE status='queued'").fetchone()["n"]; processing=c.execute("SELECT COUNT(*) n FROM tasks WHERE status='processing'").fetchone()["n"]; completed=c.execute("SELECT COUNT(*) n FROM tasks WHERE status='completed'").fetchone()["n"]; c.close()
    note="لا توجد مهام عالقة." if queued==0 and processing==0 else f"هناك {queued+processing} مهمة غير مكتملة." 
    return {"campaigns":total,"queued":queued,"processing":processing,"completed":completed,"message":note}

def participant_insights(db_path=DB):
    c=_open(db_path); total=c.execute("SELECT COUNT(*) n FROM participants").fetchone()["n"]; active=c.execute("SELECT COUNT(*) n FROM participants WHERE status='active'").fetchone()["n"]; consent=c.execute("SELECT COUNT(*) n FROM participants WHERE consent=1").fetchone()["n"]; c.close()
    return {"total":total,"active":active,"consented":consent,"message":"المشاركون المعروضون في هذه النسخة بيانات محلية/تجريبية ما لم يثبت مصدر آخر."}
