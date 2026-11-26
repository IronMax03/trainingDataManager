from fnmatch import fnmatch
from pathlib import Path

import huggingface_hub
import pytest

import utils.HF_Interface as hf

CONFIG = {
    "HF_REPO_ADDRESS": "owner/dataset",
    "HF_RAW_PATH": "raw_signals/",
    "HF_PROCESSED_PATH": "Processed_signals/",
    "LOCAL_DATA_PATH": "./local_dataset",
}
REPO_FILES = ["raw_signals/a.edf", "Processed_signals/b.parquet", "README.md"]


@pytest.fixture
def interface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> hf.Interface:
    # fake config and .env so the tests never read real files or tokens
    class FakeConfig(dict):
        find_root = staticmethod(lambda: tmp_path)

    monkeypatch.setattr(hf, "ConfigManager", lambda name: FakeConfig(CONFIG))
    monkeypatch.setattr(hf, "dotenv_values", lambda path: {"HUGGINGFACE_READ_TOKEN": "hf_test"})
    return hf.Interface()


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Fake snapshot_download: writes matching repo files to local_dir/<repo path>, like the real one."""
    calls = []

    def fake_snapshot_download(**kwargs):
        calls.append(kwargs)
        patterns = kwargs.get("allow_patterns") or ["*"]
        for name in REPO_FILES:
            if any(fnmatch(name, p) for p in patterns):
                target = Path(kwargs["local_dir"]) / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("data")
        return str(kwargs["local_dir"])

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot_download)
    return calls


def downloaded(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def test_init_reads_token(interface: hf.Interface):
    assert interface.read_token == "hf_test"
    assert interface.config["HF_REPO_ADDRESS"] == "owner/dataset"


def test_download_processed(interface: hf.Interface, calls: list[dict], tmp_path: Path):
    interface.download_processed()
    assert calls[0]["repo_id"] == "owner/dataset"
    assert calls[0]["repo_type"] == "dataset"
    assert calls[0]["token"] == "hf_test"
    assert downloaded(tmp_path / "local_dataset") == {"Processed_signals/b.parquet"}


def test_download_raws(interface: hf.Interface, calls: list[dict], tmp_path: Path):
    interface.download_raws()
    assert calls[0]["token"] == "hf_test"
    assert downloaded(tmp_path / "local_dataset") == {"raw_signals/a.edf"}


def test_download_raws_replaces_old_raws(interface: hf.Interface, calls: list[dict], tmp_path: Path):
    old = tmp_path / "local_dataset" / "raw_signals" / "old.edf"
    old.parent.mkdir(parents=True)
    old.write_text("old")
    interface.download_raws()
    assert downloaded(tmp_path / "local_dataset") == {"raw_signals/a.edf"}


def test_download_all(interface: hf.Interface, calls: list[dict], tmp_path: Path):
    interface.download_all()
    assert calls[0]["token"] == "hf_test"
    assert downloaded(tmp_path / "local_dataset") == set(REPO_FILES)


def test_download_file(interface: hf.Interface, monkeypatch: pytest.MonkeyPatch):
    calls = []
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", lambda **kwargs: calls.append(kwargs))
    interface.download_file("raw_signals/a.edf")
    assert calls == [{
        "repo_id": "owner/dataset",
        "filename": "raw_signals/a.edf",
        "repo_type": "dataset",
        "token": "hf_test",
    }]
