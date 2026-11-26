"""Read-only YAML config loader."""

from pathlib import Path
from typing import Any, NoReturn


class ImmutableConfigError(TypeError):
    """Raised when trying to modify a read-only config."""


class ConfigManager(dict):
    """Read-only dict loaded from ``<repo root>/<config_folder>/<name>``.

    Edit the YAML file and call ``reload()`` to change values.
    """

    def __init__(self, name: str, config_folder: str | Path = "configs", autosave: bool = False) -> None:
        super().__init__()
        self.name = name
        self.autosave = autosave
        self.path = self.find_root() / config_folder / name
        self.reload()

    @staticmethod
    def find_root(markers: tuple[str, ...] = (".git", ".github", "pyproject.toml")) -> Path:
        """Return the first parent folder of this file that contains a marker."""
        path = Path(__file__).resolve()
        for parent in path.parents:
            if any((parent / m).exists() for m in markers):
                return parent
        raise FileNotFoundError("Repo root not found")

    def reload(self) -> None:
        """Re-read the YAML file, replacing the current contents."""
        from yaml import safe_load

        with open(self.path) as f:
            data = safe_load(f) or {}
        # super() bypasses the blocked methods below
        super().clear()
        super().update(data)

    def _readonly(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise ImmutableConfigError(f"Config '{self.name}' is read-only; edit {self.path} and call reload()")

    def __setitem__(self, key: str, value: Any) -> NoReturn:
        raise ImmutableConfigError(f"Cannot set '{key}': config '{self.name}' is read-only")

    def __delitem__(self, key: str) -> NoReturn:
        raise ImmutableConfigError(f"Cannot delete '{key}': config '{self.name}' is read-only")

    # dict's built-in methods don't call __setitem__, so block them explicitly
    update = pop = popitem = clear = setdefault = __ior__ = _readonly
