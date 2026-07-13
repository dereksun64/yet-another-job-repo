# Final Review Fix Report

## Fixed findings

- Continuation-company markers (`↳` and `⤷`) now inherit the preceding real company, retaining tier lookup and dedupe behavior.
- Apply-link parsing now prefers nested Markdown destinations and anchor `href` values; malformed anchors no longer fall through to nested image URLs.
- `job_key()` removes `utm_*` and `ref` tracking parameters while retaining meaningful query parameters. The parser still emits only rows with an application URL; URL-free fallback dedupe remains covered for callers.
- Refresh aborts before output writes when any configured source parses zero jobs.
- Refresh preserves `generatedAt` when jobs, count, and source counts are unchanged.
- Product classification uses a word boundary; controls have accessible labels; the scheduled workflow has concurrency protection.

## Generated data

`data/jobs.json` was regenerated from the configured upstream sources. It contains 1,631 jobs; all six source counts are nonzero; no company marker rows or image apply URLs remain.

## Verification

- `python3 -m unittest tests/test_refresh_jobs.py -v` passed: 19 tests.
- `node --check web/app.js` passed.
- `python3 scripts/refresh_jobs.py --output /tmp/jobs-final-fix.json` passed with network access.
- `python3 scripts/refresh_jobs.py` passed with network access.
- Generated-data invariants and `git diff --check` passed.
