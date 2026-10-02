# -*- coding: utf-8 -*-
"""Core content analytics engine. Deterministic and based only on stored observations."""
import sqlite3
from collections import defaultdict
from analytics_core import DB, confidence_for_count, metrics, parse_datetime, mean, median


def load_posts(db_path=DB, jordan_only=False):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    rows = c.execute("SELECT * FROM content_metrics ORDER BY published_at ASC, id ASC").fetchall()
    c.close()
    if jordan_only:
        from analytics_core import is_jordanian
        rows = [r for r in rows if is_jordanian(r)]
    return rows


def analyze_content(db_path=DB, jordan_only=False):
    rows = load_posts(db_path, jordan_only)
    if not rows:
        return {"status": "empty", "posts": 0, "confidence": confidence_for_count(0), "message": "لا توجد بيانات منشورات كافية للتحليل."}

    enriched = []
    for row in rows:
        item = dict(row)
        item.update(metrics(row))
        dt = parse_datetime(row["published_at"])
        item["hour"] = dt.hour if dt else None
        item["weekday"] = dt.weekday() if dt else None
        enriched.append(item)

    totals = {k: sum(x[k] for x in enriched) for k in ("reach", "impressions", "views", "likes", "comments", "shares", "saves", "followers", "clicks", "interactions")}
    totals["engagement_rate"] = round((totals["interactions"] / totals["reach"] * 100) if totals["reach"] else 0, 4)
    totals["share_rate"] = round((totals["shares"] / totals["reach"] * 100) if totals["reach"] else 0, 4)
    totals["save_rate"] = round((totals["saves"] / totals["reach"] * 100) if totals["reach"] else 0, 4)
    totals["click_rate"] = round((totals["clicks"] / totals["reach"] * 100) if totals["reach"] else 0, 4)

    for item in enriched:
        # داخلي للتحليل فقط، وليس درجة لخوارزمية المنصة.
        item["analysis_score"] = round(item["engagement_rate"] * 0.45 + item["share_rate"] * 0.25 + item["save_rate"] * 0.15 + item["comment_rate"] * 0.15, 4)

    by_type = defaultdict(list)
    by_hour = defaultdict(list)
    for item in enriched:
        by_type[item["content_type"] or "unknown"].append(item)
        if item["hour"] is not None:
            by_hour[item["hour"]].append(item)

    type_stats = {}
    for key, items in by_type.items():
        type_stats[key] = {
            "posts": len(items),
            "avg_reach": round(mean(x["reach"] for x in items), 2),
            "median_reach": round(median(x["reach"] for x in items), 2),
            "avg_views": round(mean(x["views"] for x in items), 2),
            "avg_interactions": round(mean(x["interactions"] for x in items), 2),
            "avg_engagement_rate": round(mean(x["engagement_rate"] for x in items), 4),
            "avg_share_rate": round(mean(x["share_rate"] for x in items), 4),
            "avg_save_rate": round(mean(x["save_rate"] for x in items), 4),
            "avg_click_rate": round(mean(x["click_rate"] for x in items), 4),
            "avg_follower_conversion": round(mean(x["follower_conversion"] for x in items), 4),
        }

    hour_stats = {
        hour: {
            "posts": len(items),
            "avg_reach": round(mean(x["reach"] for x in items), 2),
            "avg_engagement_rate": round(mean(x["engagement_rate"] for x in items), 4),
            "avg_share_rate": round(mean(x["share_rate"] for x in items), 4),
        }
        for hour, items in by_hour.items()
    }

    top_posts = sorted(enriched, key=lambda x: (x["analysis_score"], x["reach"]), reverse=True)[:10]
    for item in top_posts:
        item["content_text"] = (item.get("content_text") or "")[:180]

    return {
        "status": "ok", "posts": len(enriched), "confidence": confidence_for_count(len(enriched)),
        "totals": totals, "type_stats": type_stats, "hour_stats": hour_stats,
        "top_posts": top_posts,
        "scope": "jordan" if jordan_only else "all",
        "note": "النتائج مبنية على البيانات المرصودة في قاعدة البرنامج ولا تمثل وصولًا إلى خوارزمية منصة خاصة."
    }


def analyze():
    data = analyze_content()
    if data["status"] != "ok":
        print(data["message"]); return data
    print("=" * 70)
    print("AI CONTENT ANALYTICS")
    print("=" * 70)
    print(f"المنشورات: {data['posts']:,} | الثقة: {data['confidence']['label']}")
    for key, value in data["totals"].items():
        print(f"{key}: {value}")
    print("\nأفضل المنشورات حسب المؤشر الداخلي:")
    for i, item in enumerate(data["top_posts"], 1):
        print(f"{i}. {item['content_type']} | reach={item['reach']} | ER={item['engagement_rate']}% | score={item['analysis_score']}")
    return data


if __name__ == "__main__":
    analyze()
