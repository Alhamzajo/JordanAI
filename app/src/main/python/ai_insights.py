# -*- coding: utf-8 -*-
"""Human-readable insights generated from observed content metrics."""
from collections import defaultdict
from analytics_core import DB, confidence_for_count, mean, parse_datetime
from ai_engine import load_posts


def generate_insights(db_path=DB, jordan_only=False):
    rows = load_posts(db_path, jordan_only)
    if not rows:
        return ["لا توجد بيانات كافية للتحليل."]
    insights = [f"تم تحليل {len(rows):,} منشورًا ضمن النطاق المحدد."]
    by_type = defaultdict(list); by_hour = defaultdict(list)
    for r in rows:
        from analytics_core import metrics
        m = metrics(r); by_type[r["content_type"] or "unknown"].append(m)
        dt = parse_datetime(r["published_at"])
        if dt: by_hour[dt.hour].append(m)
    if by_type:
        reach = {k: mean(x["reach"] for x in v) for k,v in by_type.items()}
        er = {k: mean(x["engagement_rate"] for x in v) for k,v in by_type.items()}
        shares = {k: mean(x["share_rate"] for x in v) for k,v in by_type.items()}
        best_r = max(reach, key=reach.get); best_e = max(er, key=er.get); best_s = max(shares, key=shares.get)
        insights.append(f"أعلى متوسط وصول في العينة: {best_r} ({reach[best_r]:.2f}).")
        insights.append(f"أعلى متوسط معدل تفاعل: {best_e} ({er[best_e]:.2f}%).")
        insights.append(f"أعلى متوسط معدل مشاركة: {best_s} ({shares[best_s]:.2f}%).")
    if by_hour:
        hour_er = {h: mean(x["engagement_rate"] for x in v) for h,v in by_hour.items()}
        h = max(hour_er, key=hour_er.get)
        insights.append(f"أعلى معدل تفاعل متوسط في العينة ظهر عند {h:02d}:00 ({hour_er[h]:.2f}%).")
    confidence = confidence_for_count(len(rows))
    insights.append(f"الثقة: {confidence['label']} — {confidence['reason']}")
    insights.append("هذه استنتاجات وصفية من البيانات المرصودة، وليست ضمانًا للانتشار أو قياسًا مباشرًا لخوارزمية المنصة.")
    return insights


def build_insights(db_path=DB, jordan_only=False):
    return {"status": "ok", "insights": generate_insights(db_path, jordan_only), "confidence": confidence_for_count(len(load_posts(db_path, jordan_only)))}


if __name__ == "__main__":
    print("\n".join("- " + x for x in generate_insights()))
