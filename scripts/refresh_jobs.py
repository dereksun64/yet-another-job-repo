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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="sources.json")
    parser.add_argument("--tiers", default="docs/list.md")
    args = parser.parse_args()

    print(f"Loaded {len(load_sources(args.sources))} sources")
    print(f"Loaded {len(load_company_tiers(args.tiers))} company tier aliases")


if __name__ == "__main__":
    main()
