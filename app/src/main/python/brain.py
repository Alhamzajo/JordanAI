#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Jordan AI Brain: local, auditable orchestration over the existing analytics tools.

The brain never fabricates platform-internal algorithm knowledge. It routes a request to
local analyzers and can optionally call an OpenAI-compatible chat endpoint when the user
configures LLM_BASE_URL/LLM_API_KEY/LLM_MODEL in the local environment.
"""
import json, os, sqlite3, urllib.request
from datetime import datetime, timezone


def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

class Brain:
    def __init__(self, db_path="manager.db"):
        self.db_path = db_path

    def _db(self):
        c = sqlite3.connect(self.db_path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=10000")
        return c

    def _counts(self):
        c=self._db()
        out={}
        for t in ("participants","accounts","campaigns","content_metrics","analysis_runs","creative_jobs","brain_memory"):
            try: out[t]=c.execute(f"SELECT COUNT(*) n FROM {t}").fetchone()["n"]
            except sqlite3.Error: out[t]=0
        c.close(); return out

    def _analytics(self):
        from ai_engine import analyze_content
        from ai_insights import generate_insights
        from algorithm_ai import analyze_algorithm_signals
        from jordan_ai import analyze_jordan
        return {
            "content": analyze_content(self.db_path),
            "insights": generate_insights(self.db_path),
            "algorithm": analyze_algorithm_signals(self.db_path),
            "jordan": analyze_jordan(self.db_path),
        }

    def _llm(self, prompt, context):
        base=os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
        key=os.getenv("LLM_API_KEY", "").strip()
        model=os.getenv("LLM_MODEL", "").strip()
        if not (base and key and model): return None
        url=base + ("/chat/completions" if not base.endswith("/chat/completions") else "")
        payload={"model":model,"messages":[
            {"role":"system","content":"أنت Jordan AI Brain داخل نظام تحليلي محلي. استخدم البيانات المعطاة فقط. ميّز بين الحقيقة والفرضية. لا تدّعي معرفة خوارزميات Meta الداخلية ولا تقدّم وعودًا مضمونة للأداء."},
            {"role":"user","content":prompt+"\n\nبيانات النظام:\n"+json.dumps(context,ensure_ascii=False,default=str)[:30000]}
        ],"temperature":0.2}
        req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={"Content-Type":"application/json","Authorization":"Bearer "+key},method="POST")
        try:
            with urllib.request.urlopen(req,timeout=45) as r:
                data=json.loads(r.read().decode("utf-8",errors="replace"))
            return (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip() or None
        except Exception:
            return None

    def route(self, prompt):
        p=(prompt or "").strip()
        low=p.lower()
        if not p: return {"ok":False,"message":"اكتب طلبًا للدماغ."}
        tools=[]
        if any(x in p for x in ("فيسبوك","ميتا","facebook","meta")): tools.append("facebook")
        if any(x in p for x in ("خوارزم","algorithm","تفاعل","engagement","وصول","reach")): tools.append("algorithm")
        if any(x in p for x in ("أردن","اردن","محافظ","هاشتاغ","هاشتاج","jordan")): tools.append("jordan")
        if any(x in p for x in ("محتوى","منشور","بوست","content","post")): tools.append("content")
        if any(x in p for x in ("صورة","فيديو","موسيقى","ريلز","creative","image","video","music")): tools.append("creative")
        if not tools: tools=["overview"]
        return {"ok":True,"tools":list(dict.fromkeys(tools))}

    def ask(self,prompt,save=True):
        plan=self.route(prompt); counts=self._counts(); context={"counts":counts,"plan":plan}
        try:
            data=self._analytics()
            context["analytics"]={k:data[k] for k in ("content","insights","algorithm","jordan") if k in data}
        except Exception as exc:
            context["analytics_error"]=str(exc)
        answer=self._llm(prompt,context)
        if not answer:
            answer=self._local_answer(prompt,plan,context)
        result={"ok":True,"answer":answer,"plan":plan,"counts":counts,"generated_at":now(),"llm_used":bool(self._llm_enabled())}
        if save: self.remember(prompt,answer,plan)
        return result

    def _llm_enabled(self):
        return bool(os.getenv("LLM_BASE_URL") and os.getenv("LLM_API_KEY") and os.getenv("LLM_MODEL"))

    def _local_answer(self,prompt,plan,ctx):
        c=ctx["counts"]; lines=["🧠 Jordan AI Brain يعمل الآن بطبقة محلية قابلة للتدقيق."]
        lines.append(f"البيانات المتاحة: {c['content_metrics']:,} منشورًا، {c['accounts']:,} حساب، {c['analysis_runs']:,} تشغيل تحليلي.")
        if "creative" in plan["tools"]:
            lines.append("أستطيع تحويل الفكرة إلى مخطط نص/صورة/فيديو/موسيقى، ثم حفظها كوظيفة Creative Job. التوليد الخارجي الفعلي يحتاج مزودًا مهيأً.")
        if "facebook" in plan["tools"]:
            lines.append("اتصال Meta الحالي منفصل عن الدماغ: يجلب البيانات للقاعدة، ثم يستخدمها الدماغ للتحليل. لا توجد عمليات نشر أو إعجاب أو تعليق.")
        if "algorithm" in plan["tools"]:
            lines.append("تحليل الخوارزمية هنا استدلال من بياناتك (ارتباطات وأنماط)، وليس وصولًا إلى الخوارزمية الداخلية السرية للمنصة.")
        if "jordan" in plan["tools"]:
            lines.append("يمكنني تضييق التحليل إلى الأردن والمحافظات والمدن والهاشتاغات عندما تحتوي البيانات على أدلة جغرافية صريحة.")
        if plan["tools"]==["overview"]:
            lines.append("الأدوات المتاحة: Content AI، Algorithm AI، Jordan AI، AI Insights، Facebook/Meta، وCreative Studio.")
        return "\n".join(lines)

    def remember(self,prompt,answer,plan):
        c=self._db()
        c.execute("INSERT INTO brain_memory(kind,input_text,output_text,plan_json,created_at) VALUES(?,?,?,?,?)",("conversation",prompt,answer,json.dumps(plan,ensure_ascii=False),now()))
        c.execute("INSERT INTO brain_runs(input_text,plan_json,result_json,created_at) VALUES(?,?,?,?)",(prompt,json.dumps(plan,ensure_ascii=False),json.dumps({"answer":answer},ensure_ascii=False),now()))
        c.commit(); c.close()
