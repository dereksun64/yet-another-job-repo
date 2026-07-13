# Job Repo Webapp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a small webapp that aggregates jobs from five GitHub job repos, joins them with the company tiers in `docs/list.md`, and supports refresh, search, filter, and sort.

**Architecture:** Use one Python stdlib refresh script to fetch raw Markdown, parse known table formats, dedupe jobs, and write `data/jobs.json`. Use a static vanilla HTML/CSS/JS app to load `data/jobs.json`, filter/sort in the browser, and provide a refresh button that reloads the latest generated data.

**Tech Stack:** Python 3 stdlib, `unittest`, vanilla HTML/CSS/JavaScript, GitHub Actions cron.

## Global Constraints

- No database for v1.
- No backend server for v1.
- No runtime npm dependencies.
- Use `docs/list.md` as the company tier source.
- Use these sources only in v1:
  - `SimplifyJobs/Summer2026-Internships`
  - `SimplifyJobs/New-Grad-Positions`
  - `vanshb03/New-Grad-2026`
  - `vanshb03/Summer2027-Internships`
  - `speedyapply/2027-SWE-College-Jobs`
- Dedupe by apply URL first, then normalized company + title + location.
- Treat upstream repos as attributed sources, not original data owned by this repo.
- Prefer simple heuristics over ML or browser automation.

---

## File Structure

- Create `sources.json`: declarative list of raw Markdown URLs and source metadata.
- Create `scripts/refresh_jobs.py`: fetches Markdown, parses tables, normalizes rows, joins company tiers, dedupes, and writes JSON.
- Create `tests/test_refresh_jobs.py`: stdlib `unittest` coverage for tier parsing, table parsing, classification, and dedupe.
- Create `data/jobs.json`: generated normalized job data consumed by the webapp.
- Create `web/index.html`: static app shell and controls.
- Create `web/styles.css`: responsive utility-style layout, no framework.
- Create `web/app.js`: loads `data/jobs.json`, handles search/filter/sort/render.
- Create `.github/workflows/refresh-jobs.yml`: scheduled refresh workflow.
- Create `README.md`: project usage and attribution.

---

### Task 1: Tier Parsing And Source Config

**Files:**
- Create: `sources.json`
- Create: `scripts/refresh_jobs.py`
- Create: `tests/test_refresh_jobs.py`

**Interfaces:**
- Consumes: `docs/list.md`
- Produces:
  - `load_company_tiers(path: str) -> dict[str, str]`
  - `normalize_company_name(value: str) -> str`
  - `load_sources(path: str) -> list[dict[str, str]]`

- [ ] **Step 1: Write failing tests for company tier parsing**

Add this to `tests/test_refresh_jobs.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from scripts.refresh_jobs import (
    load_company_tiers,
    load_sources,
    normalize_company_name,
)


class RefreshJobsTests(unittest.TestCase):
    def test_normalize_company_name(self):
        self.assertEqual(normalize_company_name("  JP Morgan Chase "), "jp morgan chase")
        self.assertEqual(normalize_company_name("TikTok/ByteDance"), "tiktok bytedance")
        self.assertEqual(normalize_company_name("X/ Twitter"), "x twitter")

    def test_load_company_tiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "list.md"
            path.write_text(
                "# Company Tiers\n\n"
                "## Tier 1\n\n"
                "- Apple\n"
                "- OpenAI\n\n"
                "## Tier 1.5\n\n"
                "- JP Morgan Chase\n\n"
                "## Tier 2\n\n"
                "- Roblox\n",
                encoding="utf-8",
            )

            tiers = load_company_tiers(str(path))

        self.assertEqual(tiers["apple"], "Tier 1")
        self.assertEqual(tiers["openai"], "Tier 1")
        self.assertEqual(tiers["jp morgan chase"], "Tier 1.5")
        self.assertEqual(tiers["roblox"], "Tier 2")

    def test_load_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "name": "Example",
                            "kind": "internship",
                            "url": "https://raw.githubusercontent.com/example/repo/main/README.md",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            sources = load_sources(str(path))

        self.assertEqual(sources[0]["name"], "Example")
        self.assertEqual(sources[0]["kind"], "internship")
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
python3 -m unittest tests/test_refresh_jobs.py -v
```

Expected: FAIL with `ModuleNotFoundError` or missing functions.

- [ ] **Step 3: Add source config**

Create `sources.json`:

```json
[
  {
    "name": "Simplify Internships",
    "kind": "internship",
    "url": "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md"
  },
  {
    "name": "Simplify New Grad",
    "kind": "full-time",
    "url": "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md"
  },
  {
    "name": "Vansh New Grad",
    "kind": "full-time",
    "url": "https://raw.githubusercontent.com/vanshb03/New-Grad-2026/dev/README.md"
  },
  {
    "name": "Vansh Internships",
    "kind": "internship",
    "url": "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/dev/README.md"
  },
  {
    "name": "SpeedyApply USA Internships",
    "kind": "internship",
    "url": "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/README.md"
  },
  {
    "name": "SpeedyApply USA New Grad",
    "kind": "full-time",
    "url": "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/main/NEW_GRAD_USA.md"
  }
]
```

- [ ] **Step 4: Add minimal implementation**

Create `scripts/refresh_jobs.py`:

```python
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
```

- [ ] **Step 5: Run tests**

Run:

```bash
python3 -m unittest tests/test_refresh_jobs.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sources.json scripts/refresh_jobs.py tests/test_refresh_jobs.py
git commit -m "feat: add job source config"
```

---

### Task 2: Markdown Parsing And Normalization

**Files:**
- Modify: `scripts/refresh_jobs.py`
- Modify: `tests/test_refresh_jobs.py`

**Interfaces:**
- Consumes:
  - `normalize_company_name(value: str) -> str`
- Produces:
  - `parse_markdown_jobs(markdown: str, source: dict[str, str], tiers: dict[str, str]) -> list[dict[str, str]]`
  - `classify_degree(title: str) -> str`
  - `classify_category(title: str, fallback: str) -> str`

- [ ] **Step 1: Write failing parser tests**

Append to `RefreshJobsTests` in `tests/test_refresh_jobs.py`:

```python
    def test_parse_markdown_jobs_from_table(self):
        markdown = """
### Software Engineering
| Company | Role | Location | Application | Age |
| --- | --- | --- | --- | --- |
| [Apple](https://apple.com) | Software Undergrad Engineering Internships | United States | [Apply](https://jobs.apple.com/1) | 2d |
| Microsoft | Software Engineer New Grad | Redmond, WA | [Apply](https://jobs.microsoft.com/2) | 5d |
"""
        source = {"name": "Example Source", "kind": "internship", "url": "https://example.com/readme.md"}
        tiers = {"apple": "Tier 1", "microsoft": "Tier 1"}

        jobs = parse_markdown_jobs(markdown, source, tiers)

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["company"], "Apple")
        self.assertEqual(jobs[0]["title"], "Software Undergrad Engineering Internships")
        self.assertEqual(jobs[0]["location"], "United States")
        self.assertEqual(jobs[0]["applyUrl"], "https://jobs.apple.com/1")
        self.assertEqual(jobs[0]["jobType"], "internship")
        self.assertEqual(jobs[0]["degreeLevel"], "bachelors")
        self.assertEqual(jobs[0]["companyTier"], "Tier 1")
        self.assertEqual(jobs[0]["source"], "Example Source")

    def test_classify_degree(self):
        self.assertEqual(classify_degree("Software Engineering Masters Internships"), "masters")
        self.assertEqual(classify_degree("Software Undergrad Engineering Internships"), "bachelors")
        self.assertEqual(classify_degree("Backend Engineer"), "unknown")

    def test_classify_category(self):
        self.assertEqual(classify_category("Machine Learning Engineer", "Other"), "AI/ML")
        self.assertEqual(classify_category("Quantitative Developer Intern", "Other"), "Quant")
        self.assertEqual(classify_category("Product Manager New Grad", "Other"), "Product")
        self.assertEqual(classify_category("Backend Software Engineer", "Other"), "Software Engineering")
```

Also add these imports:

```python
from scripts.refresh_jobs import (
    classify_category,
    classify_degree,
    load_company_tiers,
    load_sources,
    normalize_company_name,
    parse_markdown_jobs,
)
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
python3 -m unittest tests/test_refresh_jobs.py -v
```

Expected: FAIL with missing parser functions.

- [ ] **Step 3: Implement parser functions**

Add to `scripts/refresh_jobs.py` above `main()`:

```python
def strip_markdown(value: str) -> str:
    value = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = value.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", value).strip()


def first_markdown_link(value: str) -> str:
    match = re.search(r"\[[^\]]*\]\((https?://[^)]+)\)", value)
    return match.group(1) if match else ""


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
    if any(word in title for word in ("machine learning", "ai", "data science", "research scientist")):
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
```

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m unittest tests/test_refresh_jobs.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/refresh_jobs.py tests/test_refresh_jobs.py
git commit -m "feat: parse upstream job tables"
```

---

### Task 3: Refresh Command And Generated Data

**Files:**
- Modify: `scripts/refresh_jobs.py`
- Modify: `tests/test_refresh_jobs.py`
- Create: `data/jobs.json`

**Interfaces:**
- Consumes:
  - `parse_markdown_jobs(markdown: str, source: dict[str, str], tiers: dict[str, str]) -> list[dict[str, str]]`
- Produces:
  - `dedupe_jobs(jobs: list[dict[str, str]]) -> list[dict[str, str]]`
  - `refresh_jobs(sources_path: str, tiers_path: str, output_path: str) -> dict[str, object]`

- [ ] **Step 1: Write failing dedupe test**

Append to `RefreshJobsTests`:

```python
    def test_dedupe_jobs_prefers_first_source(self):
        jobs = [
            {
                "id": "",
                "company": "Apple",
                "title": "Software Engineer Intern",
                "location": "United States",
                "applyUrl": "https://jobs.apple.com/1",
                "source": "A",
            },
            {
                "id": "",
                "company": "Apple",
                "title": "Software Engineer Intern",
                "location": "United States",
                "applyUrl": "https://jobs.apple.com/1",
                "source": "B",
            },
        ]

        deduped = dedupe_jobs(jobs)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["source"], "A")
        self.assertTrue(deduped[0]["id"])
```

Add `dedupe_jobs` to the import list.

- [ ] **Step 2: Run the failing test**

Run:

```bash
python3 -m unittest tests/test_refresh_jobs.py -v
```

Expected: FAIL with missing `dedupe_jobs`.

- [ ] **Step 3: Implement dedupe and refresh**

Modify `scripts/refresh_jobs.py`:

```python
import hashlib
import urllib.request
from datetime import datetime, timezone
```

Add these functions above `main()`:

```python
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
```

Replace `main()` with:

```python
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="sources.json")
    parser.add_argument("--tiers", default="docs/list.md")
    parser.add_argument("--output", default="data/jobs.json")
    args = parser.parse_args()

    payload = refresh_jobs(args.sources, args.tiers, args.output)
    print(f"Wrote {payload['count']} jobs to {args.output}")
```

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m unittest tests/test_refresh_jobs.py -v
```

Expected: PASS.

- [ ] **Step 5: Generate initial data**

Run:

```bash
python3 scripts/refresh_jobs.py
```

Expected: prints `Wrote N jobs to data/jobs.json` where `N` is greater than 0.

- [ ] **Step 6: Commit**

```bash
git add scripts/refresh_jobs.py tests/test_refresh_jobs.py data/jobs.json
git commit -m "feat: generate normalized job data"
```

---

### Task 4: Static Webapp

**Files:**
- Create: `web/index.html`
- Create: `web/styles.css`
- Create: `web/app.js`

**Interfaces:**
- Consumes: `data/jobs.json` payload with `generatedAt`, `count`, `jobs`
- Produces: Browser UI with search, refresh, filters, sort, source links, and apply links.

- [ ] **Step 1: Create app shell**

Create `web/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Job Repo</title>
    <link rel="stylesheet" href="styles.css">
  </head>
  <body>
    <header class="topbar">
      <div>
        <h1>Job Repo</h1>
        <p id="meta">Loading jobs...</p>
      </div>
      <button id="refreshButton" type="button">Refresh</button>
    </header>

    <main>
      <section class="controls" aria-label="Job filters">
        <input id="searchInput" type="search" placeholder="Search company, role, location">
        <select id="typeFilter">
          <option value="">All types</option>
          <option value="internship">Internships</option>
          <option value="full-time">Full-time</option>
        </select>
        <select id="degreeFilter">
          <option value="">All degrees</option>
          <option value="bachelors">Bachelors</option>
          <option value="masters">Masters</option>
          <option value="unknown">Unknown</option>
        </select>
        <select id="tierFilter">
          <option value="">All tiers</option>
          <option value="Tier 1">Tier 1</option>
          <option value="Tier 1.5">Tier 1.5</option>
          <option value="Tier 2">Tier 2</option>
          <option value="Tier 3">Tier 3</option>
          <option value="Tier 4">Tier 4</option>
          <option value="Unlisted">Unlisted</option>
        </select>
        <select id="sortSelect">
          <option value="tier">Sort: company tier</option>
          <option value="age">Sort: newest</option>
          <option value="company">Sort: company</option>
          <option value="location">Sort: location</option>
        </select>
      </section>

      <section id="summary" class="summary"></section>
      <section id="jobs" class="jobs" aria-live="polite"></section>
    </main>

    <script src="app.js"></script>
  </body>
</html>
```

- [ ] **Step 2: Add styles**

Create `web/styles.css`:

```css
:root {
  color-scheme: light;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f7f8fa;
  color: #1c2024;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

.topbar {
  align-items: center;
  background: #ffffff;
  border-bottom: 1px solid #dfe3e8;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  padding: 20px clamp(16px, 4vw, 40px);
}

h1 {
  font-size: 28px;
  margin: 0 0 4px;
}

p {
  margin: 0;
}

button,
input,
select {
  border: 1px solid #c8d0d9;
  border-radius: 6px;
  font: inherit;
  min-height: 40px;
  padding: 8px 10px;
}

button {
  background: #155dfc;
  color: white;
  cursor: pointer;
}

main {
  margin: 0 auto;
  max-width: 1280px;
  padding: 20px clamp(16px, 4vw, 40px) 40px;
}

.controls {
  display: grid;
  gap: 10px;
  grid-template-columns: minmax(220px, 1fr) repeat(4, minmax(140px, 180px));
  margin-bottom: 16px;
}

.summary {
  color: #5b6470;
  margin-bottom: 12px;
}

.jobs {
  display: grid;
  gap: 10px;
}

.job {
  background: white;
  border: 1px solid #dfe3e8;
  border-radius: 8px;
  display: grid;
  gap: 8px;
  padding: 14px;
}

.jobHeader {
  align-items: start;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.job h2 {
  font-size: 16px;
  margin: 0;
}

.company {
  color: #5b6470;
  font-size: 14px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  background: #eef2f6;
  border-radius: 999px;
  color: #38414d;
  font-size: 12px;
  padding: 4px 8px;
}

.apply {
  color: #155dfc;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
}

@media (max-width: 820px) {
  .topbar,
  .jobHeader {
    align-items: stretch;
    flex-direction: column;
  }

  .controls {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 3: Add frontend logic**

Create `web/app.js`:

```javascript
const state = {
  payload: null,
  jobs: [],
};

const els = {
  meta: document.querySelector("#meta"),
  refreshButton: document.querySelector("#refreshButton"),
  searchInput: document.querySelector("#searchInput"),
  typeFilter: document.querySelector("#typeFilter"),
  degreeFilter: document.querySelector("#degreeFilter"),
  tierFilter: document.querySelector("#tierFilter"),
  sortSelect: document.querySelector("#sortSelect"),
  summary: document.querySelector("#summary"),
  jobs: document.querySelector("#jobs"),
};

const tierRank = {
  "Tier 1": 1,
  "Tier 1.5": 1.5,
  "Tier 2": 2,
  "Tier 3": 3,
  "Tier 4": 4,
  Unlisted: 99,
};

function ageDays(age) {
  const match = String(age || "").match(/(\d+)/);
  return match ? Number(match[1]) : 9999;
}

function matches(job) {
  const query = els.searchInput.value.trim().toLowerCase();
  const haystack = [job.company, job.title, job.location, job.category].join(" ").toLowerCase();
  return (
    (!query || haystack.includes(query)) &&
    (!els.typeFilter.value || job.jobType === els.typeFilter.value) &&
    (!els.degreeFilter.value || job.degreeLevel === els.degreeFilter.value) &&
    (!els.tierFilter.value || job.companyTier === els.tierFilter.value)
  );
}

function sortJobs(jobs) {
  const mode = els.sortSelect.value;
  return [...jobs].sort((a, b) => {
    if (mode === "age") return ageDays(a.age) - ageDays(b.age);
    if (mode === "company") return a.company.localeCompare(b.company);
    if (mode === "location") return a.location.localeCompare(b.location);
    return (tierRank[a.companyTier] || 99) - (tierRank[b.companyTier] || 99) || a.company.localeCompare(b.company);
  });
}

function render() {
  const jobs = sortJobs(state.jobs.filter(matches));
  els.summary.textContent = `${jobs.length.toLocaleString()} of ${state.jobs.length.toLocaleString()} jobs shown`;
  els.jobs.innerHTML = jobs
    .map(
      (job) => `
        <article class="job">
          <div class="jobHeader">
            <div>
              <h2>${escapeHtml(job.title)}</h2>
              <div class="company">${escapeHtml(job.company)} · ${escapeHtml(job.location || "Location unknown")}</div>
            </div>
            <a class="apply" href="${escapeAttribute(job.applyUrl)}" target="_blank" rel="noreferrer">Apply</a>
          </div>
          <div class="tags">
            <span class="tag">${escapeHtml(job.companyTier)}</span>
            <span class="tag">${escapeHtml(job.jobType)}</span>
            <span class="tag">${escapeHtml(job.degreeLevel)}</span>
            <span class="tag">${escapeHtml(job.category)}</span>
            <span class="tag">${escapeHtml(job.source)}</span>
            ${job.age ? `<span class="tag">${escapeHtml(job.age)}</span>` : ""}
          </div>
        </article>
      `
    )
    .join("");
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

function escapeAttribute(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

async function loadJobs() {
  els.meta.textContent = "Loading jobs...";
  const response = await fetch(`../data/jobs.json?ts=${Date.now()}`);
  if (!response.ok) throw new Error(`Failed to load jobs: ${response.status}`);
  state.payload = await response.json();
  state.jobs = state.payload.jobs || [];
  els.meta.textContent = `Generated ${new Date(state.payload.generatedAt).toLocaleString()}`;
  render();
}

for (const el of [els.searchInput, els.typeFilter, els.degreeFilter, els.tierFilter, els.sortSelect]) {
  el.addEventListener("input", render);
}

els.refreshButton.addEventListener("click", () => {
  loadJobs().catch((error) => {
    els.meta.textContent = error.message;
  });
});

loadJobs().catch((error) => {
  els.meta.textContent = error.message;
});
```

- [ ] **Step 4: Serve locally and verify**

Run:

```bash
python3 -m http.server 8000
```

Open `http://localhost:8000/web/`.

Expected:
- Jobs render from `data/jobs.json`.
- Search filters by company/title/location.
- Type, degree, and tier filters update the list.
- Sort control changes ordering.
- Refresh reloads `data/jobs.json`.

- [ ] **Step 5: Commit**

```bash
git add web/index.html web/styles.css web/app.js
git commit -m "feat: add static job browser"
```

---

### Task 5: Scheduled Refresh And Project Docs

**Files:**
- Create: `.github/workflows/refresh-jobs.yml`
- Create: `README.md`

**Interfaces:**
- Consumes: `scripts/refresh_jobs.py`
- Produces: scheduled refresh PR-free commit to `data/jobs.json`

- [ ] **Step 1: Add GitHub Actions workflow**

Create `.github/workflows/refresh-jobs.yml`:

```yaml
name: Refresh jobs

on:
  workflow_dispatch:
  schedule:
    - cron: "17 */6 * * *"

permissions:
  contents: write

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m unittest tests/test_refresh_jobs.py -v
      - run: python scripts/refresh_jobs.py
      - name: Commit updated jobs
        run: |
          if git diff --quiet data/jobs.json; then
            echo "No job changes"
            exit 0
          fi
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add data/jobs.json
          git commit -m "chore: refresh jobs"
          git push
```

- [ ] **Step 2: Add README**

Create `README.md`:

```markdown
# Job Repo

A small static job browser that aggregates internship and new-grad postings from curated GitHub job repositories.

## Sources

- SimplifyJobs/Summer2026-Internships
- SimplifyJobs/New-Grad-Positions
- vanshb03/New-Grad-2026
- vanshb03/Summer2027-Internships
- speedyapply/2027-SWE-College-Jobs

This project attributes upstream sources and stores normalized job data in `data/jobs.json`.

## Refresh Data

```bash
python3 scripts/refresh_jobs.py
```

## Run Locally

```bash
python3 -m http.server 8000
```

Open `http://localhost:8000/web/`.

## Test

```bash
python3 -m unittest tests/test_refresh_jobs.py -v
```
```

- [ ] **Step 3: Run final local checks**

Run:

```bash
python3 -m unittest tests/test_refresh_jobs.py -v
python3 scripts/refresh_jobs.py
python3 -m http.server 8000
```

Expected:
- Tests pass.
- Refresh writes `data/jobs.json`.
- Webapp renders at `http://localhost:8000/web/`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/refresh-jobs.yml README.md
git commit -m "chore: add scheduled refresh docs"
```

---

## Self-Review

- Spec coverage: The plan covers the five chosen sources, refresh generation, static UI, filters, sort, company tier joining, dedupe, and scheduled refresh.
- Placeholder scan: No placeholder markers or unspecified implementation steps remain.
- Type consistency: Function names and payload keys are consistent across parser, refresh, tests, and frontend.
- Ponytail check: The plan uses stdlib Python, vanilla frontend code, one generated JSON file, and no database/backend/npm setup.
