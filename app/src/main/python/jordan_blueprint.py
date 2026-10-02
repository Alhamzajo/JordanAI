# -*- coding: utf-8 -*-
"""Optional compatibility adapter.
The main application uses http.server, so Flask is not required for normal operation."""
try:
    from flask import Blueprint, render_template_string
except ImportError:
    Blueprint=None; render_template_string=None

if Blueprint:
    from jordan_news import fetch_latest_jordan_news
    from jordan_ai_content import generate_ai_content
    jordan_bp=Blueprint('jordan_bp',__name__)
    @jordan_bp.route('/jordan-news')
    def jordan_news_page():
        data=fetch_latest_jordan_news(); items=[]
        for item in data.get('items',[]):
            items.append({"title":item['title'],"link":item['link'],"content":generate_ai_content(item)})
        return render_template_string('<h1>🇯🇴 أخبار الأردن</h1>{% for i in items %}<article><h3>{{i.title}}</h3><p>{{i.content.summary}}</p><pre>{{i.content.text_post}}</pre><a href="{{i.link}}">المصدر</a></article>{% endfor %}',items=items)
else:
    jordan_bp=None
    def jordan_news_page():
        raise RuntimeError("Flask غير مثبت؛ استخدم app.py الرئيسي الذي لا يحتاج Flask.")
