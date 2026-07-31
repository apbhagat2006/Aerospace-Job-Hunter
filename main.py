import asyncio
import json
import os
import re
import httpx
from pathlib import Path
from typing import Any, Dict, List, Set
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from bs4 import BeautifulSoup

INTERNSHIP_PATTERN = re.compile(r"\b(interns?|internship|co-?op|coop|trainee|student)\b", re.IGNORECASE)
AEROSPACE_KEYWORDS = ["aerospace", "space", "rocket", "propulsion", "structures", "materials", "gnc", "guidance", "navigation", "control", "aerodynamics", "flight software", "avionics", 
                      "satellite", "orbital", "launch", "engineering", "engineer", "software", "mechanical", "hardware", "systems", "manufacturing", "test", "payload", "flight"]
COMPANIES = [
    # Original Companies
    {"name": "SpaceX", "provider": "greenhouse", "board": "spacex"},
    {"name": "Blue Origin", "provider": "greenhouse", "board": "blue-origin"},
    {"name": "Rocket Lab", "provider": "greenhouse", "board": "rocketlab"},
    {"name": "Anduril", "provider": "lever", "board": "anduril"},
    
    # Launch Providers & Spacecraft
    {"name": "Relativity Space", "provider": "greenhouse", "board": "relativityspace"},
    {"name": "Firefly Aerospace", "provider": "greenhouse", "board": "fireflyaerospace"},
    {"name": "Stoke Space", "provider": "greenhouse", "board": "stokespace"},
    {"name": "ABL Space Systems", "provider": "greenhouse", "board": "ablspacesystems"},
    {"name": "Impulse Space", "provider": "greenhouse", "board": "impulsespace"},
    {"name": "Vast", "provider": "greenhouse", "board": "vast"},
    {"name": "Axiom Space", "provider": "greenhouse", "board": "axiomspace"},
    
    # Satellites, Data & Comms
    {"name": "Planet", "provider": "lever", "board": "planet"},
    {"name": "Astranis", "provider": "greenhouse", "board": "astranis"},
    {"name": "Capella Space", "provider": "greenhouse", "board": "capellaspace"},
    {"name": "HawkEye 360", "provider": "greenhouse", "board": "hawkeye360"},
    {"name": "Slingshot Aerospace", "provider": "greenhouse", "board": "slingshotaerospace"},
    
    # Aerospace Defense & Autonomy
    {"name": "Shield AI", "provider": "greenhouse", "board": "shieldai"},
    {"name": "True Anomaly", "provider": "lever", "board": "trueanomaly"},
    {"name": "Skydio", "provider": "greenhouse", "board": "skydio"},
    {"name": "Palantir", "provider": "lever", "board": "palantir"},
    
    # Hypersonics & Next-Gen Aviation
    {"name": "Hermeus", "provider": "greenhouse", "board": "hermeus"},
    {"name": "Joby Aviation", "provider": "greenhouse", "board": "jobyaviation"},
    {"name": "Archer Aviation", "provider": "greenhouse", "board": "archeraviation"},
    {"name": "Beta Technologies", "provider": "greenhouse", "board": "betatechnologies"},

    # Workday Aerospace Companies
    {"name": "Boeing", "provider": "workday", "host": "boeing.wd1.myworkdayjobs.com", "tenant": "boeing", "site": "EXTERNAL_CAREERS"},
    {"name": "Northrop Grumman", "provider": "workday", "host": "ngc.wd1.myworkdayjobs.com", "tenant": "ngc", "site": "Northrop_Grumman_External_Site"},
    {"name": "RTX (Raytheon/Collins)", "provider": "workday", "host": "globalhr.wd5.myworkdayjobs.com", "tenant": "globalhr", "site": "REC_RTX_Ext_Gateway"},
    {"name": "Airbus", "provider": "workday", "host": "ag.wd3.myworkdayjobs.com", "tenant": "ag", "site": "Airbus"},
    {"name": "GE Aerospace", "provider": "workday", "host": "geaerospace.wd5.myworkdayjobs.com", "tenant": "geaerospace", "site": "GE_ExternalSite"},

    # IBM BrassRing Companies
    {"name": "Lockheed Martin", "provider": "brassring", "partnerid": "25037", "siteid": "5010"},

    # SuccessFactors Companies
    {"name": "Gulfstream", "provider": "successfactors", "base_url": "careers.gulfstream.com"},
    {"name": "Bombardier", "provider": "successfactors", "base_url": "jobs.bombardier.com"},

    # Phenom Companies
    {"name": "L3Harris", "provider": "phenom", "base_url": "careers.l3harris.com"},
    {"name": "BAE Systems", "provider": "phenom", "base_url": "jobs.baesystems.com"},
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
        job_id = f"{job['company']}:{job['id']}"
        if job_id not in seen_job_ids:
            seen_job_ids.add(job_id)
            if is_target_role(job["title"]):
                fresh_matches.append(job)
    return fresh_matches

@retry(
        stop=stop_after_attempt(3),                                   
        wait=wait_exponential(multiplier=1, min=2, max=10),             
        retry=retry_if_exception_type(httpx.TransportError),         
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
        retry=retry_if_exception_type(httpx.TransportError),         
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

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.TransportError),
    reraise=True,
)
async def fetch_workday_jobs(host: str, tenant: str, site: str,) -> List[Dict[str, Any]]:
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Language": "en-US",
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://{host}/en-US/{site}",
    }

    page_size = 50
    offset = 0
    all_postings: List[Dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            payload = {
                "appliedFacets": {},
                "limit": page_size,
                "offset": offset,
                "searchText": "",
            }

            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            postings = data.get("jobPostings", [])
            total = data.get("total", 0)

            if not postings:
                break

            all_postings.extend(postings)
            offset += len(postings)

            if offset >= total:
                break

    print(f"Workday {tenant}: fetched {len(all_postings)} jobs")
    
    return [
        {
            "id": job.get(
                "bulletinTaskRqstId",
                job.get("externalPath", "Unknown"),
            ),
            "title": job.get("title", "Untitled"),
            "location": job.get("locationsText", "Unknown"),
            "url": (
                f"https://{host}/en-US/{site}"
                f"{job.get('externalPath', '')}"
            ),
        }
        for job in all_postings
    ]

@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=1, min=2, max=10), 
    retry=retry_if_exception_type(httpx.TransportError), 
    reraise=True
)
async def fetch_brassring_jobs(partnerid: str, siteid: str) -> List[Dict[str, Any]]:
    url = "https://sjobs.brassring.com/TgNewUI/Search/Ajax/HomeSearch"
    
    payload = {
        "PageType": "JobDetails",
        "partnerid": partnerid,
        "siteid": siteid,
        "Keyword": "",
        "Longitude": 0,
        "Latitude": 0,
        "IsRadiusSearch": False,
        "QuestionnaireResults": {}
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            try:
                data = response.json()
                # Parse through the nested BrassRing JSON structure
                job_list = data.get("Data", {}).get("Jobs", {}).get("Job", [])
                
                return [
                    {
                        "id": job.get("JobId", "Unknown"),
                        "title": job.get("JobTitle", "Untitled"),
                        "location": job.get("Location", "Unknown"),
                        "url": f"https://sjobs.brassring.com/TGnewUI/Search/home/HomeWithPreLoad?partnerid={partnerid}&siteid={siteid}&PageType=JobDetails&jobid={job.get('JobId')}"
                    }
                    for job in job_list
                ]
            except Exception:
                return []
        return []

@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=1, min=2, max=10), 
    retry=retry_if_exception_type(httpx.TransportError), 
    reraise=True
)
async def fetch_successfactors_jobs(base_url: str) -> List[Dict[str, Any]]:
    url = f"https://{base_url}/search/?q=&sortColumn=referencedate&sortDirection=desc&startrow=0"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            job_rows = soup.find_all("tr", class_="data-row")
            jobs_list = []
            
            for row in job_rows:
                title_elem = row.find("a", class_="jobTitle-link")
                location_elem = row.find("span", class_="jobLocation")
                
                if title_elem:
                    title = title_elem.text.strip()
                    job_path = title_elem.get("href", "")
                    job_url = f"https://{base_url}{job_path}"
                    
                    job_id = job_path.split("/")[-2] if "/" in job_path else job_path
                    
                    location = location_elem.text.strip() if location_elem else "Unknown"
                    
                    jobs_list.append({
                        "id": job_id,
                        "title": title,
                        "location": location,
                        "url": job_url
                    })
                    
            return jobs_list
        return []

@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=1, min=2, max=10), 
    retry=retry_if_exception_type(httpx.TransportError), 
    reraise=True
)
async def fetch_phenom_jobs(base_url: str) -> List[Dict[str, Any]]:
    url = f"https://{base_url}/en/search-jobs/results"
    
    headers = {
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=headers, follow_redirects=True)
        if response.status_code == 200:
            try:
                data = response.json()
            
                html_content = data.get("results", "")
                
                if not html_content:
                    return []
                
                soup = BeautifulSoup(html_content, "html.parser")
                job_elements = soup.find_all("li")
                jobs_list = []
                
                for job in job_elements:
                    link_elem = job.find("a")
                    if link_elem:
                        title = link_elem.find("h2").text.strip() if link_elem.find("h2") else "Untitled"
                        
                        loc_elem = link_elem.find("span", class_="job-location")
                        location = loc_elem.text.strip() if loc_elem else "Unknown"
                        
                        job_path = link_elem.get("href", "")
                        job_url = f"https://{base_url}{job_path}"
                        
                        job_id = job_path.split("/")[-1] if "/" in job_path else job_path
                        
                        jobs_list.append({
                            "id": job_id,
                            "title": title,
                            "location": location,
                            "url": job_url
                        })
                return jobs_list
            except Exception as e:
                print(f"Error parsing Phenom JSON: {e}")
                return []
        return []

async def fetch_company_jobs(company: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        provider = company["provider"]

        if company["provider"] == "greenhouse":
            jobs = await fetch_greenhouse_jobs(company["board"])
        elif company["provider"] == "lever":
            jobs = await fetch_lever_jobs(company["board"])
        elif company["provider"] == "workday":
            jobs = await fetch_workday_jobs(company["host"], company["tenant"], company["site"])
        elif company["provider"] == "brassring":
            jobs = await fetch_brassring_jobs(company["partnerid"], company["siteid"])
        elif company["provider"] == "successfactors":
            jobs = await fetch_successfactors_jobs(company["base_url"])
        elif company["provider"] == "phenom":
            jobs = await fetch_phenom_jobs(company["base_url"])
        else:
            print(
                f"Skipping {company['name']}: "
                f"unknown provider '{provider}'."
            )
            return []

    except httpx.HTTPError as exc:
        print(f"Skipping {company['name']}: request failed: {exc}")
        return []
    except (KeyError, TypeError, ValueError) as exc:
        print(f"Skipping {company['name']}: invalid configuration: {exc}")
        return []
    except Exception as exc:
        print(f"Skipping {company['name']}: unexpected error: {exc}")
        return []

    for job in jobs:
        job["company"] = company["name"]

    return jobs

@retry(
        stop=stop_after_attempt(3),                                   
        wait=wait_exponential(multiplier=1, min=2, max=10),             
        retry=retry_if_exception_type(httpx.TransportError),         
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
        response = await client.post(webhook_url, json=payload)
        response.raise_for_status()

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