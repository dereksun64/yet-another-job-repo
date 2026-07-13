import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.refresh_jobs import (
    classify_category,
    classify_degree,
    dedupe_jobs,
    load_company_tiers,
    load_sources,
    normalize_company_name,
    parse_markdown_jobs,
    refresh_jobs,
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

    def test_parse_markdown_jobs_accepts_direct_application_url(self):
        markdown = """
### Software Engineering
| Company | Role | Location | Application |
| --- | --- | --- | --- |
| Example Co | Software Engineer | Remote | https://jobs.example.com/1 |
"""
        source = {"name": "Example Source", "kind": "internship", "url": "https://example.com/readme.md"}

        jobs = parse_markdown_jobs(markdown, source, {})

        self.assertEqual(jobs[0]["applyUrl"], "https://jobs.example.com/1")

    def test_parse_markdown_jobs_stops_direct_url_before_html_tail(self):
        markdown = """
### Software Engineering
| Company | Role | Location | Application |
| --- | --- | --- | --- |
| Example Co | Software Engineer | Remote | <a href="https://jobs.example.com/1?x=1"><img src="logo.png"></a> |
"""
        source = {"name": "Example Source", "kind": "internship", "url": "https://example.com/readme.md"}

        jobs = parse_markdown_jobs(markdown, source, {})

        self.assertEqual(jobs[0]["applyUrl"], "https://jobs.example.com/1?x=1")

    def test_parse_markdown_jobs_accepts_simplify_html_table(self):
        markdown = """
## Software Engineering Internship Roles
<table>
<tr><th>Company</th><th>Role</th><th>Location</th><th>Application</th><th>Age</th></tr>
<tr><td><strong>Example Co</strong></td><td>Software Engineer Intern</td><td>Remote</td><td><a href="https://jobs.example.com/1?x=1"><img src="logo.png"></a></td><td>1d</td></tr>
</table>
"""
        source = {"name": "Simplify Internships", "kind": "internship", "url": "https://example.com/readme.md"}

        jobs = parse_markdown_jobs(markdown, source, {})

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["company"], "Example Co")
        self.assertEqual(jobs[0]["category"], "Software Engineering")
        self.assertEqual(jobs[0]["applyUrl"], "https://jobs.example.com/1?x=1")

    def test_classify_category_requires_ai_word_boundary(self):
        self.assertEqual(classify_category("Maintenance Engineer", "Other"), "Other")

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

    def test_dedupe_jobs_uses_normalized_fields_without_application_url(self):
        jobs = [
            {"id": "", "company": "Example/Co", "title": "Software Engineer", "location": "New York, NY"},
            {"id": "", "company": "example co", "title": "software engineer", "location": "new york ny"},
        ]

        deduped = dedupe_jobs(jobs)

        self.assertEqual(len(deduped), 1)
        self.assertTrue(deduped[0]["id"])

    @patch("scripts.refresh_jobs.fetch_text")
    def test_refresh_jobs_writes_parsed_jobs_from_upstream_html_link(self, fetch_text):
        fetch_text.return_value = """
### Software Engineering
| Company | Role | Location | Application |
| --- | --- | --- | --- |
| Example Co | Software Engineer | Remote | <a href="https://jobs.example.com/1?x=1"><img src="logo.png"></a> |
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources_path = root / "sources.json"
            tiers_path = root / "tiers.md"
            output_path = root / "jobs.json"
            sources_path.write_text(
                json.dumps([{"name": "Example", "kind": "internship", "url": "https://example.com/jobs.md"}]),
                encoding="utf-8",
            )
            tiers_path.write_text("## Tier 1\n\n- Example Co\n", encoding="utf-8")

            payload = refresh_jobs(str(sources_path), str(tiers_path), str(output_path))
            persisted = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(fetch_text.call_count, 1)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(persisted["sourceCounts"], {"Example": 1})
        self.assertEqual(persisted["jobs"][0]["applyUrl"], "https://jobs.example.com/1?x=1")
        self.assertEqual(persisted["jobs"][0]["companyTier"], "Tier 1")
