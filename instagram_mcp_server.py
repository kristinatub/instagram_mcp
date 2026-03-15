"""
Instagram Growth Analytics MCP Server
For: kristinatubera / Femme Finance Official
Uses FastMCP with Streamable HTTP transport (production standard)
"""

import os
from datetime import datetime, timedelta
from typing import Any
import json
import httpx
from mcp.server.fastmcp import FastMCP

ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
IG_USER_ID   = os.environ.get("INSTAGRAM_USER_ID", "")
BASE_URL     = "https://graph.instagram.com/v21.0"

mcp = FastMCP("instagram-growth-mcp", stateless_http=True)

async def ig_get(endpoint: str, params: dict = {}) -> dict:
    p = dict(params)
    p["access_token"] = ACCESS_TOKEN
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}{endpoint}", params=p)
        r.raise_for_status()
        return r.json()

def fmt(data: Any) -> str:
    return json.dumps(data, indent=2)


@mcp.tool()
async def get_account_overview() -> str:
    """Get Instagram profile stats: followers, following, bio, media count."""
    data = await ig_get(f"/{IG_USER_ID}", params={
        "fields": "id,username,name,biography,followers_count,follows_count,media_count,website"
    })
    return fmt(data)


@mcp.tool()
async def get_follower_growth(days: int = 30) -> str:
    """Track follower count and growth trend over the last N days."""
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    until = int(datetime.now().timestamp())
    data = await ig_get(f"/{IG_USER_ID}/insights", params={
        "metric": "follower_count", "period": "day", "since": since, "until": until
    })
    values = data.get("data", [{}])[0].get("values", [])
    if values:
        start, end = values[0]["value"], values[-1]["value"]
        growth = end - start
        return fmt({"period": f"Last {days} days", "start_followers": start, "end_followers": end,
                    "net_growth": growth, "growth_percent": f"{round((growth/start*100),2) if start else 0}%",
                    "daily_data": values})
    return fmt({"error": "No follower data", "raw": data})


@mcp.tool()
async def get_top_posts(metric: str = "engagement_rate", limit: int = 10) -> str:
    """Get top performing posts ranked by: likes, comments, shares, saves, reach, impressions, or engagement_rate."""
    media = await ig_get(f"/{IG_USER_ID}/media", params={
        "fields": "id,caption,media_type,timestamp,like_count,comments_count,shares_count,saved,reach,impressions,permalink",
        "limit": 50
    })
    posts = media.get("data", [])
    for p in posts:
        likes = p.get("like_count", 0) or 0
        comments = p.get("comments_count", 0) or 0
        shares = p.get("shares_count", 0) or 0
        saves = p.get("saved", 0) or 0
        reach = p.get("reach", 1) or 1
        p["engagement_rate"] = round(((likes+comments+shares+saves)/reach)*100, 2)
        p["likes"], p["comments"], p["shares"], p["saves"] = likes, comments, shares, saves
    return fmt(sorted(posts, key=lambda x: x.get(metric, 0), reverse=True)[:limit])


@mcp.tool()
async def get_post_breakdown_by_type() -> str:
    """Compare Reels vs Carousels vs Images: avg likes, comments, shares, saves, reach, engagement rate."""
    media = await ig_get(f"/{IG_USER_ID}/media", params={
        "fields": "id,media_type,like_count,comments_count,shares_count,saved,reach,impressions",
        "limit": 100
    })
    breakdown = {}
    for p in media.get("data", []):
        t = p.get("media_type", "UNKNOWN")
        if t not in breakdown:
            breakdown[t] = {"count":0,"likes":0,"comments":0,"shares":0,"saves":0,"reach":0,"impressions":0}
        breakdown[t]["count"] += 1
        for k, f in [("likes","like_count"),("comments","comments_count"),("shares","shares_count"),
                     ("saves","saved"),("reach","reach"),("impressions","impressions")]:
            breakdown[t][k] += p.get(f, 0) or 0
    for t, v in breakdown.items():
        n = v["count"] or 1
        for k in ["likes","comments","shares","saves","reach"]:
            v[f"avg_{k}"] = round(v[k]/n, 1)
        v["avg_engagement_rate"] = round(
            ((v["likes"]+v["comments"]+v["shares"]+v["saves"])/max(v["reach"],1))*100, 2)
    return fmt(breakdown)


@mcp.tool()
async def get_best_posting_times() -> str:
    """Analyze which days of the week and hours get the most engagement."""
    media = await ig_get(f"/{IG_USER_ID}/media", params={
        "fields": "id,timestamp,like_count,comments_count,shares_count,saved",
        "limit": 100
    })
    by_day, by_hour = {}, {}
    days_map = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    for p in media.get("data", []):
        ts = datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00"))
        day, hour = days_map[ts.weekday()], ts.hour
        eng = sum(p.get(k,0) or 0 for k in ["like_count","comments_count","shares_count","saved"])
        if day not in by_day: by_day[day] = {"posts":0,"total_engagement":0}
        by_day[day]["posts"] += 1; by_day[day]["total_engagement"] += eng
        if hour not in by_hour: by_hour[hour] = {"posts":0,"total_engagement":0}
        by_hour[hour]["posts"] += 1; by_hour[hour]["total_engagement"] += eng
    for d in by_day.values(): d["avg_engagement"] = round(d["total_engagement"]/max(d["posts"],1), 1)
    for h in by_hour.values(): h["avg_engagement"] = round(h["total_engagement"]/max(h["posts"],1), 1)
    best_day = max(by_day, key=lambda x: by_day[x]["avg_engagement"]) if by_day else "N/A"
    best_hour = max(by_hour, key=lambda x: by_hour[x]["avg_engagement"]) if by_hour else "N/A"
    return fmt({"best_day_to_post": best_day, "best_hour_to_post": f"{best_hour}:00 UTC",
                "by_day": dict(sorted(by_day.items())),
                "by_hour": {f"{k}:00": v for k,v in sorted(by_hour.items())}})


@mcp.tool()
async def get_audience_insights() -> str:
    """Get audience demographics: top countries, cities, age groups, gender split."""
    results = {}
    for metric in ["audience_country","audience_city","audience_gender_age"]:
        try:
            data = await ig_get(f"/{IG_USER_ID}/insights", params={"metric": metric, "period": "lifetime"})
            results[metric] = data.get("data",[{}])[0].get("values",[{}])[0].get("value",{})
        except Exception as e:
            results[metric] = {"error": str(e)}
    return fmt(results)


@mcp.tool()
async def get_reach_and_impressions(days: int = 30) -> str:
    """Get account-level reach, impressions and profile views over last N days."""
    since = int((datetime.now() - timedelta(days=days)).timestamp())
    until = int(datetime.now().timestamp())
    results = {}
    for metric in ["reach","impressions","profile_views"]:
        try:
            data = await ig_get(f"/{IG_USER_ID}/insights", params={
                "metric": metric, "period": "day", "since": since, "until": until
            })
            values = data.get("data",[{}])[0].get("values",[])
            results[metric] = {"total": sum(v["value"] for v in values), "daily": values}
        except Exception as e:
            results[metric] = {"error": str(e)}
    return fmt(results)


@mcp.tool()
async def get_post_detail(post_id: str) -> str:
    """Get full metrics for a single post by its ID."""
    data = await ig_get(f"/{post_id}", params={
        "fields": "id,caption,media_type,timestamp,like_count,comments_count,shares_count,saved,reach,impressions,permalink"
    })
    return fmt(data)


@mcp.tool()
async def get_hashtag_performance(top_n: int = 20) -> str:
    """Analyze which hashtags appear most in your top-performing posts."""
    media = await ig_get(f"/{IG_USER_ID}/media", params={
        "fields": "id,caption,like_count,comments_count,shares_count,saved,reach",
        "limit": top_n
    })
    scores = {}
    for p in media.get("data", []):
        caption = p.get("caption", "") or ""
        eng = sum(p.get(k,0) or 0 for k in ["like_count","comments_count","shares_count","saved"])
        for tag in [w.lower().strip("#.,!") for w in caption.split() if w.startswith("#")]:
            if tag not in scores: scores[tag] = {"appearances":0,"total_engagement":0}
            scores[tag]["appearances"] += 1; scores[tag]["total_engagement"] += eng
    for tag in scores:
        scores[tag]["avg_engagement"] = round(scores[tag]["total_engagement"]/scores[tag]["appearances"], 1)
    return fmt(dict(sorted(scores.items(), key=lambda x: x[1]["avg_engagement"], reverse=True)))


@mcp.tool()
async def get_growth_recommendations() -> str:
    """Full growth report: best content type, best posting day, top hashtags, saves and shares leaders."""
    media = await ig_get(f"/{IG_USER_ID}/media", params={
        "fields": "id,media_type,timestamp,like_count,comments_count,shares_count,saved,reach,caption",
        "limit": 50
    })
    posts = media.get("data", [])
    profile = await ig_get(f"/{IG_USER_ID}", params={"fields": "followers_count,media_count"})
    type_stats, by_day, hash_scores = {}, {}, {}
    days_map = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    for p in posts:
        t = p.get("media_type","UNKNOWN")
        if t not in type_stats: type_stats[t] = {"count":0,"eng":0,"saves":0,"shares":0}
        eng = sum(p.get(k,0) or 0 for k in ["like_count","comments_count","shares_count","saved"])
        type_stats[t]["count"]+=1; type_stats[t]["eng"]+=eng
        type_stats[t]["saves"]+=p.get("saved",0) or 0
        type_stats[t]["shares"]+=p.get("shares_count",0) or 0
        day = days_map[datetime.fromisoformat(p["timestamp"].replace("Z","+00:00")).weekday()]
        if day not in by_day: by_day[day] = {"posts":0,"eng":0}
        by_day[day]["posts"]+=1; by_day[day]["eng"]+=eng
        for tag in [w.lower().strip("#.,!") for w in (p.get("caption","") or "").split() if w.startswith("#")]:
            if tag not in hash_scores: hash_scores[tag] = {"count":0,"eng":0}
            hash_scores[tag]["count"]+=1; hash_scores[tag]["eng"]+=eng
    for t in type_stats:
        n = type_stats[t]["count"] or 1
        type_stats[t]["avg_eng"] = round(type_stats[t]["eng"]/n, 1)
        type_stats[t]["avg_saves"] = round(type_stats[t]["saves"]/n, 1)
        type_stats[t]["avg_shares"] = round(type_stats[t]["shares"]/n, 1)
    best_type = max(type_stats, key=lambda x: type_stats[x]["avg_eng"]) if type_stats else "N/A"
    best_day = max(by_day, key=lambda x: by_day[x]["eng"]/max(by_day[x]["posts"],1)) if by_day else "N/A"
    top_tags = sorted(hash_scores.items(), key=lambda x: x[1]["eng"]/max(x[1]["count"],1), reverse=True)[:10]
    return fmt({
        "account_summary": {"followers": profile.get("followers_count"), "posts_analyzed": len(posts)},
        "content_type_performance": type_stats,
        "recommendations": {
            "1_best_content_type": f"Post more {best_type} — highest avg engagement",
            "2_best_day": f"Post on {best_day} for best organic reach",
            "3_top_hashtags": [f"#{t}" for t,_ in top_tags]
        },
        "saves_leaders": sorted(posts, key=lambda x: x.get("saved",0) or 0, reverse=True)[:3],
        "shares_leaders": sorted(posts, key=lambda x: x.get("shares_count",0) or 0, reverse=True)[:3]
    })


@mcp.tool()
async def get_reel_performance() -> str:
    """Reel-specific analytics: engagement rate, avg likes, shares, saves. Top 5 reels."""
    media = await ig_get(f"/{IG_USER_ID}/media", params={
        "fields": "id,media_type,timestamp,like_count,comments_count,shares_count,saved,reach,impressions,permalink,caption",
        "limit": 100
    })
    reels = [p for p in media.get("data",[]) if p.get("media_type")=="VIDEO"]
    for r in reels:
        eng = sum(r.get(k,0) or 0 for k in ["like_count","comments_count","shares_count","saved"])
        r["engagement_rate"] = round((eng/max(r.get("reach",1) or 1,1))*100, 2)
    reels_sorted = sorted(reels, key=lambda x: x.get("engagement_rate",0), reverse=True)
    n = max(len(reels),1)
    return fmt({
        "total_reels": len(reels),
        "avg_engagement_rate": round(sum(r["engagement_rate"] for r in reels)/n, 2),
        "avg_likes": round(sum(r.get("like_count",0) or 0 for r in reels)/n, 1),
        "avg_shares": round(sum(r.get("shares_count",0) or 0 for r in reels)/n, 1),
        "avg_saves": round(sum(r.get("saved",0) or 0 for r in reels)/n, 1),
        "top_reels": reels_sorted[:5]
    })


@mcp.tool()
async def get_saves_analysis() -> str:
    """Save rate across all posts. High saves = high-value content people bookmark."""
    media = await ig_get(f"/{IG_USER_ID}/media", params={
        "fields": "id,caption,media_type,timestamp,saved,like_count,reach,permalink",
        "limit": 100
    })
    posts = media.get("data",[])
    for p in posts:
        p["save_rate"] = round(((p.get("saved",0) or 0)/max(p.get("reach",1) or 1,1))*100, 2)
    posts_sorted = sorted(posts, key=lambda x: x.get("saved",0) or 0, reverse=True)
    total = sum(p.get("saved",0) or 0 for p in posts)
    return fmt({
        "total_saves": total,
        "avg_saves_per_post": round(total/max(len(posts),1), 1),
        "insight": "High saves = content people bookmark. Educational finance carousels typically win here.",
        "top_saved_posts": posts_sorted[:10]
    })


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
