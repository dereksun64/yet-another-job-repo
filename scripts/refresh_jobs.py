#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.request
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
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
    value = re.sub(r"<[^>]+>", "", value)
    value = value.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", value).strip()


def valid_http_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        parsed.port
    except ValueError:
        return False
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname) and not re.search(r"\s", value)


def matching_paren(value: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(value)):
        if value[index] == "(":
            depth += 1
        elif value[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def nested_image_destination(value: str) -> str | None:
    start = value.find("[![")
    if start == -1:
        return None

    image_open = value.find("](", start)
    if image_open == -1:
        return ""
    image_close = matching_paren(value, image_open + 1)
    if image_close == -1 or value[image_close + 1 : image_close + 3] != "](":
        return ""

    destination_open = image_close + 2
    destination_close = matching_paren(value, destination_open)
    if destination_close == -1:
        return ""

    destination = html.unescape(value[destination_open + 1 : destination_close].strip())
    return destination if valid_http_url(destination) else ""


def markdown_destination(value: str) -> str:
    match = re.search(r"\[[^\]]+\]\(", value)
    if not match:
        return ""

    destination_open = match.end() - 1
    destination_close = matching_paren(value, destination_open)
    if destination_close == -1:
        return ""

    destination = html.unescape(value[destination_open + 1 : destination_close].strip())
    return destination if valid_http_url(destination) else ""


def bare_http_url(value: str) -> str:
    match = re.search(r"https?://", value)
    if not match:
        return ""

    end = match.start()
    while end < len(value) and value[end] not in ' \t\r\n"\'<>':
        end += 1

    candidate = html.unescape(value[match.start() : end])
    return candidate if valid_http_url(candidate) else ""


def first_markdown_link(value: str) -> str:
    nested_destination = nested_image_destination(value)
    if nested_destination is not None:
        return nested_destination

    value_without_images = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", value)
    link_destination = markdown_destination(value_without_images)
    if link_destination:
        return link_destination

    html_link = re.search(r'''<a\b[^>]*\bhref=["']([^"']+)''', value_without_images, flags=re.IGNORECASE)
    if html_link:
        candidate = html.unescape(html_link.group(1))
        return candidate if valid_http_url(candidate) else ""
    return bare_http_url(value_without_images)


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
    if re.search(r"\bproduct\b", title):
        return "Product"
    if any(word in title for word in ("software", "backend", "frontend", "full stack", "mobile", "devops")):
        return "Software Engineering"
    return fallback


def split_markdown_row(line: str) -> list[str]:
    if not line.strip().startswith("|"):
        return []
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def normalize_html_tables(markdown: str) -> str:
    def table_to_markdown(match: re.Match[str]) -> str:
        rows: list[str] = []
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", match.group(0), flags=re.IGNORECASE | re.DOTALL):
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.IGNORECASE | re.DOTALL)
            if cells:
                rows.append("| " + " | ".join(cells) + " |")
        return "\n".join(rows)

    return re.sub(r"<table[^>]*>.*?</table>", table_to_markdown, markdown, flags=re.IGNORECASE | re.DOTALL)


def parse_markdown_jobs(markdown: str, source: dict[str, str], tiers: dict[str, str]) -> list[dict[str, str]]:
    jobs: list[dict[str, str]] = []
    headers: list[str] = []
    current_category = "Other"
    previous_company = ""

    for line in normalize_html_tables(markdown).splitlines():
        heading = re.match(r"^#{2,3}\s+(.+)$", line.strip())
        if heading:
            current_category = strip_markdown(heading.group(1))
            headers = []
            previous_company = ""
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
        if company in {"↳", "⤷"}:
            company = previous_company
        elif company:
            previous_company = company
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
        return canonical_apply_url(job["applyUrl"])
    return "|".join(
        [
            normalize_company_name(job.get("company", "")),
            normalize_company_name(job.get("title", "")),
            normalize_company_name(job.get("location", "")),
        ]
    )


def canonical_apply_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() != "ref" and not key.lower().startswith("utm_")
    ]
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, urlencode(query), ""))


def validate_generated_jobs(jobs: list[dict[str, str]]) -> None:
    markers = {"↳", "⤷"}
    image_extensions = (".avif", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp")
    invalid_companies = [job["company"] for job in jobs if job.get("company") in markers]
    image_apply_urls = [
        job["applyUrl"]
        for job in jobs
        if urlsplit(job.get("applyUrl", "")).path.lower().endswith(image_extensions)
    ]
    if invalid_companies or image_apply_urls:
        raise ValueError("generated jobs contain invalid company markers or image apply URLs")


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
        if not parsed:
            raise ValueError(f"source parsed zero jobs: {source['name']}")
        jobs.extend(parsed)

    jobs = dedupe_jobs(jobs)
    validate_generated_jobs(jobs)
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceCounts": source_counts,
        "count": len(jobs),
        "jobs": jobs,
    }

    output = Path(output_path)
    if output.exists():
        existing = json.loads(output.read_text(encoding="utf-8"))
        if (
            existing.get("jobs") == payload["jobs"]
            and existing.get("sourceCounts") == payload["sourceCounts"]
            and existing.get("count") == payload["count"]
        ):
            payload["generatedAt"] = existing.get("generatedAt", payload["generatedAt"])
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
