from pathlib import Path

import pytest

from config_manager import ConfigManager, ImmutableConfigError

REPO = Path(__file__).parent.parent


@pytest.fixture
def config(tmp_path: Path) -> ConfigManager:
    (tmp_path / "test.yaml").write_text("a: 1\nb:\n  c: two\n")
    # an absolute config_folder replaces the repo root in the path
    return ConfigManager("test.yaml", config_folder=tmp_path)


def test_find_root():
    assert ConfigManager.find_root() == REPO


def test_relative_folder_is_under_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # fake repo root so the test never reads the real configs/ folder
    monkeypatch.setattr(ConfigManager, "find_root", staticmethod(lambda: tmp_path))
    (tmp_path / "my_configs").mkdir()
    (tmp_path / "my_configs" / "dummy.yaml").write_text("key: value\n")
    config = ConfigManager("dummy.yaml", config_folder="my_configs")
    assert config.path == tmp_path / "my_configs" / "dummy.yaml"
    assert config == {"key": "value"}


def test_loads_values(config: ConfigManager):
    assert config == {"a": 1, "b": {"c": "two"}}
    assert config["b"]["c"] == "two"


def test_empty_file_is_empty_dict(tmp_path: Path):
    (tmp_path / "empty.yaml").write_text("")
    assert ConfigManager("empty.yaml", config_folder=tmp_path) == {}


def test_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        ConfigManager("nope.yaml", config_folder=tmp_path)


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c.__setitem__("a", 2),
        lambda c: c.__delitem__("a"),
        lambda c: c.update(a=2),
        lambda c: c.pop("a"),
        lambda c: c.popitem(),
        lambda c: c.clear(),
        lambda c: c.setdefault("z", 0),
        lambda c: c.__ior__({"a": 2}),
    ],
    ids=["setitem", "delitem", "update", "pop", "popitem", "clear", "setdefault", "ior"],
)
def test_read_only(config: ConfigManager, change):
    with pytest.raises(ImmutableConfigError):
        change(config)
    assert config == {"a": 1, "b": {"c": "two"}}


def test_error_is_type_error(config: ConfigManager):
    with pytest.raises(TypeError):
        config["a"] = 2


def test_reload(config: ConfigManager):
    config.path.write_text("x: 9\n")
    config.reload()
    assert config == {"x": 9}
