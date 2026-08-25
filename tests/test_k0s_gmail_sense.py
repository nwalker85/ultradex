"""Gmail Sense stays off the shared API/worker pods; CronJob owns the sweep."""
from pathlib import Path

MANIFEST = Path(__file__).parents[1] / "deploy" / "k0s" / "ccc.yaml"


def test_cronjob_runs_sense_cli_with_dedicated_secret():
    text = MANIFEST.read_text()
    assert "kind: CronJob" in text
    assert "name: gmail-sense" in text
    assert "python\", \"-m\", \"cli.sense_gmail\"" in text or (
        '"python", "-m", "cli.sense_gmail"' in text
    )
    assert "secretRef:\n                    name: gmail-sense" in text
    api_block = text.split("name: api\n", 1)[1].split("name: worker\n", 1)[0]
    assert "gmail-sense" not in api_block
    assert "GMAIL_" not in api_block


def test_cronjob_runs_dex_sense_from_shared_ultradex_secret():
    text = MANIFEST.read_text()
    assert "name: dex-sense" in text
    assert '"python", "-m", "cli.sense_dex"' in text
    assert "47 */4 * * *" in text
