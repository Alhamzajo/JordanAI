# -*- coding: utf-8 -*-
"""Local creative assistant. It generates concepts from text; it does not call an external LLM."""
import re

TOPICS={
    "قهوة":{"keywords":["قهوة","فنجان","كافيه","إسبريسو","اسبرسو"],"angle":"لقطات قريبة للبخار والتفاصيل مع حركة بطيئة.","hook":"ابدأ بأقوى لقطة خلال أول 2-3 ثوانٍ."},
    "عمان":{"keywords":["عمان","عمّان","وسط البلد","البلد"],"angle":"حركة بان أو تتبع في شارع/معلم مع طبقات صوتية محلية.","hook":"ابدأ بتفصيل بصري مألوف للأردني ثم اكشف المكان."},
    "جمعة":{"keywords":["جمعة","مباركة","دعاء","صلاة"],"angle":"لقطات هادئة للمدينة والسماء والضوء مع إيقاع متزن.","hook":"افتتاحية هادئة ثم رسالة قصيرة وواضحة."},
    "الأردن":{"keywords":["الأردن","الاردن","Jordan","الأردنية","اردني"],"angle":"لقطات محلية مرتبطة بالمكان والهوية دون مبالغة دعائية.","hook":"ابدأ بعنصر أردني واضح قبل النص التفسيري."},
}

def generate_reels_concept(post_text):
    text=str(post_text or '').strip(); selected=None
    for topic,data in TOPICS.items():
        if any(k in text for k in data['keywords']): selected=(topic,data); break
    if selected is None:
        selected=("عام",{"angle":"لقطة افتتاحية واضحة ثم تفاصيل متتابعة مرتبطة مباشرة بالنص.","hook":"ابدأ بالمعلومة أو الصورة الأكثر إثارة للاهتمام."})
    topic,data=selected
    return {
        "topic":topic,
        "visual":{"angle":data['angle'],"details":f"تصميم بصري مبني على النص: {text[:120]}"},
        "script":{"scene_1":data['hook'],"scene_2":"3-7 ثوانٍ: عرض المعلومة الرئيسية بصريًا.","scene_3":"7-12 ثانية: خلاصة قصيرة أو سؤال للتفاعل.","audio":"اختيار صوت مناسب لحقوق الاستخدام والمنصة."},
        "note":"هذه مسودة إبداعية محلية وليست تنبؤًا بأداء الريلز."
    }

if __name__=='__main__': print(generate_reels_concept('عمّان في المساء'))
