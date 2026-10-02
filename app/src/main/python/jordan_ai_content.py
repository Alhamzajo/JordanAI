# -*- coding: utf-8 -*-
"""Small deterministic content formatter used only by the optional Flask adapter."""
def generate_ai_content(item):
    title=str(item.get('title') or '').strip()
    return {"summary": title or "لا يوجد عنوان متاح.", "text_post": (title + "\n\nللمزيد راجع المصدر الأصلي.").strip()}
