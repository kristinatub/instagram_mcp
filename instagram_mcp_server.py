"""
Instagram Growth Analytics MCP Server
For: kristinatubera / Femme Finance Official
Simple HTTP JSON-RPC - no SSE transport library needed
"""

import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Any
import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

ACCESS_TOKEN = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
IG_USER_ID   = os.environ.get("INSTAGRAM_USER_ID", "")
BASE_URL     = "https://graph.instagram.com/v21.0"

async def ig_get(endpoint: str, params: dict = {}) -> dict:
    p = dict(params)
    p["access_token"] = ACCESS_TOKEN
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}{endpoint}", params=p)
        r.raise_for_status()
        return r.json()

def fmt(data: Any) -> str:
    return json.dumps(data, indent=2)

TOOLS = [
    {"name": "get_account_overview", "description": "Get Instagram profile stats: followers, following, bio, media count.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_follower_growth", "description": "Track follower growth over last N days.", "inputSchema": {"type": "object", "properties": {"days": {"type": "integer", "default": 30}}}},
    {"name": "get_top_posts", "description": "Top posts ranked by: likes, comments, shares, saves, reach, impressions, engagement_rate.", "inputSchema": {"type": "object", "properties": {"metric": {"type": "string", "default": "engagement_rate"}, "limit": {"type": "integer", "default": 10}}}},
    {"name": "get_post_breakdown_by_type", "description": "Compare Reels vs Carousels vs Images performance.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_best_posting_times", "description": "Best days and hours to post based on engagement.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_audience_insights", "description": "Audience demographics: countries, cities, age, gender.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_reach_and_impressions", "description": "Account-level reach and impressions over last N days.", "inputSchema": {"type": "object", "properties": {"days": {"type": "integer", "default": 30}}}},
    {"name": "get_post_detail", "description": "Full metrics for a single post by ID.", "inputSchema": {"type": "object", "properties": {"post_id": {"type": "string"}}, "required": ["post_id"]}},
    {"name": "get_hashtag_performance", "description": "Which hashtags appear in your top performing posts.", "inputSchema": {"type": "object", "properties": {"top_n": {"type": "integer", "default": 20}}}},
    {"name": "get_growth_recommendations", "description": "Full growth report: best content type, best day, top hashtags, saves and shares leaders.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_reel_performance", "description": "Reel-specific analytics: engagement rate, likes, shares, saves.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_saves_analysis", "description": "Save rate across all posts - saves signal high-value content.", "inputSchema": {"type": "object", "properties": {}}},
]

async def execute_tool(name: str, args: dict) -> str:
    if name == "get_account_overview":
        data = await ig_get(f"/{IG_USER_ID}", params={"fields": "id,username,name,biography,followers_count,follows_count,media_count,website"})
        return fmt(data)

    if name == "get_follower_growth":
        days = args.get("days", 30)
        since = int((datetime.now() - timedelta(days=days)).timestamp())
        until = int(datetime.now().timestamp())
        data = await ig_get(f"/{IG_USER_ID}/insights", params={"metric": "follower_count", "period": "day", "since": since, "until": until})
        values = data.get("data", [{}])[0].get("values", [])
        if values:
            start, end = values[0]["value"], values[-1]["value"]
            growth = end - start
            return fmt({"period": f"Last {days} days", "start_followers": start, "end_followers": end, "net_growth": growth, "growth_percent": f"{round((growth/start*100),2) if start else 0}%", "daily_data": values})
        return fmt({"error": "No follower data", "raw": data})

    if name == "get_top_posts":
        metric = args.get("metric", "engagement_rate")
        limit = args.get("limit", 10)
        media = await ig_get(f"/{IG_USER_ID}/media", params={"fields": "id,caption,media_type,timestamp,like_count,comments_count,shares_count,saved,reach,impressions,permalink", "limit": 50})
        posts = media.get("data", [])
        for p in posts:
            likes, comments = p.get("like_count", 0) or 0, p.get("comments_count", 0) or 0
            shares, saves, reach = p.get("shares_count", 0) or 0, p.get("saved", 0) or 0, p.get("reach", 1) or 1
            p["engagement_rate"] = round(((likes+comments+shares+saves)/reach)*100, 2)
            p["likes"], p["comments"], p["shares"], p["saves"] = likes, comments, shares, saves
        return fmt(sorted(posts, key=lambda x: x.get(metric, 0), reverse=True)[:limit])

    if name == "get_post_breakdown_by_type":
        media = await ig_get(f"/{IG_USER_ID}/media", params={"fields": "id,media_type,like_count,comments_count,shares_count,saved,reach,impressions", "limit": 100})
        breakdown = {}
        for p in media.get("data", []):
            t = p.get("media_type", "UNKNOWN")
            if t not in breakdown:
                breakdown[t] = {"count":0,"likes":0,"comments":0,"shares":0,"saves":0,"reach":0,"impressions":0}
            breakdown[t]["count"] += 1
            for k,f in [("likes","like_count"),("comments","comments_count"),("shares","shares_count"),("saves","saved"),("reach","reach"),("impressions","impressions")]:
                breakdown[t][k] += p.get(f, 0) or 0
        for t, v in breakdown.items():
            n = v["count"] or 1
            for k in ["likes","comments","shares","saves","reach"]:
                v[f"avg_{k}"] = round(v[k]/n, 1)
            v["avg_engagement_rate"] = round(((v["likes"]+v["comments"]+v["shares"]+v["saves"])/max(v["reach"],1))*100, 2)
        return fmt(breakdown)

    if name == "get_best_posting_times":
        media = await ig_get(f"/{IG_USER_ID}/media", params={"fields": "id,timestamp,like_count,comments_count,shares_count,saved", "limit": 100})
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
        return fmt({"best_day_to_post": best_day, "best_hour_to_post": f"{best_hour}:00 UTC", "by_day": dict(sorted(by_day.items())), "by_hour": {f"{k}:00": v for k,v in sorted(by_hour.items())}})

    if name == "get_audience_insights":
        results = {}
        for metric in ["audience_country","audience_city","audience_gender_age"]:
            try:
                data = await ig_get(f"/{IG_USER_ID}/insights", params={"metric": metric, "period": "lifetime"})
                results[metric] = data.get("data",[{}])[0].get("values",[{}])[0].get("value",{})
            except Exception as e:
                results[metric] = {"error": str(e)}
        return fmt(results)

    if name == "get_reach_and_impressions":
        days = args.get("days", 30)
        since = int((datetime.now() - timedelta(days=days)).timestamp())
        until = int(datetime.now().timestamp())
        results = {}
        for metric in ["reach","impressions","profile_views"]:
            try:
                data = await ig_get(f"/{IG_USER_ID}/insights", params={"metric": metric, "period": "day", "since": since, "until": until})
                values = data.get("data",[{}])[0].get("values",[])
                results[metric] = {"total": sum(v["value"] for v in values), "daily": values}
            except Exception as e:
                results[metric] = {"error": str(e)}
        return fmt(results)

    if name == "get_post_detail":
        data = await ig_get(f"/{args['post_id']}", params={"fields": "id,caption,media_type,timestamp,like_count,comments_count,shares_count,saved,reach,impressions,permalink"})
        return fmt(data)

    if name == "get_hashtag_performance":
        top_n = args.get("top_n", 20)
        media = await ig_get(f"/{IG_USER_ID}/media", params={"fields": "id,caption,like_count,comments_count,shares_count,saved,reach", "limit": top_n})
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

    if name == "get_growth_recommendations":
        media = await ig_get(f"/{IG_USER_ID}/media", params={"fields": "id,media_type,timestamp,like_count,comments_count,shares_count,saved,reach,caption", "limit": 50})
        posts = media.get("data", [])
        profile = await ig_get(f"/{IG_USER_ID}", params={"fields": "followers_count,media_count"})
        type_stats, by_day, hash_scores = {}, {}, {}
        days_map = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        for p in posts:
            t = p.get("media_type","UNKNOWN")
            if t not in type_stats: type_stats[t] = {"count":0,"eng":0,"saves":0,"shares":0}
            eng = sum(p.get(k,0) or 0 for k in ["like_count","comments_count","shares_count","saved"])
            type_stats[t]["count"]+=1; type_stats[t]["eng"]+=eng
            type_stats[t]["saves"]+=p.get("saved",0) or 0; type_stats[t]["shares"]+=p.get("shares_count",0) or 0
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
        return fmt({"account_summary": {"followers": profile.get("followers_count"), "posts_analyzed": len(posts)}, "content_type_performance": type_stats, "recommendations": {"1_best_content_type": f"Post more {best_type}", "2_best_day": f"Post on {best_day}", "3_top_hashtags": [f"#{t}" for t,_ in top_tags]}, "saves_leaders": sorted(posts, key=lambda x: x.get("saved",0) or 0, reverse=True)[:3], "shares_leaders": sorted(posts, key=lambda x: x.get("shares_count",0) or 0, reverse=True)[:3]})

    if name == "get_reel_performance":
        media = await ig_get(f"/{IG_USER_ID}/media", params={"fields": "id,media_type,timestamp,like_count,comments_count,shares_count,saved,reach,impressions,permalink,caption", "limit": 100})
        reels = [p for p in media.get("data",[]) if p.get("media_type")=="VIDEO"]
        for r in reels:
            eng = sum(r.get(k,0) or 0 for k in ["like_count","comments_count","shares_count","saved"])
            r["engagement_rate"] = round((eng/max(r.get("reach",1) or 1,1))*100, 2)
        reels_sorted = sorted(reels, key=lambda x: x.get("engagement_rate",0), reverse=True)
        n = max(len(reels),1)
        return fmt({"total_reels": len(reels), "avg_engagement_rate": round(sum(r["engagement_rate"] for r in reels)/n,2), "avg_likes": round(sum(r.get("like_count",0) or 0 for r in reels)/n,1), "avg_shares": round(sum(r.get("shares_count",0) or 0 for r in reels)/n,1), "avg_saves": round(sum(r.get("saved",0) or 0 for r in reels)/n,1), "top_reels": reels_sorted[:5]})

    if name == "get_saves_analysis":
        media = await ig_get(f"/{IG_USER_ID}/media", params={"fields": "id,caption,media_type,timestamp,saved,like_count,reach,permalink", "limit": 100})
        posts = media.get("data",[])
        for p in posts:
            p["save_rate"] = round(((p.get("saved",0) or 0)/max(p.get("reach",1) or 1,1))*100, 2)
        posts_sorted = sorted(posts, key=lambda x: x.get("saved",0) or 0, reverse=True)
        total = sum(p.get("saved",0) or 0 for p in posts)
        return fmt({"total_saves": total, "avg_saves_per_post": round(total/max(len(posts),1),1), "insight": "High saves = content people bookmark. Educational finance carousels typically win here.", "top_saved_posts": posts_sorted[:10]})

    return fmt({"error": f"Unknown tool: {name}"})


async def handle_health(request: Request):
    return JSONResponse({"status": "ok", "server": "instagram-growth-mcp", "tools": len(TOOLS)})

async def handle_sse(request: Request):
    async def event_stream():
        yield f"data: {json.dumps({'type': 'endpoint', 'url': '/mcp'})}\n\n"
        while True:
            await asyncio.sleep(15)
            yield ": keepalive\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "Access-Control-Allow-Origin": "*"})

async def handle_mcp(request: Request):
    if request.method == "OPTIONS":
        return JSONResponse({}, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type"})
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc":"2.0","id":None,"error":{"code":-32700,"message":"Parse error"}})
    id_ = body.get("id")
    method = body.get("method", "")
    params = body.get("params", {})
    try:
        if method == "initialize":
            return JSONResponse({"jsonrpc":"2.0","id":id_,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"instagram-growth-mcp","version":"1.0.0"}}})
        if method in ["notifications/initialized", "ping"]:
            return JSONResponse({"jsonrpc":"2.0","id":id_,"result":{}})
        if method == "tools/list":
            return JSONResponse({"jsonrpc":"2.0","id":id_,"result":{"tools":TOOLS}})
        if method == "tools/call":
            name = params.get("name","")
            args = params.get("arguments", {})
            result = await execute_tool(name, args)
            return JSONResponse({"jsonrpc":"2.0","id":id_,"result":{"content":[{"type":"text","text":result}]}})
        return JSONResponse({"jsonrpc":"2.0","id":id_,"error":{"code":-32601,"message":f"Method not found: {method}"}})
    except Exception as e:
        return JSONResponse({"jsonrpc":"2.0","id":id_,"error":{"code":-32603,"message":str(e)}})


app = Starlette(routes=[
    Route("/", handle_health),
    Route("/health", handle_health),
    Route("/sse", handle_sse, methods=["GET"]),
    Route("/mcp", handle_mcp, methods=["POST", "OPTIONS"]),
    Route("/messages", handle_mcp, methods=["POST", "OPTIONS"]),
])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting Instagram MCP server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
