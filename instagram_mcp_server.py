"""
Instagram Growth Analytics MCP Server
For: kristinatubera / Femme Finance Official
Connects Claude to Instagram Graph API for deep growth analytics
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ─── CONFIG ───────────────────────────────────────────────────────────────────
ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN_HERE")
IG_USER_ID   = os.environ.get("INSTAGRAM_USER_ID", "YOUR_IG_USER_ID_HERE")
BASE_URL     = "https://graph.instagram.com/v21.0"

app = Server("instagram-growth-mcp")

# ─── HELPER ───────────────────────────────────────────────────────────────────
async def ig_get(endpoint: str, params: dict = {}) -> dict:
    params["access_token"] = ACCESS_TOKEN
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}{endpoint}", params=params)
        r.raise_for_status()
        return r.json()

def fmt(data: Any) -> str:
    return json.dumps(data, indent=2)

# ─── TOOLS ────────────────────────────────────────────────────────────────────
@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_account_overview",
            description="Get your Instagram profile stats: followers, following, bio, media count.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        types.Tool(
            name="get_follower_growth",
            description="Track follower count and growth trend over the last N days.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Number of days to look back (default 30)", "default": 30}
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_top_posts",
            description="Get your top performing posts ranked by a metric: likes, comments, shares, saves, reach, impressions, or engagement_rate.",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": ["likes", "comments", "shares", "saves", "reach", "impressions", "engagement_rate"],
                        "description": "Metric to rank by",
                        "default": "engagement_rate"
                    },
                    "limit": {"type": "integer", "description": "Number of posts to return (default 10)", "default": 10}
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_post_breakdown_by_type",
            description="Compare performance across content types: IMAGE, VIDEO (Reels), CAROUSEL_ALBUM. Shows avg likes, comments, shares, saves, reach per type.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        types.Tool(
            name="get_best_posting_times",
            description="Analyze which days of the week and hours your posts get the most engagement.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        types.Tool(
            name="get_audience_insights",
            description="Get audience demographics: top countries, cities, age groups, gender split.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        types.Tool(
            name="get_reach_and_impressions",
            description="Get account-level reach and impressions over the last N days.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Days to look back (default 30)", "default": 30}
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_post_detail",
            description="Get full metrics for a single post by its ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {"type": "string", "description": "Instagram media ID"}
                },
                "required": ["post_id"]
            }
        ),
        types.Tool(
            name="get_hashtag_performance",
            description="Analyze which hashtags appear most in your top-performing posts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "top_n": {"type": "integer", "description": "Number of top posts to analyze (default 20)", "default": 20}
                },
                "required": []
            }
        ),
        types.Tool(
            name="get_growth_recommendations",
            description="AI-powered growth analysis: pull all key metrics and return ranked recommendations for growing followers and engagement.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        types.Tool(
            name="get_reel_performance",
            description="Get performance metrics specifically for Reels: plays, reach, likes, comments, shares, saves.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        types.Tool(
            name="get_saves_analysis",
            description="Analyze saves across your posts — saves indicate high-value content people want to return to.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
    ]


# ─── TOOL HANDLERS ────────────────────────────────────────────────────────────
@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    # 1. ACCOUNT OVERVIEW
    if name == "get_account_overview":
        data = await ig_get(f"/{IG_USER_ID}", params={
            "fields": "id,username,name,biography,followers_count,follows_count,media_count,profile_picture_url,website"
        })
        return [types.TextContent(type="text", text=fmt(data))]

    # 2. FOLLOWER GROWTH
    elif name == "get_follower_growth":
        days = arguments.get("days", 30)
        since = int((datetime.now() - timedelta(days=days)).timestamp())
        until = int(datetime.now().timestamp())
        data = await ig_get(f"/{IG_USER_ID}/insights", params={
            "metric": "follower_count",
            "period": "day",
            "since": since,
            "until": until
        })
        values = data.get("data", [{}])[0].get("values", [])
        if values:
            start = values[0]["value"]
            end = values[-1]["value"]
            growth = end - start
            pct = round((growth / start * 100), 2) if start else 0
            summary = {
                "period": f"Last {days} days",
                "start_followers": start,
                "end_followers": end,
                "net_growth": growth,
                "growth_percent": f"{pct}%",
                "daily_data": values
            }
        else:
            summary = {"error": "No follower data returned", "raw": data}
        return [types.TextContent(type="text", text=fmt(summary))]

    # 3. TOP POSTS
    elif name == "get_top_posts":
        metric = arguments.get("metric", "engagement_rate")
        limit = arguments.get("limit", 10)
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
            p["engagement_rate"] = round(((likes + comments + shares + saves) / reach) * 100, 2)
            p["likes"] = likes
            p["comments"] = comments
            p["shares"] = shares
            p["saves"] = saves
        sort_key = metric if metric != "engagement_rate" else "engagement_rate"
        sorted_posts = sorted(posts, key=lambda x: x.get(sort_key, 0), reverse=True)[:limit]
        return [types.TextContent(type="text", text=fmt(sorted_posts))]

    # 4. BREAKDOWN BY CONTENT TYPE
    elif name == "get_post_breakdown_by_type":
        media = await ig_get(f"/{IG_USER_ID}/media", params={
            "fields": "id,media_type,like_count,comments_count,shares_count,saved,reach,impressions",
            "limit": 100
        })
        posts = media.get("data", [])
        breakdown = {}
        for p in posts:
            t = p.get("media_type", "UNKNOWN")
            if t not in breakdown:
                breakdown[t] = {"count": 0, "likes": 0, "comments": 0, "shares": 0, "saves": 0, "reach": 0, "impressions": 0}
            breakdown[t]["count"] += 1
            breakdown[t]["likes"] += p.get("like_count", 0) or 0
            breakdown[t]["comments"] += p.get("comments_count", 0) or 0
            breakdown[t]["shares"] += p.get("shares_count", 0) or 0
            breakdown[t]["saves"] += p.get("saved", 0) or 0
            breakdown[t]["reach"] += p.get("reach", 0) or 0
            breakdown[t]["impressions"] += p.get("impressions", 0) or 0
        for t, v in breakdown.items():
            n = v["count"] or 1
            v["avg_likes"] = round(v["likes"] / n, 1)
            v["avg_comments"] = round(v["comments"] / n, 1)
            v["avg_shares"] = round(v["shares"] / n, 1)
            v["avg_saves"] = round(v["saves"] / n, 1)
            v["avg_reach"] = round(v["reach"] / n, 1)
            v["avg_engagement_rate"] = round(
                ((v["likes"] + v["comments"] + v["shares"] + v["saves"]) / max(v["reach"], 1)) * 100, 2
            )
        return [types.TextContent(type="text", text=fmt(breakdown))]

    # 5. BEST POSTING TIMES
    elif name == "get_best_posting_times":
        media = await ig_get(f"/{IG_USER_ID}/media", params={
            "fields": "id,timestamp,like_count,comments_count,shares_count,saved,reach",
            "limit": 100
        })
        posts = media.get("data", [])
        by_day = {}
        by_hour = {}
        days_map = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for p in posts:
            ts = datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00"))
            day = days_map[ts.weekday()]
            hour = ts.hour
            engagement = (p.get("like_count", 0) or 0) + (p.get("comments_count", 0) or 0) + \
                         (p.get("shares_count", 0) or 0) + (p.get("saved", 0) or 0)
            if day not in by_day:
                by_day[day] = {"posts": 0, "total_engagement": 0}
            by_day[day]["posts"] += 1
            by_day[day]["total_engagement"] += engagement
            if hour not in by_hour:
                by_hour[hour] = {"posts": 0, "total_engagement": 0}
            by_hour[hour]["posts"] += 1
            by_hour[hour]["total_engagement"] += engagement
        for d in by_day.values():
            d["avg_engagement"] = round(d["total_engagement"] / max(d["posts"], 1), 1)
        for h in by_hour.values():
            h["avg_engagement"] = round(h["total_engagement"] / max(h["posts"], 1), 1)
        best_day = max(by_day, key=lambda x: by_day[x]["avg_engagement"]) if by_day else "N/A"
        best_hour = max(by_hour, key=lambda x: by_hour[x]["avg_engagement"]) if by_hour else "N/A"
        result = {
            "best_day_to_post": best_day,
            "best_hour_to_post": f"{best_hour}:00",
            "by_day": dict(sorted(by_day.items())),
            "by_hour": {f"{k}:00": v for k, v in sorted(by_hour.items())}
        }
        return [types.TextContent(type="text", text=fmt(result))]

    # 6. AUDIENCE INSIGHTS
    elif name == "get_audience_insights":
        results = {}
        for metric in ["audience_country", "audience_city", "audience_gender_age"]:
            try:
                data = await ig_get(f"/{IG_USER_ID}/insights", params={
                    "metric": metric,
                    "period": "lifetime"
                })
                results[metric] = data.get("data", [{}])[0].get("values", [{}])[0].get("value", {})
            except Exception as e:
                results[metric] = {"error": str(e)}
        return [types.TextContent(type="text", text=fmt(results))]

    # 7. REACH & IMPRESSIONS
    elif name == "get_reach_and_impressions":
        days = arguments.get("days", 30)
        since = int((datetime.now() - timedelta(days=days)).timestamp())
        until = int(datetime.now().timestamp())
        results = {}
        for metric in ["reach", "impressions", "profile_views"]:
            try:
                data = await ig_get(f"/{IG_USER_ID}/insights", params={
                    "metric": metric,
                    "period": "day",
                    "since": since,
                    "until": until
                })
                values = data.get("data", [{}])[0].get("values", [])
                total = sum(v["value"] for v in values)
                results[metric] = {"total": total, "daily": values}
            except Exception as e:
                results[metric] = {"error": str(e)}
        return [types.TextContent(type="text", text=fmt(results))]

    # 8. SINGLE POST DETAIL
    elif name == "get_post_detail":
        post_id = arguments["post_id"]
        data = await ig_get(f"/{post_id}", params={
            "fields": "id,caption,media_type,timestamp,like_count,comments_count,shares_count,saved,reach,impressions,permalink,media_url"
        })
        return [types.TextContent(type="text", text=fmt(data))]

    # 9. HASHTAG PERFORMANCE
    elif name == "get_hashtag_performance":
        top_n = arguments.get("top_n", 20)
        media = await ig_get(f"/{IG_USER_ID}/media", params={
            "fields": "id,caption,like_count,comments_count,shares_count,saved,reach",
            "limit": top_n
        })
        posts = media.get("data", [])
        hashtag_scores = {}
        for p in posts:
            caption = p.get("caption", "") or ""
            tags = [w for w in caption.split() if w.startswith("#")]
            engagement = (p.get("like_count", 0) or 0) + (p.get("comments_count", 0) or 0) + \
                         (p.get("shares_count", 0) or 0) + (p.get("saved", 0) or 0)
            for tag in tags:
                tag = tag.lower().strip("#.,!")
                if tag not in hashtag_scores:
                    hashtag_scores[tag] = {"appearances": 0, "total_engagement": 0}
                hashtag_scores[tag]["appearances"] += 1
                hashtag_scores[tag]["total_engagement"] += engagement
        for tag in hashtag_scores:
            n = hashtag_scores[tag]["appearances"]
            hashtag_scores[tag]["avg_engagement"] = round(hashtag_scores[tag]["total_engagement"] / n, 1)
        sorted_tags = dict(sorted(hashtag_scores.items(), key=lambda x: x[1]["avg_engagement"], reverse=True))
        return [types.TextContent(type="text", text=fmt(sorted_tags))]

    # 10. GROWTH RECOMMENDATIONS
    elif name == "get_growth_recommendations":
        # Pull all key data points
        media = await ig_get(f"/{IG_USER_ID}/media", params={
            "fields": "id,media_type,timestamp,like_count,comments_count,shares_count,saved,reach,impressions,caption",
            "limit": 50
        })
        posts = media.get("data", [])
        profile = await ig_get(f"/{IG_USER_ID}", params={
            "fields": "followers_count,media_count"
        })
        # Compute type breakdown
        type_stats = {}
        for p in posts:
            t = p.get("media_type", "UNKNOWN")
            if t not in type_stats:
                type_stats[t] = {"count": 0, "eng": 0, "saves": 0, "shares": 0}
            eng = (p.get("like_count", 0) or 0) + (p.get("comments_count", 0) or 0) + \
                  (p.get("shares_count", 0) or 0) + (p.get("saved", 0) or 0)
            type_stats[t]["count"] += 1
            type_stats[t]["eng"] += eng
            type_stats[t]["saves"] += p.get("saved", 0) or 0
            type_stats[t]["shares"] += p.get("shares_count", 0) or 0
        for t in type_stats:
            n = type_stats[t]["count"] or 1
            type_stats[t]["avg_eng"] = round(type_stats[t]["eng"] / n, 1)
            type_stats[t]["avg_saves"] = round(type_stats[t]["saves"] / n, 1)
            type_stats[t]["avg_shares"] = round(type_stats[t]["shares"] / n, 1)
        best_type = max(type_stats, key=lambda x: type_stats[x]["avg_eng"]) if type_stats else "N/A"
        # Best day
        by_day = {}
        days_map = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for p in posts:
            ts = datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00"))
            day = days_map[ts.weekday()]
            eng = (p.get("like_count", 0) or 0) + (p.get("comments_count", 0) or 0)
            if day not in by_day:
                by_day[day] = {"posts": 0, "eng": 0}
            by_day[day]["posts"] += 1
            by_day[day]["eng"] += eng
        best_day = max(by_day, key=lambda x: by_day[x]["eng"] / max(by_day[x]["posts"], 1)) if by_day else "N/A"
        # Top hashtags
        hashtag_scores = {}
        for p in posts:
            caption = p.get("caption", "") or ""
            tags = [w.lower().strip("#.,!") for w in caption.split() if w.startswith("#")]
            eng = (p.get("like_count", 0) or 0) + (p.get("comments_count", 0) or 0)
            for tag in tags:
                if tag not in hashtag_scores:
                    hashtag_scores[tag] = {"count": 0, "eng": 0}
                hashtag_scores[tag]["count"] += 1
                hashtag_scores[tag]["eng"] += eng
        top_hashtags = sorted(hashtag_scores.items(), key=lambda x: x[1]["eng"] / max(x[1]["count"], 1), reverse=True)[:10]
        report = {
            "account_summary": {
                "followers": profile.get("followers_count"),
                "total_posts_analyzed": len(posts)
            },
            "content_type_performance": type_stats,
            "top_recommendation_1_content_type": f"Post more {best_type} — it drives the highest average engagement",
            "top_recommendation_2_posting_day": f"Post on {best_day} for best organic reach",
            "top_recommendation_3_hashtags": [tag for tag, _ in top_hashtags],
            "saves_leaders": sorted(posts, key=lambda x: x.get("saved", 0) or 0, reverse=True)[:3],
            "shares_leaders": sorted(posts, key=lambda x: x.get("shares_count", 0) or 0, reverse=True)[:3],
            "raw_type_breakdown": type_stats
        }
        return [types.TextContent(type="text", text=fmt(report))]

    # 11. REEL PERFORMANCE
    elif name == "get_reel_performance":
        media = await ig_get(f"/{IG_USER_ID}/media", params={
            "fields": "id,media_type,timestamp,like_count,comments_count,shares_count,saved,reach,impressions,permalink,caption",
            "limit": 100
        })
        reels = [p for p in media.get("data", []) if p.get("media_type") == "VIDEO"]
        for r in reels:
            likes = r.get("like_count", 0) or 0
            comments = r.get("comments_count", 0) or 0
            shares = r.get("shares_count", 0) or 0
            saves = r.get("saved", 0) or 0
            reach = r.get("reach", 1) or 1
            r["engagement_rate"] = round(((likes + comments + shares + saves) / reach) * 100, 2)
        reels_sorted = sorted(reels, key=lambda x: x.get("engagement_rate", 0), reverse=True)
        summary = {
            "total_reels": len(reels),
            "avg_engagement_rate": round(sum(r["engagement_rate"] for r in reels) / max(len(reels), 1), 2),
            "avg_likes": round(sum(r.get("like_count", 0) or 0 for r in reels) / max(len(reels), 1), 1),
            "avg_shares": round(sum(r.get("shares_count", 0) or 0 for r in reels) / max(len(reels), 1), 1),
            "avg_saves": round(sum(r.get("saved", 0) or 0 for r in reels) / max(len(reels), 1), 1),
            "top_reels": reels_sorted[:5]
        }
        return [types.TextContent(type="text", text=fmt(summary))]

    # 12. SAVES ANALYSIS
    elif name == "get_saves_analysis":
        media = await ig_get(f"/{IG_USER_ID}/media", params={
            "fields": "id,caption,media_type,timestamp,saved,like_count,reach,permalink",
            "limit": 100
        })
        posts = media.get("data", [])
        for p in posts:
            saves = p.get("saved", 0) or 0
            reach = p.get("reach", 1) or 1
            p["save_rate"] = round((saves / reach) * 100, 2)
        sorted_by_saves = sorted(posts, key=lambda x: x.get("saved", 0) or 0, reverse=True)
        total_saves = sum(p.get("saved", 0) or 0 for p in posts)
        summary = {
            "total_saves_across_all_posts": total_saves,
            "avg_saves_per_post": round(total_saves / max(len(posts), 1), 1),
            "top_saved_posts": sorted_by_saves[:10],
            "insight": "High saves = content people find valuable enough to revisit. Great signal for educational/finance content."
        }
        return [types.TextContent(type="text", text=fmt(summary))]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# ─── MAIN ─────────────────────────────────────────────────────────────────────
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())