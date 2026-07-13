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
