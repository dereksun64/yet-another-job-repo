# Job Repo

A small static job browser that aggregates internship and new-grad postings from curated GitHub job repositories.

## Sources

- SimplifyJobs/Summer2026-Internships
- SimplifyJobs/New-Grad-Positions
- vanshb03/New-Grad-2026
- vanshb03/Summer2027-Internships
- speedyapply/2027-SWE-College-Jobs

This project attributes upstream sources and stores normalized job data in `data/jobs.json`.
The v1 parser emits only rows with an application URL; URL-free rows are skipped, while the dedupe fallback remains available for callers that provide them.

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
