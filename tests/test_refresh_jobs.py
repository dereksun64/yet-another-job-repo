import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.refresh_jobs import (
    canonical_apply_url,
    classify_category,
    classify_degree,
    dedupe_jobs,
    first_markdown_link,
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
        self.assertEqual(classify_category("Production Engineer", "Other"), "Other")
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

    def test_parse_markdown_jobs_prefers_outer_markdown_link_over_image(self):
        markdown = """
### Software Engineering
| Company | Role | Location | Application |
| --- | --- | --- | --- |
| Example Co | Software Engineer | Remote | [![Apply](https://example.com/apply.png)](https://jobs.example.com/1) |
"""
        source = {"name": "Example Source", "kind": "internship", "url": "https://example.com/readme.md"}

        jobs = parse_markdown_jobs(markdown, source, {})

        self.assertEqual(jobs[0]["applyUrl"], "https://jobs.example.com/1")

    def test_first_markdown_link_returns_nested_image_outer_destination(self):
        value = "[![Apply](https://cdn.example.com/apply.png)](https://jobs.example.com/123)"

        self.assertEqual(first_markdown_link(value), "https://jobs.example.com/123")

    def test_parse_markdown_jobs_skips_nested_image_with_relative_outer_destination(self):
        markdown = """
### Software Engineering
| Company | Role | Location | Application |
| --- | --- | --- | --- |
| Example Co | Software Engineer | Remote | [![Apply](https://cdn.example.com/apply.png)](/jobs/123) |
"""
        source = {"name": "Example Source", "kind": "internship", "url": "https://example.com/readme.md"}

        self.assertEqual(parse_markdown_jobs(markdown, source, {}), [])

    def test_first_markdown_link_rejects_relative_nested_outer_with_parenthesized_image(self):
        value = "[![Apply](https://cdn.example.com/badge(1).png)](/jobs/123)"

        self.assertEqual(first_markdown_link(value), "")

    def test_first_markdown_link_rejects_wrapped_relative_nested_outer(self):
        value = '<span>[![Apply](https://cdn.example.com/apply.png)](/jobs/123)</span>'

        self.assertEqual(first_markdown_link(value), "")

    def test_first_markdown_link_rejects_malformed_or_non_http_nested_outer_destination(self):
        image = "https://cdn.example.com/apply.png"

        self.assertEqual(first_markdown_link(f"[![Apply]({image})](javascript:void(0))"), "")
        self.assertEqual(first_markdown_link(f"[![Apply]({image})](https:/.jobs.example.com/123)"), "")
        self.assertEqual(first_markdown_link(f"[![Apply]({image})](https://[)"), "")
        self.assertEqual(first_markdown_link(f"[![Apply]({image})](https://example.com:bad/path)"), "")

    def test_first_markdown_link_rejects_malformed_markdown_and_bare_urls(self):
        self.assertEqual(first_markdown_link("[Apply](https://[)"), "")
        self.assertEqual(first_markdown_link("[Apply](https://example.com:bad/path)"), "")
        self.assertEqual(first_markdown_link("https://["), "")
        self.assertEqual(first_markdown_link("https://example.com:bad/path"), "")

    def test_parse_markdown_jobs_skips_malformed_anchor_instead_of_using_its_image(self):
        markdown = """
### Software Engineering
| Company | Role | Location | Application |
| --- | --- | --- | --- |
| Example Co | Software Engineer | Remote | <a href="https:/.jobs.example.com/1"><img src="https://example.com/apply.png"></a> |
"""
        source = {"name": "Example Source", "kind": "internship", "url": "https://example.com/readme.md"}

        self.assertEqual(parse_markdown_jobs(markdown, source, {}), [])

    def test_parse_markdown_jobs_inherits_company_from_continuation_rows(self):
        markdown = """
### Software Engineering
| Company | Role | Location | Application |
| --- | --- | --- | --- |
| [Apple](https://apple.com) | Software Engineer Intern | Remote | [Apply](https://jobs.apple.com/1) |
| ↳ | Software Engineer Intern | Remote | [Apply](https://jobs.apple.com/2) |
"""
        source = {"name": "Example Source", "kind": "internship", "url": "https://example.com/readme.md"}

        jobs = parse_markdown_jobs(markdown, source, {"apple": "Tier 1"})

        self.assertEqual([job["company"] for job in jobs], ["Apple", "Apple"])
        self.assertTrue(all(job["companyTier"] == "Tier 1" for job in jobs))

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

    def test_dedupe_jobs_ignores_tracking_parameters_in_apply_urls(self):
        jobs = [
            {"id": "", "company": "Example", "title": "Engineer", "location": "Remote", "applyUrl": "https://jobs.example.com/1?gh_jid=123&utm_source=source&ref=feed"},
            {"id": "", "company": "Example", "title": "Engineer", "location": "Remote", "applyUrl": "https://jobs.example.com/1?gh_jid=123"},
        ]

        self.assertEqual(canonical_apply_url(jobs[0]["applyUrl"]), "https://jobs.example.com/1?gh_jid=123")
        self.assertEqual(len(dedupe_jobs(jobs)), 1)

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

    @patch("scripts.refresh_jobs.fetch_text")
    def test_refresh_jobs_does_not_overwrite_output_when_a_source_parses_zero_rows(self, fetch_text):
        fetch_text.side_effect = [
            """
| Company | Role | Location | Application |
| --- | --- | --- | --- |
| Example | Software Engineer | Remote | [Apply](https://jobs.example.com/1) |
""",
            "no job table here",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources_path = root / "sources.json"
            tiers_path = root / "tiers.md"
            output_path = root / "jobs.json"
            sources_path.write_text(json.dumps([
                {"name": "First", "kind": "internship", "url": "https://example.com/first"},
                {"name": "Second", "kind": "internship", "url": "https://example.com/second"},
            ]), encoding="utf-8")
            tiers_path.write_text("", encoding="utf-8")
            output_path.write_text("existing output", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Second"):
                refresh_jobs(str(sources_path), str(tiers_path), str(output_path))

            self.assertEqual(output_path.read_text(encoding="utf-8"), "existing output")

    @patch("scripts.refresh_jobs.fetch_text")
    def test_refresh_jobs_preserves_generated_at_when_content_is_unchanged(self, fetch_text):
        fetch_text.return_value = """
| Company | Role | Location | Application |
| --- | --- | --- | --- |
| Example | Software Engineer | Remote | [Apply](https://jobs.example.com/1) |
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources_path = root / "sources.json"
            tiers_path = root / "tiers.md"
            output_path = root / "jobs.json"
            sources_path.write_text(json.dumps([{"name": "Example", "kind": "internship", "url": "https://example.com/jobs"}]), encoding="utf-8")
            tiers_path.write_text("", encoding="utf-8")

            first = refresh_jobs(str(sources_path), str(tiers_path), str(output_path))
            persisted = json.loads(output_path.read_text(encoding="utf-8"))
            persisted["generatedAt"] = "2020-01-01T00:00:00+00:00"
            output_path.write_text(json.dumps(persisted), encoding="utf-8")
            second = refresh_jobs(str(sources_path), str(tiers_path), str(output_path))

        self.assertNotEqual(first["generatedAt"], second["generatedAt"])
        self.assertEqual(second["generatedAt"], "2020-01-01T00:00:00+00:00")
