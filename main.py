import asyncio
import json
import os
import re
import httpx
from pathlib import Path
from typing import Any, Dict, List, Set
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

INTERNSHIP_PATTERN = re.compile(r"\b(interns?|internship|co-?op|coop|trainee|student)\b", re.IGNORECASE)
AEROSPACE_KEYWORDS = ["aerospace", "space", "rocket", "propulsion", "structures", "materials", "gnc", "guidance", "navigation", "control", "aerodynamics", "flight software", "avionics", 
                      "satellite", "orbital", "launch", "engineering", "engineer", "software", "mechanical", "hardware", "systems", "manufacturing", "test", "payload", "flight"]
COMPANIES = [
    {"name": "SpaceX", "provider": "greenhouse", "board": "spacex"},
    {"name": "Blue Origin", "provider": "greenhouse", "board": "blue-origin"},
    {"name": "Rocket Lab", "provider": "greenhouse", "board": "rocketlab"},
    {"name": "Anduril", "provider": "lever", "board": "anduril"},
]
PERSISTENCE_FILE = Path("seen_jobs.json")


def is_target_role(job_title: str) -> bool:
    title_lower = job_title.lower()
    
    is_internship = bool(INTERNSHIP_PATTERN.search(title_lower))
    
    is_aerospace = (any(keyword in title_lower for keyword in AEROSPACE_KEYWORDS))
    
    return is_internship and is_aerospace


def process_jobs(new_jobs: List[Dict[str, Any]], seen_job_ids: Set[str]) -> List[Dict[str, Any]]:
    fresh_matches: List[Dict[str, Any]] = []
    for job in new_jobs:
        job_id = str(job["id"])
        if job_id not in seen_job_ids:
            seen_job_ids.add(job_id)
            if is_target_role(job["title"]):
                fresh_matches.append(job)
    return fresh_matches

@retry(
        stop=stop_after_attempt(3),                                   
        wait=wait_exponential(multiplier=1, min=2, max=10),             
        retry=retry_if_exception_type(httpx.TimeoutException),         
        reraise=True
)
async def fetch_greenhouse_jobs(company_board: str) -> List[Dict[str, Any]]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_board}/jobs"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        if response.status_code == 200:
            data = response.json()
            return [
                {
                    "id": str(job["id"]),
                    "title": job["title"],
                    "location": job.get("location", {}).get("name", "Unknown"),
                    "url": job.get("absolute_url", ""),
                }
                for job in data.get("jobs", [])
            ]
    return []

@retry(
        stop=stop_after_attempt(3),                                   
        wait=wait_exponential(multiplier=1, min=2, max=10),             
        retry=retry_if_exception_type(httpx.TimeoutException),         
        reraise=True
)
async def fetch_lever_jobs(company_board: str) -> List[Dict[str, Any]]:
    url = f"https://api.lever.co/v0/postings/{company_board}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        if response.status_code == 200:
            data = response.json()
            return [
                {
                    "id": str(job["id"]),
                    "title": job.get("text", "Untitled"),
                    "location": job.get("categories", {}).get("location", "Unknown"),
                    "url": job.get("hostedUrl", ""),
                }
                for job in data
            ]
    return []


async def fetch_company_jobs(company: Dict[str, Any]) -> List[Dict[str, Any]]:
    if company["provider"] == "greenhouse":
        jobs = await fetch_greenhouse_jobs(company["board"])
    else:
        jobs = await fetch_lever_jobs(company["board"])

    for job in jobs:
        job["company"] = company["name"]
    return jobs

@retry(
        stop=stop_after_attempt(3),                                   
        wait=wait_exponential(multiplier=1, min=2, max=10),             
        retry=retry_if_exception_type(httpx.TimeoutException),         
        reraise=True
)
async def send_discord_alert(webhook_url: str, job: Dict[str, Any]) -> None:
    payload = {
        "content": (
            f"🚨 **New internship role posted at {job['company']}!**\n"
            f"**Role:** {job['title']}\n"
            f"**Location:** {job['location']}\n"
            f"**Apply:** {job['url']}"
        )
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(webhook_url, json=payload)

#  --------Supabase helper functions-------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True
)
def _supabase_get(url: str, headers: dict) -> httpx.Response:
    return httpx.get(url, headers=headers, timeout=10.0)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True
)
def _supabase_post(url: str, headers: dict, **kwargs: Any) -> httpx.Response:
    json_data = kwargs.pop("json", None)
    if json_data is None:
        json_data = kwargs.pop("json_data", None)
    return httpx.post(url, headers=headers, json=json_data, timeout=10.0, **kwargs)

# -----------------------------------------

def load_seen_job_ids() -> Set[str]:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if supabase_url and supabase_key:
        try:
            response = _supabase_get(
                url=f"{supabase_url}/rest/v1/job_seen_ids?select=id",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "application/json",
                }
            )
            if response.status_code == 200:
                data = response.json()
                return {str(item["id"]) for item in data if "id" in item}
        except httpx.HTTPError as exc:
            print(f"Supabase read failed after 3 attempts: {exc}")

    if PERSISTENCE_FILE.exists():
        try:
            data = json.loads(PERSISTENCE_FILE.read_text())
            return {str(item) for item in data}
        except json.JSONDecodeError:
            return set()

    return set()


def save_seen_job_ids(seen_job_ids: Set[str]) -> None:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if supabase_url and supabase_key:
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
        }
        for job_id in sorted(seen_job_ids):
            try:
                _supabase_post(
                    url=f"{supabase_url}/rest/v1/job_seen_ids?on_conflict=id",
                    headers=headers,
                    json={"id": job_id}
                )
            except httpx.HTTPError as exc:
                print(f"Supabase write failed for {job_id} after 3 attempts: {exc}")
        return

    PERSISTENCE_FILE.write_text(json.dumps(sorted(seen_job_ids)))


async def run_scraper() -> List[Dict[str, Any]]:
    tasks = [fetch_company_jobs(company) for company in COMPANIES]
    results = await asyncio.gather(*tasks)

    all_jobs: List[Dict[str, Any]] = []
    for company_jobs in results:
        all_jobs.extend(company_jobs)

    seen_job_ids = load_seen_job_ids()
    fresh_matches = process_jobs(all_jobs, seen_job_ids)
    save_seen_job_ids(seen_job_ids)
    return fresh_matches


def main() -> None:
    fresh_matches = asyncio.run(run_scraper())
    if fresh_matches:
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        if webhook_url:
            asyncio.run(_send_all_alerts(webhook_url, fresh_matches))
        else:
            print(f"Found {len(fresh_matches)} new matches but no Discord webhook was configured.")
    else:
        print("No new matching roles found.")


async def _send_all_alerts(webhook_url: str, jobs: List[Dict[str, Any]]) -> None:
    for job in jobs:
        await send_discord_alert(webhook_url, job)


if __name__ == "__main__":
    main()