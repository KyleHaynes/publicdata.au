import yaml

from .conftest import ROOT

GUARD = "github.repository == 'National-Digital/publicdata.au'"
# Checks that only read the tree, which a fork or a private copy may run.
CHECKS = {
    "ci.yml": "*",
    "clients.yml": {"python", "r"},
    "codeql.yml": "*",
    "dco.yml": "*",
    "dependency-review.yml": "*",
    "pr-title.yml": "*",
    "secrets.yml": "*",
}


def _guarded(jobs: dict, name: str) -> bool:
    """The job's own condition names the repo, or a job it needs does."""
    job = jobs[name]
    if GUARD in str(job.get("if", "")):
        return True
    needs = job.get("needs", [])
    return any(_guarded(jobs, n) for n in ([needs] if isinstance(needs, str) else needs))


def test_every_job_with_side_effects_runs_only_in_the_public_repo():
    unguarded = []
    for f in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        jobs = yaml.safe_load(f.read_text(encoding="utf-8"))["jobs"]
        allowed = CHECKS.get(f.name, set())
        for name in jobs:
            if allowed != "*" and name not in allowed and not _guarded(jobs, name):
                unguarded.append(f"{f.name}: {name}")
    assert unguarded == []


def test_every_fixture_dataset_is_in_the_third_party_notices():
    notices = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    store = ROOT / "pipeline" / "tests" / "fixtures" / "store"
    missing = [
        d.name for d in sorted(store.iterdir()) if d.is_dir() and f"`{d.name}`" not in notices
    ]
    assert missing == []
