"""Load YAML configs (reference: agentic_rag_contracts)."""
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent


def load_yaml(path: str) -> dict:
    try:
        import yaml
    except ImportError:
        return {}
    p = Path(path) if Path(path).is_absolute() else _BASE / path
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_prompt(path: str) -> str:
    """Load a markdown prompt file."""
    p = Path(path) if Path(path).is_absolute() else _BASE / path
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8").strip()


def get_agents_config() -> dict:
    """Load agents.yaml; used by runtime for agent definition."""
    return load_yaml("configs/agents.yaml")


def get_models_config() -> dict:
    """Load models.yaml; used by runtime for LLM settings."""
    return load_yaml("configs/models.yaml")
