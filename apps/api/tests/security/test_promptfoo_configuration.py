from pathlib import Path
from typing import Any

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
PROMPTFOO_ROOT = REPOSITORY_ROOT / "evaluation" / "promptfoo"
MESH_PROVIDER = {
    "id": "openai:chat:openai/gpt-5.4-mini",
    "label": "mesh-openai-gpt-5.4-mini",
    "config": {
        "apiBaseUrl": "https://api.meshapi.ai/v1",
        "apiKeyEnvar": "MESH_API_KEY",
        "useDefaultApiKey": False,
        "omitDefaults": True,
    },
}


def load_config(name: str) -> dict[str, Any]:
    value = yaml.safe_load((PROMPTFOO_ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("Promptfoo configuration must be a mapping")
    return value


def test_quick_promptfoo_lane_has_no_model_or_network_provider() -> None:
    config = load_config("promptfooconfig.quick.yaml")

    assert config["providers"] == [
        {"id": "file://policy_provider.py", "label": "finpilot-production-input-policy"}
    ]
    assert config["sharing"] is False
    assert config["writeLatestResults"] is False


def test_model_based_promptfoo_roles_use_mesh_only() -> None:
    config = load_config("promptfooconfig.redteam.yaml")

    assert config["defaultTest"]["options"]["provider"] == MESH_PROVIDER
    assert config["redteam"]["provider"] == MESH_PROVIDER
    assert config["targets"] == [
        {"id": "file://policy_provider.py", "label": "finpilot-production-input-policy"}
    ]
    assert config["sharing"] is False
    assert config["writeLatestResults"] is False


def test_redteam_avoids_promptfoo_remote_only_plugins_and_strategies() -> None:
    config = load_config("promptfooconfig.redteam.yaml")
    plugin_ids = {
        plugin if isinstance(plugin, str) else plugin["id"]
        for plugin in config["redteam"]["plugins"]
    }
    strategy_ids = {
        strategy if isinstance(strategy, str) else strategy["id"]
        for strategy in config["redteam"]["strategies"]
    }

    assert plugin_ids == {
        "prompt-extraction",
        "pii:direct",
        "rbac",
        "excessive-agency",
        "tool-discovery",
        "policy",
    }
    assert strategy_ids == {"basic", "jailbreak-templates", "base64", "rot13", "leetspeak"}
