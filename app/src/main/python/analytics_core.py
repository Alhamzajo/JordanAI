# -*- coding: utf-8 -*-
"""Shared, deterministic analytics helpers. No private platform data is accessed."""
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone

DB = "manager.db"
INTERACTION_FIELDS = ("likes", "comments", "shares", "saves")
JORDAN_COUNTRY_NAMES = {
    "jordan", "الأردن", "الاردن", "المملكة الأردنية الهاشمية", "المملكه الاردنيه الهاشميه"
}
JORDAN_GOVERNORATES = {
    "عمان", "العاصمة", "الزرقاء", "إربد", "اربد", "البلقاء", "مادبا", "مأدبا",
    "جرش", "عجلون", "المفرق", "الكرك", "الطفيلة", "طفيلة", "معان", "العقبة", "العقبه"
}
JORDAN_CITIES = {
    "عمان", "الزرقاء", "الرصيفة", "اربد", "إربد", "السلط", "مادبا", "مأدبا", "جرش",
    "عجلون", "المفرق", "الكرك", "الطفيلة", "معان", "العقبة", "العقبه", "الرمثا",
    "الفحيص", "البيادر", "صويلح", "ماركا", "وادي السير", "الشونة", "البتراء"
}


def as_int(value):
    try:
        if value is None or value == "":
            return 0
        return max(0, int(float(str(value).strip().replace(",", ""))))
    except (TypeError, ValueError):
        return 0


def parse_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    candidates = [text.replace("Z", "+00:00"), text]
    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def interactions(row):
    return sum(as_int(row[k]) for k in INTERACTION_FIELDS)


def rate(value, denominator):
    return round((value / denominator) * 100, 4) if denominator else 0.0


def metrics(row):
    reach = as_int(row["reach"])
    impressions = as_int(row["impressions"])
    views = as_int(row["views"])
    likes = as_int(row["likes"])
    comments = as_int(row["comments"])
    shares = as_int(row["shares"])
    saves = as_int(row["saves"])
    followers = as_int(row["followers_delta"])
    clicks = as_int(row["link_clicks"])
    inter = likes + comments + shares + saves
    return {
        "reach": reach, "impressions": impressions, "views": views,
        "likes": likes, "comments": comments, "shares": shares, "saves": saves,
        "followers": followers, "clicks": clicks, "interactions": inter,
        "engagement_rate": rate(inter, reach),
        "share_rate": rate(shares, reach),
        "save_rate": rate(saves, reach),
        "comment_rate": rate(comments, reach),
        "click_rate": rate(clicks, reach),
        "view_rate": rate(views, reach),
        "reach_efficiency": rate(reach, impressions),
        "follower_conversion": rate(followers, reach),
    }


def extract_hashtags(text):
    return re.findall(r"#[\w\u0600-\u06FF]+", text or "")


def normalize_text(value):
    return " ".join(str(value or "").strip().lower().split())


def is_jordanian(row):
    country = normalize_text(row["country"])
    governorate = normalize_text(row["governorate"])
    city = normalize_text(row["city"])
    if country in {normalize_text(x) for x in JORDAN_COUNTRY_NAMES}:
        return True
    if governorate in {normalize_text(x) for x in JORDAN_GOVERNORATES}:
        return True
    if city in {normalize_text(x) for x in JORDAN_CITIES}:
        return True
    return False


def confidence_for_count(count):
    if count < 10:
        return {"label": "منخفضة", "level": 1, "reason": "العينة صغيرة."}
    if count < 30:
        return {"label": "متوسطة", "level": 2, "reason": "العينة تسمح بمؤشرات أولية، لكنها قد تتغير مع بيانات إضافية."}
    if count < 100:
        return {"label": "جيدة", "level": 3, "reason": "العينة مناسبة لمقارنات أولية أكثر استقرارًا."}
    return {"label": "مرتفعة نسبيًا", "level": 4, "reason": "حجم العينة كبير نسبيًا، مع بقاء عوامل خارج البيانات مؤثرة."}


def mean(values):
    values = [float(v) for v in values if v is not None]
    return statistics.mean(values) if values else 0.0


def median(values):
    values = [float(v) for v in values if v is not None]
    return statistics.median(values) if values else 0.0


def pearson(xs, ys):
    pairs = [(float(x), float(y)) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    mx, my = mean([x for x, _ in pairs]), mean([y for _, y in pairs])
    num = sum((x - mx) * (y - my) for x, y in pairs)
    den_x = sum((x - mx) ** 2 for x, _ in pairs) ** 0.5
    den_y = sum((y - my) ** 2 for _, y in pairs) ** 0.5
    if not den_x or not den_y:
        return None
    return round(num / (den_x * den_y), 4)
