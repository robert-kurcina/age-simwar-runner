import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "campaigns/civic-recovery/campaign.json"


class CampaignCliTest(unittest.TestCase):
    def test_full_campaign(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a, b, c, baseline = (root / name for name in ("a.json", "b.json", "c.json", "baseline.json"))

            def cli(*args, ok=True):
                result = subprocess.run([sys.executable, str(ROOT / "play.py"),
                                         *map(str, args)], capture_output=True, text=True)
                if not ok:
                    self.assertNotEqual(result.returncode, 0)
                    return
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)

            catalog = cli("list", MANIFEST)
            self.assertEqual(sum(len(g["scenarios"]) for g in catalog["groups"]), 4)
            cli("start", MANIFEST, "service-restoration", a)
            cli("start", MANIFEST, "community-assistance", b, "--from-session", a, ok=False)
            self.assertFalse(b.exists())
            before = a.read_bytes()
            cli("inspect", a, "--actor", "coordinator")
            self.assertEqual(before, a.read_bytes())
            cli("submit", a, "restore_service_center", "--actor", "coordinator")
            cli("advance", a, "--actor", "coordinator")
            cli("finish", a)
            self.assertEqual(cli("report", a)["values"]["open_service_centers"], 3)
            cli("start", MANIFEST, "service-restoration", baseline)
            cli("finish", baseline)
            self.assertEqual(cli("compare", baseline, a)["right_minus_left"]["values"]["open_service_centers"], 1)
            cli("start", MANIFEST, "community-assistance", b, "--from-session", a)
            self.assertEqual(cli("inspect", b, "--actor", "coordinator")["values"]["open_service_centers"], 3)
            cli("submit", b, "deliver_aid", "--actor", "coordinator")
            cli("finish", b)
            cli("start", MANIFEST, "civic-agreement", c, "--from-session", b)
            self.assertEqual(cli("inspect", c, "--actor", "council_a")["values"]["households_assisted"], 30)
            cli("submit", c, "join_council_a", "--actor", "council_a")
            cli("advance", c)
            cli("submit", c, "join_council_b", "--actor", "council_b")
            self.assertTrue(cli("finish", c)["complete"])
            self.assertIn("objectives", cli("report", c))
            before = c.read_bytes()
            cli("submit", c, "join_council_a", "--actor", "council_a", ok=False)
            cli("start", MANIFEST, "civic-agreement", c, ok=False)
            self.assertEqual(before, c.read_bytes())
            cli("compare", a, c, ok=False)
