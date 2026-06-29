"""Tests for the provisioning helpers (no AiiDA profile required)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiida_qe_converse.provision import discover_pseudo_families, default_pseudo_dir


def _make_pseudo_tree(tmp_path):
    for fam, elements in (("gipaw_PBE", ["O", "Si"]), ("gipaw_PBEsol", ["O"])):
        d = tmp_path / fam
        d.mkdir()
        for el in elements:
            (d / f"{el}.upf").write_text("dummy upf")
    # a non-gipaw dir and an empty gipaw dir should be ignored
    (tmp_path / "sssp").mkdir()
    (tmp_path / "sssp" / "O.upf").write_text("x")
    (tmp_path / "gipaw_empty").mkdir()


def test_discover_pseudo_families(tmp_path):
    _make_pseudo_tree(tmp_path)
    fams = discover_pseudo_families(tmp_path)
    assert set(fams) == {"gipaw_PBE", "gipaw_PBEsol"}  # non-gipaw + empty skipped
    assert [p.name for p in fams["gipaw_PBE"]] == ["O.upf", "Si.upf"]
    assert [p.name for p in fams["gipaw_PBEsol"]] == ["O.upf"]


def test_discover_missing_dir(tmp_path):
    assert discover_pseudo_families(tmp_path / "nope") == {}


def test_default_pseudo_dir_env(monkeypatch, tmp_path):
    monkeypatch.setenv("AIIDA_QE_CONVERSE_PSEUDO_DIR", str(tmp_path))
    assert default_pseudo_dir() == tmp_path


def test_default_pseudo_dir_repo_fallback(monkeypatch):
    # no env, and the known container path does not exist on the test host ->
    # falls back to the repo's pseudos/ dir next to the package.
    monkeypatch.delenv("AIIDA_QE_CONVERSE_PSEUDO_DIR", raising=False)
    d = default_pseudo_dir()
    assert d.name == "pseudos"
    # the repo ships gipaw_PBE / gipaw_PBEsol there
    assert (d / "gipaw_PBE").is_dir()
