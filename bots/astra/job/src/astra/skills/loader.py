from pathlib import Path

SKILLS_DIR = Path(__file__).parent


def load_skill(name: str) -> str:
    return (SKILLS_DIR / f"{name}.md").read_text()
