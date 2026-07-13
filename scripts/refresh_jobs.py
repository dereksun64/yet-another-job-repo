#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def normalize_company_name(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[/&|]+", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def load_company_tiers(path: str) -> dict[str, str]:
    tiers: dict[str, str] = {}
    current_tier = ""

    for line in Path(path).read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^##\s+(Tier\s+.+)$", line.strip())
        if heading:
            current_tier = heading.group(1)
            continue

        company = re.match(r"^-\s+(.+)$", line.strip())
        if company and current_tier:
            tiers[normalize_company_name(company.group(1))] = current_tier

    return tiers


def load_sources(path: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8") as handle:
        sources = json.load(handle)

    for source in sources:
        for key in ("name", "kind", "url"):
            if key not in source:
                raise ValueError(f"source missing {key}: {source}")

    return sources


def strip_markdown(value: str) -> str:
    value = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = value.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", value).strip()


def first_markdown_link(value: str) -> str:
    match = re.search(r"https?://[^\s)]+", value)
    return match.group(0) if match else ""


def classify_degree(title: str) -> str:
    title = title.lower()
    if any(word in title for word in ("master", "mba", "phd", "graduate internship")):
        return "masters"
    if any(word in title for word in ("undergrad", "bachelor", "bs/ms", "b.s", "student")):
        return "bachelors"
    return "unknown"


def classify_category(title: str, fallback: str) -> str:
    title = title.lower()
    if any(word in title for word in ("quant", "trading", "trader")):
        return "Quant"
    if any(word in title for word in ("machine learning", "data science", "research scientist")) or re.search(r"\bai\b", title):
        return "AI/ML"
    if "product" in title:
        return "Product"
    if any(word in title for word in ("software", "backend", "frontend", "full stack", "mobile", "devops")):
        return "Software Engineering"
    return fallback


def split_markdown_row(line: str) -> list[str]:
    if not line.strip().startswith("|"):
        return []
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_markdown_jobs(markdown: str, source: dict[str, str], tiers: dict[str, str]) -> list[dict[str, str]]:
    jobs: list[dict[str, str]] = []
    headers: list[str] = []
    current_category = "Other"

    for line in markdown.splitlines():
        heading = re.match(r"^###\s+(.+)$", line.strip())
        if heading:
            current_category = strip_markdown(heading.group(1))
            headers = []
            continue

        cells = split_markdown_row(line)
        if not cells:
            continue

        lowered = [strip_markdown(cell).lower() for cell in cells]
        if {"company", "location"}.issubset(set(lowered)):
            headers = lowered
            continue
        if all(set(cell) <= {"-", ":"} for cell in lowered):
            continue
        if not headers or len(cells) < len(headers):
            continue

        row = dict(zip(headers, cells))
        company_raw = row.get("company", "")
        title_raw = row.get("role") or row.get("position") or ""
        location_raw = row.get("location", "")
        apply_raw = row.get("application") or row.get("application/link") or row.get("posting") or row.get("apply") or ""
        age_raw = row.get("age") or row.get("date posted") or row.get("posted") or ""
        salary_raw = row.get("salary", "")

        company = strip_markdown(company_raw)
        title = strip_markdown(title_raw)
        location = strip_markdown(location_raw)
        apply_url = first_markdown_link(apply_raw)

        if not company or not title or not apply_url:
            continue

        tier_key = normalize_company_name(company)
        jobs.append(
            {
                "id": "",
                "company": company,
                "title": title,
                "location": location,
                "applyUrl": apply_url,
                "source": source["name"],
                "sourceUrl": source["url"],
                "jobType": source["kind"],
                "category": classify_category(title, strip_markdown(current_category)),
                "degreeLevel": classify_degree(title),
                "companyTier": tiers.get(tier_key, "Unlisted"),
                "age": strip_markdown(age_raw),
                "salary": strip_markdown(salary_raw),
            }
        )

    return jobs


def job_key(job: dict[str, str]) -> str:
    if job.get("applyUrl"):
        return job["applyUrl"].strip().lower()
    return "|".join(
        [
            normalize_company_name(job.get("company", "")),
            normalize_company_name(job.get("title", "")),
            normalize_company_name(job.get("location", "")),
        ]
    )


def dedupe_jobs(jobs: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []

    for job in jobs:
        key = job_key(job)
        if key in seen:
            continue
        seen.add(key)
        job = dict(job)
        job["id"] = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
        deduped.append(job)

    return deduped


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "job-repo-refresh/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def refresh_jobs(sources_path: str, tiers_path: str, output_path: str) -> dict[str, object]:
    sources = load_sources(sources_path)
    tiers = load_company_tiers(tiers_path)
    jobs: list[dict[str, str]] = []
    source_counts: dict[str, int] = {}

    for source in sources:
        markdown = fetch_text(source["url"])
        parsed = parse_markdown_jobs(markdown, source, tiers)
        source_counts[source["name"]] = len(parsed)
        jobs.extend(parsed)

    jobs = dedupe_jobs(jobs)
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceCounts": source_counts,
        "count": len(jobs),
        "jobs": jobs,
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="sources.json")
    parser.add_argument("--tiers", default="docs/list.md")
    parser.add_argument("--output", default="data/jobs.json")
    args = parser.parse_args()

    payload = refresh_jobs(args.sources, args.tiers, args.output)
    print(f"Wrote {payload['count']} jobs to {args.output}")


if __name__ == "__main__":
    main()
