#!/usr/bin/env python3
import argparse
import json
import re
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="sources.json")
    parser.add_argument("--tiers", default="docs/list.md")
    args = parser.parse_args()

    print(f"Loaded {len(load_sources(args.sources))} sources")
    print(f"Loaded {len(load_company_tiers(args.tiers))} company tier aliases")


if __name__ == "__main__":
    main()
