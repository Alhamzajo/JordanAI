#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Complete Account Manager - local analytics/control plane.

The executor is intentionally SIMULATED_ONLY. This application does not log into,
control, or manufacture engagement for social-media accounts. AI features analyze
only data stored in the local database and public data explicitly fetched by a user.
"""
import csv, io, json, os, sqlite3, threading, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

APP_HOME=os.environ.get("JORDAN_AI_HOME", os.getcwd()); DB=os.path.join(APP_HOME,"manager.db"); PARTICIPANT_DB=os.path.join(APP_HOME,"participants_demo.db"); HOST="127.0.0.1"; PORT=int(os.environ.get("JORDAN_AI_PORT","8765"))
STOP=threading.Event(); MAX_BODY=12*1024*1024


def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

def conn():
    c=sqlite3.connect(DB, timeout=10); c.row_factory=sqlite3.Row
    c.execute("PRAGMA busy_timeout=10000"); c.execute("PRAGMA foreign_keys=ON")
    return c

def table_columns(c, table): return {r[1] for r in c.execute(f'PRAGMA table_info("{table}")')}

def init_db():
    c=conn(); c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA synchronous=NORMAL")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS participants(id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT UNIQUE,username TEXT,platform TEXT DEFAULT 'facebook',profile_url TEXT DEFAULT '',country TEXT DEFAULT '',language TEXT DEFAULT '',status TEXT DEFAULT 'active',consent INTEGER DEFAULT 1,points INTEGER DEFAULT 0,completed_tasks INTEGER DEFAULT 0,joined_at TEXT);
    CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT UNIQUE,username TEXT,country TEXT DEFAULT '',status TEXT DEFAULT 'active',source TEXT DEFAULT 'import',created_at TEXT);
    CREATE TABLE IF NOT EXISTS campaigns(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,target_url TEXT,action TEXT,target_count INTEGER DEFAULT 0,status TEXT DEFAULT 'draft',created_at TEXT);
    CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id INTEGER,account_id INTEGER,status TEXT DEFAULT 'queued',result TEXT DEFAULT '',created_at TEXT,updated_at TEXT);
    CREATE TABLE IF NOT EXISTS content_metrics(id INTEGER PRIMARY KEY AUTOINCREMENT,external_id TEXT,published_at TEXT,content_type TEXT,content_text TEXT,reach INTEGER DEFAULT 0,impressions INTEGER DEFAULT 0,views INTEGER DEFAULT 0,likes INTEGER DEFAULT 0,comments INTEGER DEFAULT 0,shares INTEGER DEFAULT 0,saves INTEGER DEFAULT 0,followers_delta INTEGER DEFAULT 0,link_clicks INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP,hashtags TEXT,country TEXT,governorate TEXT,city TEXT,topic TEXT);
    CREATE TABLE IF NOT EXISTS analysis_runs(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,scope TEXT,row_count INTEGER DEFAULT 0,summary_json TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS facebook_pages(id INTEGER PRIMARY KEY AUTOINCREMENT,page_id TEXT UNIQUE,page_name TEXT DEFAULT '',last_synced_at TEXT DEFAULT '',last_imported INTEGER DEFAULT 0,last_error TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS brain_memory(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT DEFAULT 'conversation',input_text TEXT,output_text TEXT,plan_json TEXT DEFAULT '{}',created_at TEXT);
    CREATE TABLE IF NOT EXISTS brain_runs(id INTEGER PRIMARY KEY AUTOINCREMENT,input_text TEXT,plan_json TEXT DEFAULT '{}',result_json TEXT DEFAULT '{}',created_at TEXT);
    CREATE TABLE IF NOT EXISTS creative_jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,job_id TEXT UNIQUE,kind TEXT,title TEXT DEFAULT '',prompt TEXT,status TEXT DEFAULT 'planned',provider TEXT DEFAULT '',metadata_json TEXT DEFAULT '{}',created_at TEXT,updated_at TEXT);
    CREATE TABLE IF NOT EXISTS social_patterns(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT,pattern_json TEXT DEFAULT '{}',confidence REAL DEFAULT 0,created_at TEXT);
    CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status); CREATE INDEX IF NOT EXISTS idx_tasks_campaign_status ON tasks(campaign_id,status);
    CREATE INDEX IF NOT EXISTS idx_participants_status ON participants(status); CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status);
    CREATE INDEX IF NOT EXISTS idx_content_published ON content_metrics(published_at); CREATE INDEX IF NOT EXISTS idx_content_country ON content_metrics(country);
    CREATE INDEX IF NOT EXISTS idx_content_geo ON content_metrics(governorate,city); CREATE INDEX IF NOT EXISTS idx_content_type ON content_metrics(content_type);
    CREATE INDEX IF NOT EXISTS idx_content_topic ON content_metrics(topic);
    """)
    cols=table_columns(c,"content_metrics")
    for name,definition in (("hashtags","TEXT"),("country","TEXT"),("governorate","TEXT"),("city","TEXT"),("topic","TEXT")):
        if name not in cols: c.execute(f"ALTER TABLE content_metrics ADD COLUMN {name} {definition}")
    # A unique external id makes repeated imports safe; current project has no duplicates.
    c.execute("DROP INDEX IF EXISTS ux_content_external_id")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_content_external_id ON content_metrics(external_id)")
    c.commit(); c.close()
    # Import demo participants only when the main database is empty.
    c=conn(); empty=not c.execute("SELECT 1 FROM participants LIMIT 1").fetchone(); c.close()
    if empty and os.path.exists(PARTICIPANT_DB):
        src=sqlite3.connect(PARTICIPANT_DB); src.row_factory=sqlite3.Row
        rows=src.execute("SELECT external_id,username,platform,profile_url,country,language,status,consent,points,completed_tasks,joined_at FROM participants").fetchall(); src.close()
        c=conn(); c.executemany("INSERT OR IGNORE INTO participants(external_id,username,platform,profile_url,country,language,status,consent,points,completed_tasks,joined_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",[tuple(r) for r in rows]); c.commit(); c.close()


def esc(value):
    return (str(value if value is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#39;"))

def num(value):
    try: return max(0,int(float(str(value or 0).replace(",",""))))
    except (ValueError,TypeError): return 0

def add_account(external_id,username="",country=""):
    c=conn(); c.execute("INSERT INTO accounts(external_id,username,country,status,source,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT(external_id) DO UPDATE SET username=excluded.username,country=excluded.country",(external_id,username,country,"active","import",now())); c.commit(); c.close()

def import_csv(data):
    reader=csv.DictReader(io.StringIO(data.decode("utf-8-sig",errors="replace"))); count=0
    for row in reader:
        eid=(row.get("external_id") or row.get("id") or row.get("username") or "").strip()
        if not eid: continue
        add_account(eid,(row.get("username") or "").strip(),(row.get("country") or "").strip()); count+=1
    return count

def import_content_csv(data):
    reader=csv.DictReader(io.StringIO(data.decode("utf-8-sig",errors="replace"))); count=0; skipped=0
    c=conn()
    for row in reader:
        eid=(row.get("external_id") or row.get("id") or "").strip()
        if not eid: skipped+=1; continue
        values=(eid,(row.get("published_at") or "").strip(),(row.get("content_type") or "unknown").strip(),(row.get("content_text") or "").strip(),num(row.get("reach")),num(row.get("impressions")),num(row.get("views")),num(row.get("likes")),num(row.get("comments")),num(row.get("shares")),num(row.get("saves")),num(row.get("followers_delta")),num(row.get("link_clicks")),(row.get("hashtags") or "").strip(),(row.get("country") or "").strip(),(row.get("governorate") or "").strip(),(row.get("city") or "").strip(),(row.get("topic") or "").strip())
        c.execute("""INSERT INTO content_metrics(external_id,published_at,content_type,content_text,reach,impressions,views,likes,comments,shares,saves,followers_delta,link_clicks,hashtags,country,governorate,city,topic) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(external_id) DO UPDATE SET published_at=excluded.published_at,content_type=excluded.content_type,content_text=excluded.content_text,reach=excluded.reach,impressions=excluded.impressions,views=excluded.views,likes=excluded.likes,comments=excluded.comments,shares=excluded.shares,saves=excluded.saves,followers_delta=excluded.followers_delta,link_clicks=excluded.link_clicks,hashtags=excluded.hashtags,country=excluded.country,governorate=excluded.governorate,city=excluded.city,topic=excluded.topic""",values); count+=1
    c.commit(); c.close(); return count,skipped

def create_campaign(name,url,action,target_count):
    c=conn(); cur=c.execute("INSERT INTO campaigns(name,target_url,action,target_count,status,created_at) VALUES(?,?,?,?,?,?)",(name,url,action,target_count,"queued",now())); cid=cur.lastrowid
    rows=c.execute("SELECT id FROM accounts WHERE status='active' ORDER BY id LIMIT ?",(target_count,)).fetchall()
    for r in rows: c.execute("INSERT INTO tasks(campaign_id,account_id,status,created_at,updated_at) VALUES(?,?,?,?,?)",(cid,r["id"],"queued",now(),now()))
    c.commit(); c.close(); return cid,len(rows)

def worker():
    while not STOP.is_set():
        c=conn(); task=c.execute("SELECT * FROM tasks WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
        if not task: c.close(); STOP.wait(1.0); continue
        c.execute("UPDATE tasks SET status='processing',updated_at=? WHERE id=?",(now(),task["id"])); c.commit(); time.sleep(.08)
        c.execute("UPDATE tasks SET status='completed',result=?,updated_at=? WHERE id=?",("SIMULATED_ONLY",now(),task["id"])); c.execute("UPDATE campaigns SET status='running' WHERE id=?",(task["campaign_id"],)); c.commit(); c.close()
        c=conn(); left=c.execute("SELECT COUNT(*) n FROM tasks WHERE campaign_id=? AND status!='completed'",(task["campaign_id"],)).fetchone()["n"]
        if left==0: c.execute("UPDATE campaigns SET status='completed' WHERE id=?",(task["campaign_id"],)); c.commit()
        c.close()

def layout(title,body):
    return f'''<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>
body{{font-family:Arial,sans-serif;background:#f3f4f6;margin:0;color:#111827}}nav{{background:#111827;padding:12px;display:flex;flex-wrap:wrap;gap:8px}}nav a{{color:#fff;text-decoration:none;padding:8px 10px;border-radius:7px}}nav a:hover{{background:#374151}}main{{max-width:1100px;margin:20px auto;padding:0 14px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}}.card{{background:#fff;border-radius:14px;padding:17px;margin:12px 0;box-shadow:0 2px 12px #0001}}.stat{{font-size:27px;font-weight:700}}.muted,.small{{color:#6b7280;font-size:13px}}.ok{{color:#15803d}}.warn{{color:#b45309}}.bad{{color:#b91c1c}}table{{width:100%;border-collapse:collapse;display:block;overflow:auto}}td,th{{padding:9px;border-bottom:1px solid #eee;text-align:right;white-space:nowrap}}input,select,textarea{{width:100%;box-sizing:border-box;padding:10px;margin:6px 0 12px;border:1px solid #d1d5db;border-radius:8px}}button{{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:10px 16px;cursor:pointer}}a{{color:#1d4ed8}}.pill{{display:inline-block;padding:4px 8px;border-radius:999px;background:#eef2ff;margin:2px}}.two{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}@media(max-width:700px){{.two{{grid-template-columns:1fr}}}}
</style></head><body><nav><a href="/">الرئيسية</a><a href="/participants">المشاركون</a><a href="/accounts">الحسابات</a><a href="/campaigns">الحملات</a><a href="/import">استيراد الحسابات</a><a href="/content-import">استيراد المحتوى</a><a href="/insights">AI Insights</a><a href="/algorithm-ai">🧠 AI الخوارزميات</a><a href="/jordan-ai">🇯🇴 Jordan AI</a><a href="/reels-ai">🎬 AI Reels</a><a href="/jordan-news">📰 أخبار الأردن</a><a href="/facebook">Facebook</a><a href="/brain">🧠 Jordan AI Brain</a><a href="/creative">🎨 Creative Studio</a><a href="/about">الحدود</a></nav><main>{body}</main></body></html>'''

def multipart_payload(raw,content_type):
    marker="boundary="
    if marker not in content_type: return raw
    boundary=content_type.split(marker,1)[1].split(';',1)[0].strip().strip('"').encode()
    for part in raw.split(b"--"+boundary):
        if b'filename=' not in part: continue
        head,sep,payload=part.partition(b"\r\n\r\n")
        if not sep: continue
        return payload.rsplit(b"\r\n",1)[0]
    return b""

class H(BaseHTTPRequestHandler):
    def send_html(self,s,code=200):
        b=s.encode("utf-8"); self.send_response(code); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(b)
    def redir(self,p): self.send_response(303); self.send_header("Location",p); self.end_headers()
    def send_json(self,data,code=200):
        b=json.dumps(data,ensure_ascii=False).encode("utf-8"); self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(b))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(b)
    def body(self):
        n=num(self.headers.get("Content-Length","0"));
        if n>MAX_BODY: raise ValueError("الملف أكبر من الحد المسموح.")
        return self.rfile.read(n)
    def log_message(self,*args): return
    def facebook_page(self,message="",result=None):
        c=conn()
        pages=c.execute("SELECT page_id,page_name,last_synced_at,last_imported,last_error FROM facebook_pages ORDER BY id DESC").fetchall()
        c.close()
        note=f"<div class='card warn'>{esc(message)}</div>" if message else ""
        res=""
        if result:
            res += "<div class='card ok'><h3>تمت المزامنة</h3>"
            res += f"<p>الصفحة: <b>{esc(result.get('page',{}).get('name',''))}</b> — {esc(result.get('page',{}).get('id',''))}</p>"
            res += f"<p>تم جلب {result.get('fetched',0)} منشورًا، واستيراد/تحديث {result.get('imported',0)}.</p>"
            if result.get("errors"):
                res += "<p class='warn'>ملاحظات API: " + "<br>".join(esc(x) for x in result["errors"][:8]) + "</p>"
            res += "<p class='small'>"+esc(result.get("note",""))+"</p></div>"
        rows=[]
        for r in pages:
            status = "آخر مزامنة: "+str(r["last_synced_at"] or "—")
            if r["last_error"]: status += " — خطأ: "+str(r["last_error"])
            rows.append(f"<tr><td>{esc(r['page_id'])}</td><td>{esc(r['page_name'])}</td><td>{esc(status)}</td><td>{r['last_imported']}</td></tr>")
        history = "<div class='card'><h3>الصفحات المعروفة محليًا</h3><table><tr><th>Page ID</th><th>الاسم</th><th>الحالة</th><th>آخر عدد مستورد</th></tr>"+"".join(rows)+"</table></div>" if rows else ""
        body=note+res+"""<h2>🔗 Facebook / Meta — قراءة فقط</h2>
        <div class="card"><p>هذه الوحدة تستخدم Meta Graph API لجلب بيانات الصفحة والمنشورات إلى التحليل المحلي.</p><p class="ok">لا يتم حفظ Access Token، ولا يتم النشر أو الإعجاب أو التعليق أو المتابعة.</p>
        <form method="post" action="/facebook"><label>Access Token</label><input name="token" type="password" required autocomplete="off" placeholder="User Access Token أو Page Access Token"><label>Page ID <span class="small">اختياري عند استخدام User Token، ومطلوب عادةً مع Page Token</span></label><input name="page_id" inputmode="numeric" placeholder="مثال: 123456789"><div class="two"><div><label>عدد المنشورات</label><input name="limit" type="number" min="1" max="100" value="50"></div><div><label>عدد صفحات API</label><input name="max_pages" type="number" min="1" max="5" value="2"></div></div><button>تحقق ومزامنة الآن</button></form></div>
        <div class="card small"><b>ما الذي سيُستورد؟</b><br>معرّف المنشور، تاريخ النشر، النوع، النص، الإعجابات، التعليقات، المشاركات، والوصول/الانطباعات/النقرات عندما تسمح صلاحيات Meta ونسخة API بذلك. بعض المقاييس قد تبقى 0 إذا لم يمنحها API.</div>"""+history
        self.send_html(layout("Facebook",body))
    def insights_page(self):
        from ai_insights import build_insights
        from ai_engine import analyze_content
        data=analyze_content(); insights=build_insights();
        if data["status"]!="ok": body="<h2>AI Insights</h2><div class='card'><p>لا توجد بيانات منشورات بعد.</p></div>"
        else:
            t=data["totals"]; cards=[f"<div class='card'><div class='stat'>{data['posts']:,}</div>منشور محلل</div>",f"<div class='card'><div class='stat'>{t['reach']:,}</div>إجمالي الوصول</div>",f"<div class='card'><div class='stat'>{t['engagement_rate']:.2f}%</div>معدل التفاعل المجمع</div>",f"<div class='card'><div class='stat'>{esc(data['confidence']['label'])}</div>الثقة</div>"]
            cards.append("<div class='card'><h3>🧠 الاستنتاجات</h3>"+"<br>".join("• "+esc(x) for x in insights["insights"])+"</div>")
            rows=[]
            for typ,x in sorted(data["type_stats"].items()): rows.append(f"<tr><td>{esc(typ)}</td><td>{x['posts']}</td><td>{x['avg_reach']}</td><td>{x['avg_engagement_rate']:.2f}%</td><td>{x['avg_share_rate']:.2f}%</td><td>{x['avg_save_rate']:.2f}%</td></tr>")
            table="<table><tr><th>النوع</th><th>المنشورات</th><th>متوسط الوصول</th><th>التفاعل</th><th>المشاركة</th><th>الحفظ</th></tr>"+"".join(rows)+"</table>"
            body="<h2>AI Insights</h2><div class='grid'>"+"".join(cards)+"</div><div class='card'><h3>الأداء حسب النوع</h3>"+table+"</div>"
        self.send_html(layout("AI Insights",body))
    def algorithm_ai_page(self):
        from algorithm_ai import analyze_algorithm_signals
        data=analyze_algorithm_signals()
        if data["status"]!="ok": self.send_html(layout("AI الخوارزميات","<h2>🧠 AI الخوارزميات</h2><div class='card'>"+esc(data["message"])+"</div>")); return
        rows=[]
        for typ,x in sorted(data["type_signals"].items()): rows.append(f"<tr><td>{esc(typ)}</td><td>{x['posts']}</td><td>{x['avg_reach']}</td><td>{x['avg_engagement_rate']:.2f}%</td><td>{x['avg_share_rate']:.2f}%</td><td>{x['avg_save_rate']:.2f}%</td><td>{x['avg_click_rate']:.2f}%</td></tr>")
        corr="<br>".join(f"{esc(k)}: {('غير كافٍ' if v is None else v)}" for k,v in data["correlations"].items())
        body="<h2>🧠 AI — مختص إشارات الخوارزميات</h2><div class='grid'><div class='card'><div class='stat'>"+str(data["posts"])+"</div>منشور</div><div class='card'><div class='stat'>"+esc(data["confidence"]["label"])+"</div>الثقة</div></div><div class='card'><h3>إشارات حسب نوع المحتوى</h3><table><tr><th>النوع</th><th>العدد</th><th>الوصول</th><th>التفاعل</th><th>المشاركة</th><th>الحفظ</th><th>النقر</th></tr>"+"".join(rows)+"</table></div><div class='two'><div class='card'><h3>العلاقات الإحصائية</h3>"+corr+"</div><div class='card'><h3>فرضيات قابلة للاختبار</h3>"+"<br>".join("• "+esc(x) for x in data["hypotheses"])+"</div></div><div class='card small'>"+esc(data["note"])+"</div>"
        self.send_html(layout("AI الخوارزميات",body))
    def jordan_ai_page(self):
        from jordan_ai import analyze_jordan
        from ai_engine import analyze_content
        data=analyze_jordan(); overall=analyze_content(jordan_only=True)
        if data["status"]!="ok": body="<h2>🇯🇴 Jordan AI</h2><div class='card'><p>"+esc(data["message"])+"</p><p class='small'>عدد الصفوف الكلي في قاعدة المحتوى: "+str(data.get("total_rows",0))+"</p></div>"
        else:
            body=f"<h2>🇯🇴 Jordan AI</h2><div class='grid'><div class='card'><div class='stat'>{data['posts']:,}</div>منشور أردني</div><div class='card'><div class='stat'>{data['confidence']['label']}</div>الثقة</div><div class='card'><div class='stat'>{overall['totals']['engagement_rate']:.2f}%</div>معدل التفاعل</div></div>"
            topic_html="<br>".join(esc(x[0])+" — "+f"{x[1]:.2f}%" for x in data["topics"][:15]) or "لا توجد بيانات"
            body+="<div class='card'><h3>📌 المواضيع</h3>"+topic_html+"</div>"
            body+="<div class='two'><div class='card'><h3>🇯🇴 المحافظات</h3>"+"<br>".join(esc(x[0])+" — "+f"{x[1]:.2f}%" for x in data["governorates"][:15])+"</div><div class='card'><h3>📍 المدن</h3>"+"<br>".join(esc(x[0])+" — "+f"{x[1]:.2f}%" for x in data["cities"][:15])+"</div></div>"
            body+="<div class='card small'>"+esc(data["note"])+"</div>"
        self.send_html(layout("Jordan AI",body))
    def reels_ai_page(self):
        self.send_html(layout("AI Reels",'''<h2>🎬 AI Reels</h2><div class="card"><form method="post" action="/reels-ai"><label>نص المنشور</label><textarea name="text" rows="6" required placeholder="اكتب النص الأردني هنا..."></textarea><button>توليد فكرة الريلز</button></form></div>'''))
    def jordan_news_page(self):
        from jordan_news import fetch_latest_jordan_news
        data=fetch_latest_jordan_news(); body="<h2>📰 أخبار الأردن</h2>"
        if not data["items"]: body+="<div class='card warn'>تعذر الوصول إلى مصدر الأخبار حاليًا. لم يتم اختلاق أخبار بديلة.</div>"
        for x in data["items"]: body+=f"<div class='card'><h3>{esc(x['title'])}</h3><p>{esc(x['summary'])}</p><p><a href='{esc(x['link'])}' target='_blank' rel='noopener'>المصدر</a></p></div>"
        self.send_html(layout("أخبار الأردن",body))
    def brain_page(self, result=None):
        result_html=""
        if result:
            answer=esc(result.get("answer","")); tools=esc(", ".join(result.get("plan",{}).get("tools",[]))); llm="نعم" if result.get("llm_used") else "لا"
            result_html=f"<div class='card'><h3>🧠 النتيجة</h3><pre style=\"white-space:pre-wrap;font-family:Arial\">{answer}</pre><p class='small'>الأدوات: {tools} | LLM خارجي: {llm}</p></div>"
        body=result_html+'''<h2>🧠 Jordan AI Brain</h2><div class="card"><p>طبقة العقل الموحدة: تفهم الطلب، تختار الأدوات، تجمع البيانات المحلية، ثم تنتج جوابًا قابلًا للتدقيق.</p><form method="post" action="/brain"><label>اكتب طلبك</label><textarea name="prompt" rows="5" required placeholder="مثال: حلل أداء المحتوى الأردني واشرح لي أين توجد الإشارات المهمة."></textarea><button>اسأل الدماغ</button></form></div><div class="card"><h3>ما الذي يعرفه الآن؟</h3><p>Content AI · Algorithm AI · Jordan AI · AI Insights · Facebook/Meta · Creative Studio</p><p class="small">يمكن تفعيل مزود LLM خارجي محليًا عبر متغيرات البيئة LLM_BASE_URL وLLM_API_KEY وLLM_MODEL. لا يتم حفظ المفتاح في قاعدة البيانات.</p></div>'''
        return self.send_html(layout("Jordan AI Brain",body))

    def creative_page(self, result=None):
        result_html=""
        if result:
            result_html=f"<div class='card ok'><h3>تم إنشاء الوظيفة</h3><p>Job ID: <b>{esc(result.get('job_id'))}</b></p><p>{esc(result.get('message'))}</p><p>الحالة: {esc(result.get('status'))} — المزود: {esc(result.get('provider'))}</p></div>"
        from creative_studio import list_jobs, provider_status
        jobs=list_jobs(DB)
        trs="".join(f"<tr><td>{esc(r['job_id'])}</td><td>{esc(r['kind'])}</td><td>{esc(r['title'])}</td><td>{esc(r['status'])}</td><td>{esc(r['provider'])}</td><td>{esc(r['created_at'])}</td></tr>" for r in jobs)
        body=result_html+'''<h2>🎨 Creative Studio</h2><div class="card"><p>تحويل فكرة الحملة إلى وظائف نص/صورة/فيديو/موسيقى، مع طبقة مزودين قابلة للتبديل. لا ندّعي توليد ملف وسائط حقيقي دون مزود مهيأ.</p><form method="post" action="/creative"><div class="two"><div><label>النوع</label><select name="kind"><option value="text">نص</option><option value="image">صورة</option><option value="video">فيديو</option><option value="music">موسيقى</option></select></div><div><label>عنوان</label><input name="title" placeholder="حملة الأردن"></div></div><label>الفكرة / الوصف</label><textarea name="prompt" rows="5" required placeholder="اكتب الفكرة الإبداعية..."></textarea><button>أنشئ Creative Job</button></form></div>'''
        statuses=[provider_status(k) for k in ("text","image","video","music")]
        body+="<div class='grid'>"+"".join(f"<div class='card'><b>{esc(x['kind'])}</b><p>{'🟢 مهيأ' if x['configured'] else '⚪ خطة فقط'}</p><span class='small'>{esc(x['provider'])}</span></div>" for x in statuses)+"</div>"
        body+="<div class='card'><h3>آخر الوظائف</h3><table><tr><th>Job</th><th>النوع</th><th>العنوان</th><th>الحالة</th><th>المزود</th><th>التاريخ</th></tr>"+trs+"</table></div>"
        return self.send_html(layout("Creative Studio",body))

    def do_GET(self):
        p=urlparse(self.path).path
        if p=="/facebook": return self.facebook_page()
        if p=="/brain": return self.brain_page()
        if p=="/creative": return self.creative_page()
        if p=="/api/facebook-pages":
            c=conn(); rows=[dict(r) for r in c.execute("SELECT page_id,page_name,last_synced_at,last_imported,last_error FROM facebook_pages ORDER BY id DESC")]; c.close(); return self.send_json({"pages":rows})
        if p=="/api/brain":
            from brain import Brain
            return self.send_json(Brain(DB).ask("ما حالة النظام وما الأدوات المتاحة؟",save=False))
        if p=="/api/creative":
            from creative_studio import list_jobs, provider_status
            return self.send_json({"providers":[provider_status(k) for k in ("text","image","video","music")],"jobs":list_jobs(DB)})
        if p=="/api/social-brain":
            from social_media_brain import snapshot
            return self.send_json(snapshot(DB))
        if p=="/content-import": return self.send_html(layout("استيراد المحتوى",'''<h2>استيراد بيانات المحتوى</h2><div class="card"><p>يدعم الحقول الأساسية مع country/governorate/city/topic/hashtags.</p><form method="post" action="/content-import" enctype="multipart/form-data"><input type="file" name="file" accept=".csv" required><button>استيراد وتحليل</button></form><p class="small">external_id,published_at,content_type,content_text,reach,impressions,views,likes,comments,shares,saves,followers_delta,link_clicks,hashtags,country,governorate,city,topic</p></div>'''))
        if p=="/algorithm-ai": return self.algorithm_ai_page()
        if p=="/jordan-ai": return self.jordan_ai_page()
        if p=="/insights": return self.insights_page()
        if p=="/reels-ai": return self.reels_ai_page()
        if p=="/jordan-news": return self.jordan_news_page()
        if p=="/api/ai-overview":
            from manager_ai import analyze_manager
            return self.send_json(analyze_manager())
        if p=="/api/content-ai":
            from ai_engine import analyze_content
            return self.send_json(analyze_content())
        if p=="/api/algorithm-ai":
            from algorithm_ai import analyze_algorithm_signals
            return self.send_json(analyze_algorithm_signals())
        if p=="/api/jordan-ai":
            from jordan_ai import analyze_jordan
            return self.send_json(analyze_jordan())
        c=conn()
        if p=="/":
            from manager_ai import analyze_manager
            a=analyze_manager(); q=a["tasks"]; counts=a["counts"]; warns=a["data_quality"]["warnings"]
            body=f"<h1>لوحة التحكم</h1><div class='grid'><div class='card'><div class='stat'>{counts['participants']:,}</div>مشاركون</div><div class='card'><div class='stat'>{counts['accounts']:,}</div>حسابات</div><div class='card'><div class='stat'>{counts['campaigns']:,}</div>حملات</div><div class='card'><div class='stat'>{counts['content_metrics']:,}</div>منشورات محللة</div><div class='card'><div class='stat'>{q['queued']:,}</div>مهام منتظرة</div><div class='card'><div class='stat'>{q['completed']:,}</div>مهام مكتملة</div></div><div class='card'><h3>🤖 صحة النظام بالذكاء التحليلي</h3><p class='ok'>النظام يعمل محليًا. التنفيذ الخارجي غير موصول ويظل SIMULATED_ONLY.</p>"+"<br>".join("• "+esc(x) for x in warns)+"</div>"; c.close(); return self.send_html(layout("لوحة التحكم",body))
        if p=="/participants":
            from manager_ai import participant_insights
            ai=participant_insights(); page=max(1,num(parse_qs(urlparse(self.path).query).get("page",[1])[0])); size=50; total=c.execute("SELECT COUNT(*) n FROM participants").fetchone()["n"]; pages=max(1,(total+size-1)//size); page=min(page,pages); rows=c.execute("SELECT id,external_id,username,country,language,points,status FROM participants ORDER BY id LIMIT ? OFFSET ?",(size,(page-1)*size)).fetchall(); c.close(); trs="".join(f"<tr><td>{r['id']}</td><td>{esc(r['external_id'])}</td><td>{esc(r['username'])}</td><td>{esc(r['country'])}</td><td>{esc(r['language'])}</td><td>{r['points']}</td><td>{esc(r['status'])}</td></tr>" for r in rows); return self.send_html(layout("المشاركون",f"<h2>المشاركون</h2><div class='grid'><div class='card'><div class='stat'>{ai['total']:,}</div>إجمالي</div><div class='card'><div class='stat'>{ai['active']:,}</div>نشط</div><div class='card'><div class='stat'>{ai['consented']:,}</div>بموافقة مسجلة</div></div><div class='card'><p class='small'>{esc(ai['message'])}</p></div><div class='card'><table><tr><th>ID</th><th>External</th><th>Username</th><th>Country</th><th>Language</th><th>Points</th><th>Status</th></tr>{trs}</table></div>"))
        if p=="/accounts":
            from manager_ai import account_insights
            ai=account_insights(); rows=c.execute("SELECT id,external_id,username,country,status FROM accounts ORDER BY id DESC").fetchall(); c.close(); trs="".join(f"<tr><td>{r['id']}</td><td>{esc(r['external_id'])}</td><td>{esc(r['username'])}</td><td>{esc(r['country'])}</td><td>{esc(r['status'])}</td></tr>" for r in rows); return self.send_html(layout("الحسابات",f"<h2>الحسابات</h2><div class='grid'><div class='card'><div class='stat'>{ai['total']:,}</div>إجمالي</div><div class='card'><div class='stat'>{ai['active']:,}</div>نشط</div><div class='card'><div class='stat'>{ai['countries']:,}</div>دول مختلفة</div></div><div class='card small'>{esc(ai['message'])}</div><div class='card'><table><tr><th>ID</th><th>External</th><th>Username</th><th>Country</th><th>Status</th></tr>{trs}</table></div>"))
        if p=="/import": c.close(); return self.send_html(layout("استيراد الحسابات",'''<h2>استيراد الحسابات</h2><div class="card"><form method="post" action="/import" enctype="multipart/form-data"><input type="file" name="file" accept=".csv" required><button>استيراد</button></form><p class="small">external_id,username,country</p></div>'''))
        if p=="/campaigns":
            from manager_ai import campaign_insights
            ai=campaign_insights(); rows=c.execute("SELECT * FROM campaigns ORDER BY id DESC").fetchall(); c.close(); trs="".join(f"<tr><td>{r['id']}</td><td>{esc(r['name'])}</td><td>{esc(r['action'])}</td><td>{esc(r['target_url'])}</td><td>{r['target_count']}</td><td>{esc(r['status'])}</td></tr>" for r in rows)
            form="<div class='card'><form method='post' action='/campaign'><label>اسم الحملة</label><input name='name' required><label>الرابط</label><input name='url' required><label>المهمة</label><select name='action'><option>follow</option><option>view</option><option>like</option></select><label>العدد</label><input name='count' type='number' min='1' value='10'><button>إنشاء</button></form></div>"
            body=f"<h2>الحملات</h2><div class='grid'><div class='card'><div class='stat'>{ai['campaigns']:,}</div>حملات</div><div class='card'><div class='stat'>{ai['queued']:,}</div>مهام منتظرة</div><div class='card'><div class='stat'>{ai['completed']:,}</div>مهام مكتملة</div></div><div class='card'><p class='small'>🤖 {esc(ai['message'])} التنفيذ الخارجي غير موصول.</p></div>{form}<div class='card'><table><tr><th>ID</th><th>الاسم</th><th>المهمة</th><th>الرابط</th><th>العدد</th><th>الحالة</th></tr>{trs}</table></div>"
            return self.send_html(layout("الحملات",body))
        if p=="/about": c.close(); return self.send_html(layout("الحدود",'''<div class="card"><h2>حدود النظام</h2><p>الذكاء الاصطناعي هنا تحليلي محلي: يكتشف أنماطًا من البيانات التي تزوده بها، ولا يدّعي معرفة خوارزميات المنصات الخاصة.</p><p>لا توجد عمليات اصطناعية لرفع التفاعل، ولا تحكم آلي بحسابات Facebook.</p></div>'''))
        c.close(); return self.send_html(layout("404","<div class='card'>المسار غير موجود.</div>"),404)
    def do_POST(self):
        p=urlparse(self.path).path; ct=self.headers.get("Content-Type","")
        try: raw=self.body()
        except Exception as exc: return self.send_html(layout("خطأ",f"<div class='card bad'>{esc(exc)}</div>"),413)
        if p=="/brain":
            data=parse_qs(raw.decode(errors="replace")); prompt=data.get("prompt",[""])[0].strip()
            if not prompt: return self.brain_page()
            try:
                from brain import Brain
                return self.brain_page(Brain(DB).ask(prompt))
            except Exception as exc:
                return self.brain_page({"answer":"تعذر تشغيل الدماغ: "+str(exc),"plan":{"tools":[]},"llm_used":False})
        if p=="/creative":
            data=parse_qs(raw.decode(errors="replace")); kind=data.get("kind",["text"])[0].strip(); title=data.get("title",[""])[0].strip(); prompt=data.get("prompt",[""])[0].strip()
            try:
                from creative_studio import plan_job
                return self.creative_page(plan_job(DB,kind,prompt,title))
            except Exception as exc:
                return self.creative_page({"job_id":"-","status":"error","provider":"","message":"تعذر إنشاء الوظيفة: "+str(exc)})
        if p=="/facebook":
            data=parse_qs(raw.decode(errors="replace")); token=data.get("token",[""])[0].strip(); page_id=data.get("page_id",[""])[0].strip()
            try: limit=max(1,min(100,int(data.get("limit",["50"])[0]))); max_pages=max(1,min(5,int(data.get("max_pages",["2"])[0])))
            except ValueError: limit,max_pages=50,2
            if not token: return self.facebook_page("لم يتم إدخال Access Token.")
            try:
                from facebook_meta import sync_page, list_pages, verify_token
                if not page_id:
                    pages=list_pages(token)
                    if len(pages)==1:
                        page_id=str(pages[0].get("id"))
                    elif len(pages)>1:
                        names=", ".join(str(x.get("name") or x.get("id")) for x in pages[:20])
                        return self.facebook_page("تم التحقق من User Token، لكن توجد عدة صفحات. أدخل Page ID للصفحة المطلوبة. الصفحات: "+names)
                    else:
                        me=verify_token(token)
                        return self.facebook_page("تم التحقق من التوكن باسم "+str(me.get("name",""))+"، لكن لم يتم العثور على صفحة. إذا كان هذا Page Token فأدخل Page ID ثم أعد المحاولة.")
                result=sync_page(DB,page_id,token,user_token=token,limit=limit,max_pages=max_pages)
                c=conn(); c.execute("INSERT INTO facebook_pages(page_id,page_name,last_synced_at,last_imported,last_error) VALUES(?,?,?,?,?) ON CONFLICT(page_id) DO UPDATE SET page_name=excluded.page_name,last_synced_at=excluded.last_synced_at,last_imported=excluded.last_imported,last_error=excluded.last_error",(result["page"]["id"],result["page"]["name"],result["synced_at"],result["imported"],"\n".join(result.get("errors",[])[:3]))); c.execute("INSERT INTO analysis_runs(kind,scope,row_count,summary_json,created_at) VALUES(?,?,?,?,?)",("facebook_sync",result["page"]["id"],result["imported"],json.dumps(result,ensure_ascii=False),now())); c.commit(); c.close()
                return self.facebook_page(result=result)
            except Exception as exc:
                return self.facebook_page("فشلت المزامنة: "+str(exc))
        if p=="/campaign":
            data=parse_qs(raw.decode(errors="replace"));
            try: count=max(1,int(data.get("count",["1"])[0]))
            except ValueError: count=1
            create_campaign(data.get("name",[""])[0].strip(),data.get("url",[""])[0].strip(),data.get("action",["view"])[0],count); return self.redir("/campaigns")
        if p in ("/import","/content-import"):
            payload=multipart_payload(raw,ct) if "multipart/form-data" in ct else raw
            if not payload: return self.send_html(layout("الاستيراد", "<div class='card bad'>تعذر قراءة الملف المرفوع.</div>"),400)
            if p=="/import": count=import_csv(payload); return self.send_html(layout("الاستيراد",f"<div class='card ok'>تم استيراد/تحديث {count} حسابًا.</div>"))
            count,skipped=import_content_csv(payload); return self.send_html(layout("استيراد المحتوى",f"<div class='card ok'>تم استيراد/تحديث {count} منشورًا.</div><div class='card'>تم تجاوز {skipped} صفوف بلا external_id.</div><p><a href='/jordan-ai'>فتح Jordan AI</a> | <a href='/insights'>فتح AI Insights</a></p>"))
        if p=="/reels-ai":
            data=parse_qs(raw.decode(errors="replace")); text=data.get("text",[""])[0].strip()
            from reels_gen import generate_reels_concept
            if not text: return self.reels_ai_page()
            result=generate_reels_concept(text); s=result["script"]; v=result["visual"]
            body=f"<h2>🎬 AI Reels</h2><div class='card'><h3>الموضوع: {esc(result['topic'])}</h3><p>{esc(v['angle'])}</p><p>{esc(v['details'])}</p></div><div class='card'><h3>السيناريو</h3><p>1. {esc(s['scene_1'])}</p><p>2. {esc(s['scene_2'])}</p><p>3. {esc(s['scene_3'])}</p><p>الصوت: {esc(s['audio'])}</p></div><div class='card small'>{esc(result['note'])}</div>"
            return self.send_html(layout("AI Reels",body))
        return self.redir("/")

class Server(ThreadingHTTPServer):
    allow_reuse_address=True
    daemon_threads=True

if __name__=="__main__":
    init_db(); STOP.clear(); worker_thread=threading.Thread(target=worker,daemon=True); worker_thread.start(); server=Server((HOST,PORT),H); print(f"Open http://{HOST}:{PORT}")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: STOP.set(); server.server_close()
