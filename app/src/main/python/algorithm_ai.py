# -*- coding: utf-8 -*-
"""Observed-signal analysis. It never claims access to a platform's private algorithm."""
from collections import defaultdict
from analytics_core import DB, confidence_for_count, metrics, parse_datetime, mean, pearson
from ai_engine import load_posts


def analyze_algorithm_signals(db_path=DB, jordan_only=False):
    rows = load_posts(db_path, jordan_only)
    if not rows:
        return {"status": "empty", "message": "لا توجد بيانات كافية لاختبار إشارات الأداء."}
    enriched = []
    for r in rows:
        x = dict(r); x.update(metrics(r)); dt = parse_datetime(r["published_at"]); x["hour"] = dt.hour if dt else None
        enriched.append(x)

    by_type = defaultdict(list)
    for x in enriched: by_type[x["content_type"] or "unknown"].append(x)
    type_signals = {}
    for typ, items in by_type.items():
        type_signals[typ] = {
            "posts": len(items), "avg_reach": round(mean(x["reach"] for x in items), 2),
            "avg_engagement_rate": round(mean(x["engagement_rate"] for x in items), 4),
            "avg_share_rate": round(mean(x["share_rate"] for x in items), 4),
            "avg_save_rate": round(mean(x["save_rate"] for x in items), 4),
            "avg_comment_rate": round(mean(x["comment_rate"] for x in items), 4),
            "avg_click_rate": round(mean(x["click_rate"] for x in items), 4),
            "avg_view_rate": round(mean(x["view_rate"] for x in items), 4),
        }

    signals = {
        "shares_vs_engagement": pearson([x["share_rate"] for x in enriched], [x["engagement_rate"] for x in enriched]),
        "saves_vs_engagement": pearson([x["save_rate"] for x in enriched], [x["engagement_rate"] for x in enriched]),
        "views_vs_reach": pearson([x["views"] for x in enriched], [x["reach"] for x in enriched]),
        "impressions_vs_reach": pearson([x["impressions"] for x in enriched], [x["reach"] for x in enriched]),
    }
    hypotheses = []
    if signals["shares_vs_engagement"] is not None and signals["shares_vs_engagement"] >= 0.5:
        hypotheses.append("المشاركات ترتبط إيجابيًا بمعدل التفاعل داخل هذه العينة.")
    if signals["saves_vs_engagement"] is not None and signals["saves_vs_engagement"] >= 0.5:
        hypotheses.append("الحفظ يرتبط إيجابيًا بمعدل التفاعل داخل هذه العينة.")
    if not hypotheses:
        hypotheses.append("لا توجد علاقة قوية كافية في العينة الحالية لبناء فرضية مستقرة.")
    return {
        "status": "ok", "posts": len(enriched), "confidence": confidence_for_count(len(enriched)),
        "type_signals": type_signals, "correlations": signals, "hypotheses": hypotheses,
        "note": "هذه إشارات مستنتجة من الأداء المرصود وليست وصولًا إلى الخوارزمية الداخلية للمنصة. الارتباط لا يثبت السببية.",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(analyze_algorithm_signals(), ensure_ascii=False, indent=2))
