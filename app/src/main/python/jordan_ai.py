# -*- coding: utf-8 -*-
"""Jordan-focused analytics. Jordan scope requires explicit Jordan geography/country evidence."""
from collections import Counter, defaultdict
from analytics_core import DB, confidence_for_count, extract_hashtags, is_jordanian, metrics, mean
from ai_engine import load_posts


def analyze_jordan(db_path=DB):
    all_rows = load_posts(db_path, False)
    rows = [r for r in all_rows if is_jordanian(r)]
    if not rows:
        return {
            "status": "empty", "posts": 0,
            "message": "لا توجد منشورات أردنية كافية. أضف country=Jordan أو محافظة/مدينة أردنية واضحة في بيانات المنشورات.",
            "total_rows": len(all_rows), "confidence": confidence_for_count(0)
        }

    hashtags = Counter(); hashtag_rates = defaultdict(list); topics = defaultdict(list); governorates = defaultdict(list); cities = defaultdict(list)
    for r in rows:
        m = metrics(r)
        tags = extract_hashtags((r["hashtags"] or "") + " " + (r["content_text"] or ""))
        for tag in tags:
            key = tag.lower(); hashtags[key] += 1; hashtag_rates[key].append(m["engagement_rate"])
        if r["topic"]: topics[r["topic"]].append(m["engagement_rate"])
        if r["governorate"]: governorates[r["governorate"]].append(m["engagement_rate"])
        if r["city"]: cities[r["city"]].append(m["engagement_rate"])

    return {
        "status": "ok", "posts": len(rows), "total_rows": len(all_rows), "confidence": confidence_for_count(len(rows)),
        "top_hashtags": hashtags.most_common(20),
        "hashtag_engagement": sorted(((k, round(mean(v), 4), len(v)) for k,v in hashtag_rates.items()), key=lambda x:x[1], reverse=True)[:20],
        "topics": sorted(((k, round(mean(v), 4), len(v)) for k,v in topics.items()), key=lambda x:x[1], reverse=True),
        "governorates": sorted(((k, round(mean(v), 4), len(v)) for k,v in governorates.items()), key=lambda x:x[1], reverse=True),
        "cities": sorted(((k, round(mean(v), 4), len(v)) for k,v in cities.items()), key=lambda x:x[1], reverse=True),
        "note": "النطاق الأردني يعتمد على دليل جغرافي/بلدي صريح، وليس على تخمين من المحتوى وحده."
    }


if __name__ == "__main__":
    print(analyze_jordan())
