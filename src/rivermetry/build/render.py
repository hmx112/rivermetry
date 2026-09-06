from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def env() -> Environment:
    return Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render(template: str, **context) -> str:
    return env().get_template(template).render(**context)


def write_page(root: Path, public_path: str, content: str) -> Path:
    target = root / public_path.strip("/") / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return target
