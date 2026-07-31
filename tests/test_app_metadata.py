"""The AiiDAlab app metadata exists twice for two different consumers:
setup.cfg [aiidalab] (read by the aiidalab package for the home-page tile)
and metadata.json (read by registry tooling). Nothing at runtime checks they
agree, so this test does.
"""
import configparser
import json
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _norm(text):
    """Collapse whitespace: configparser folds multiline values with newlines."""
    return " ".join(str(text).split())


def test_setup_cfg_matches_metadata_json():
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(REPO_ROOT, "setup.cfg"))
    aiidalab = cfg["aiidalab"]
    with open(os.path.join(REPO_ROOT, "metadata.json")) as handle:
        meta = json.load(handle)

    for key in ("title", "description", "authors", "logo", "state"):
        assert _norm(aiidalab[key]) == _norm(meta[key]), key
    categories = [c for c in aiidalab["categories"].split("\n") if c]
    assert categories == meta["categories"]
