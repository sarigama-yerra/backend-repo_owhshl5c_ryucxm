import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


@app.get("/api/github/repos")
def get_github_repos(
    username: str = Query(..., description="GitHub username to fetch repositories for"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    per_page: int = Query(30, ge=1, le=100, description="Number of repos per page (max 100)"),
    sort: str = Query("updated", description="Sort key: created, updated, pushed, full_name"),
    direction: str = Query("desc", description="Sort direction: asc or desc"),
):
    """Fetch public repositories for a GitHub user via GitHub API.

    Optionally uses a GitHub token from environment (GITHUB_TOKEN) to increase rate limits.
    """
    if not username:
        raise HTTPException(status_code=400, detail="username is required")

    base_url = f"https://api.github.com/users/{username}/repos"
    params = {
        "page": page,
        "per_page": per_page,
        "sort": sort,
        "direction": direction,
        "type": "owner",
    }

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "FlamesBlue-GitHub-Portfolio-App"
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(base_url, params=params, headers=headers, timeout=15)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach GitHub: {e}")

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="GitHub user not found")
    if resp.status_code == 403:
        # Rate limited or forbidden
        detail = resp.json().get("message", "Forbidden or rate limited by GitHub") if resp.headers.get("content-type", "").startswith("application/json") else "Forbidden or rate limited by GitHub"
        raise HTTPException(status_code=403, detail=detail)
    if not resp.ok:
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:200])

    repos = resp.json()

    # Normalize/whitelist fields to send to frontend
    def map_repo(r: dict) -> dict:
        return {
            "id": r.get("id"),
            "name": r.get("name"),
            "full_name": r.get("full_name"),
            "html_url": r.get("html_url"),
            "description": r.get("description"),
            "language": r.get("language"),
            "stargazers_count": r.get("stargazers_count"),
            "forks_count": r.get("forks_count"),
            "open_issues_count": r.get("open_issues_count"),
            "watchers_count": r.get("watchers_count"),
            "topics": r.get("topics", []),
            "license": (r.get("license") or {}).get("spdx_id") if r.get("license") else None,
            "archived": r.get("archived", False),
            "disabled": r.get("disabled", False),
            "private": r.get("private", False),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
            "pushed_at": r.get("pushed_at"),
            "homepage": r.get("homepage"),
        }

    return {"items": [map_repo(r) for r in repos]}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
