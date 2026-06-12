import os
import random

import httpx
import sentry_sdk
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates


load_dotenv()
sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    # Add data like request headers and IP for users,
    # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
    send_default_pii=True,
    # Enable sending logs to Sentry
    enable_logs=True,
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for tracing.
    traces_sample_rate=1.0,
    # Set profile_session_sample_rate to 1.0 to profile 100%
    # of profile sessions.
    profile_session_sample_rate=0.1,
    # Set profile_lifecycle to "trace" to automatically
    # run the profiler on when there is an active transaction
    profile_lifecycle="trace",
)


app = FastAPI()
templates = Jinja2Templates(directory="templates")


async def get_anime_by_status(username: str, status: str):
    """
    Fetch all anime with specified status from a user's AniList.

    Args:
        username: AniList username
        status: PLANNING, CURRENT, COMPLETED, DROPPED, PAUSED, or REPEATING

    Returns:
        List of anime dictionaries with title and other info
    """
    url = "https://graphql.anilist.co"

    query = """
    query ($username: String, $status: MediaListStatus) {
      MediaListCollection(userName: $username, type: ANIME, status: $status) {
        lists {
          entries {
            media {
              id
              title {
                romaji
                english
                native
              }
              format
              episodes
              status
              averageScore
              genres
              season
              seasonYear
              coverImage {
                large
              }
              siteUrl
            }
          }
        }
      }
    }
    """

    variables = {"username": username, "status": status}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url, json={"query": query, "variables": variables}
            )
            response.raise_for_status()

            data = response.json()

            if "data" in data and data["data"]["MediaListCollection"]:
                lists = data["data"]["MediaListCollection"]["lists"]
                if lists and len(lists) > 0:
                    entries = lists[0]["entries"]
                    anime_list = [entry["media"] for entry in entries]
                    return anime_list

            return []

    except Exception as e:
        print(f"Error: {e}")
        return []


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the main page with search form"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/random", response_class=HTMLResponse)
async def get_random(
    request: Request, username: str = Form(...), status: str = Form(...)
):
    """Get a random anime and return HTML fragment"""

    if not username:
        return """
        <div id="result" class="error">
            <p>❌ Please enter a username</p>
        </div>
        """

    anime_list = await get_anime_by_status(username, status)

    if not anime_list:
        return f"""
        <div id="result" class="error">
            <p>❌ No anime found for user '{username}' with status '{status}'</p>
            <p>Make sure the username is correct and your list is public.</p>
        </div>
        """

    # Pick random anime
    anime = random.choice(anime_list)

    # Prefer English title, fall back to Romaji
    title = anime["title"]["english"] or anime["title"]["romaji"]
    romaji = anime["title"]["romaji"] if anime["title"]["romaji"] != title else None
    native = anime["title"]["native"]

    sentry_sdk.logger.info(f"User: {username} | Anime: {title}")

    # Build genres string
    genres_str = ", ".join(anime["genres"]) if anime["genres"] else "N/A"

    # Build season/year string
    season_info = ""
    if anime["season"] and anime["seasonYear"]:
        season_info = f"{anime['season'].title()} {anime['seasonYear']}"
    elif anime["seasonYear"]:
        season_info = str(anime["seasonYear"])

    # Return HTML fragment with anime card
    return f"""
    <div id="result" class="anime-card">
        <div class="anime-header">
            <img src="{anime["coverImage"]["large"]}" alt="{title}" class="anime-cover">
            <div class="anime-info">
                <h2>🎲 {title}</h2>
                {f'<p class="alt-title">({romaji})</p>' if romaji else ""}
                {f'<p class="alt-title">{native}</p>' if native else ""}
            </div>
        </div>
        
        <div class="anime-details">
            <div class="detail-row">
                <span class="label">📊 Format:</span>
                <span>{anime["format"]}</span>
            </div>
            
            <div class="detail-row">
                <span class="label">📺 Episodes:</span>
                <span>{anime["episodes"] if anime["episodes"] else "Unknown"}</span>
            </div>
            
            {
        f'''<div class="detail-row">
                <span class="label">⭐ Score:</span>
                <span>{anime["averageScore"]}/100</span>
            </div>'''
        if anime["averageScore"]
        else ""
    }
            
            {
        f'''<div class="detail-row">
                <span class="label">📅 Release:</span>
                <span>{season_info}</span>
            </div>'''
        if season_info
        else ""
    }
            
            <div class="detail-row">
                <span class="label">🎭 Genres:</span>
                <span>{genres_str}</span>
            </div>
            
            <div class="detail-row">
                <span class="label">📌 Status:</span>
                <span>{anime["status"]}</span>
            </div>
        </div>
        
        <div class="anime-footer">
            <a href="{anime["siteUrl"]}" target="_blank" class="anilist-link">
                🔗 View on AniList
            </a>
        </div>
    </div>
    """


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    return "User-agent: *\nDisallow: /"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
