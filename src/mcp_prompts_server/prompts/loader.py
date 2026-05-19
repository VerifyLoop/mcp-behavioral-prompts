"""Template loading and rendering for behavioral prompts.

Templates live in `prompts/templates/<name>.md` and use `string.Template`
syntax (`$var` / `${var}`). Missing variables are left intact via
`safe_substitute`, so curly-brace placeholders intended for the model
(e.g. `{file_name}`) are preserved.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template

TEMPLATES_DIR = Path(__file__).parent / "templates"


class TemplateNotFoundError(FileNotFoundError):
    """Raised when a requested template file does not exist."""


@lru_cache(maxsize=None)
def _load_raw(name: str) -> str:
    path = TEMPLATES_DIR / f"{name}.md"
    if not path.is_file():
        raise TemplateNotFoundError(f"Template not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def render_template(name: str, **variables: str) -> str:
    """Load `<name>.md` and substitute `$var` placeholders.

    Unknown placeholders are preserved (safe_substitute), so the rendered
    output can still contain `{...}` style markers meant for the model.
    """
    raw = _load_raw(name)
    return Template(raw).safe_substitute(variables)


def available_templates() -> list[str]:
    """Return the list of template names (without `.md`) on disk."""
    return sorted(p.stem for p in TEMPLATES_DIR.glob("*.md"))
