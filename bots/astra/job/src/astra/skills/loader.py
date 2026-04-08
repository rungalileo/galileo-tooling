from pathlib import Path

SKILLS_DIR = Path(__file__).parent


def load_skill(name: str) -> str:
    path = (SKILLS_DIR / f"{name}.md").resolve()
    if not path.is_relative_to(SKILLS_DIR.resolve()):
        raise ValueError(f"Invalid skill name: {name!r}")
    return path.read_text()
