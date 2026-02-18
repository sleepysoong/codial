from __future__ import annotations

from codial_discord.command_specs import build_application_commands


def _find_command(name: str) -> dict[str, object]:
    commands = build_application_commands()
    for command in commands:
        if command.get("name") == name:
            return command
    raise AssertionError(f"커맨드를 찾지 못했어요: {name}")


def test_command_specs_include_expected_names() -> None:
    commands = build_application_commands()
    names = {command["name"] for command in commands}
    assert names == {
        "ask",
        "end",
        "provider",
        "model",
        "mcp",
        "subagent",
        "rules_list",
        "rules_add",
        "rules_remove",
        "규칙목록",
        "규칙추가",
        "규칙제거",
    }


def test_provider_command_only_allows_copilot_provider() -> None:
    command = _find_command("provider")
    options = command.get("options")
    assert isinstance(options, list)
    provider_option = options[0]
    assert isinstance(provider_option, dict)
    choices = provider_option.get("choices")
    assert choices == [{"name": "github-copilot-sdk", "value": "github-copilot-sdk"}]


def test_rules_remove_command_has_min_index_option() -> None:
    command = _find_command("rules_remove")
    options = command.get("options")
    assert isinstance(options, list)
    index_option = options[0]
    assert isinstance(index_option, dict)
    assert index_option.get("name") == "index"
    assert index_option.get("type") == 4
    assert index_option.get("min_value") == 1
