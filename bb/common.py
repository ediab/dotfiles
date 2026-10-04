"""Portable BB preferences: intentionally exclude auth, routing, and runtime state."""
import json
import os
import subprocess

GENERAL_KEYS = (
    "showKeyboardHints", "steerActiveThreadOnEnter", "confirmThreadArchive",
    "showDiagnosticEvents", "providerOrder", "defaultProviderId", "streamerMode",
    "allowFastServiceTier", "telemetryEnabled", "managedBranchPrefix",
    "showUnhandledProviderEvents",
)
UI_KEYS = (
    "sidebar.organizationMode", "sidebar.threadGrouping.environment",
    "sidebar.chronologicalSort", "sidebar.sortDirection", "sidebar.sectionOrder",
    "sidebar.manualSectionOrder", "sidebar.machineSectionOrder",
    "sidebar.footerOrder", "sidebar.hiddenFooterItems", "sidebar.pluginPanelOrder",
    "sidebar.visiblePluginPanels", "sidebar.navigationProvider",
    "sidebar.headerProvider", "sidebar.threadListProvider",
)


def run_bb(binary, server, args, *, capture=True):
    env = os.environ.copy()
    for key in ("BB_CLI", "BB_PROJECT_ID", "BB_THREAD_ID", "BB_ENVIRONMENT_ID"):
        env.pop(key, None)
    env["BB_SERVER_URL"] = server
    result = subprocess.run([binary, *args], env=env, check=True,
                            text=True, capture_output=capture)
    return json.loads(result.stdout) if capture else None


def portable_preferences(settings, ui):
    appearance = settings["appearance"]
    return {
        "general": {k: settings["generalSettings"][k] for k in GENERAL_KEYS
                    if k in settings["generalSettings"]},
        "appearance": {k: appearance[k] for k in ("themeId", "faviconColor")},
        "ui": {k: ui["preferences"][k]["value"] for k in UI_KEYS
               if k in ui["preferences"]},
    }


def preference_commands(preferences):
    if set(preferences) != {"general", "appearance", "ui"}:
        raise ValueError("Expected only general, appearance, and ui preferences")
    if set(preferences["general"]) - set(GENERAL_KEYS):
        raise ValueError("Unsupported or non-portable general setting")
    if set(preferences["ui"]) - set(UI_KEYS):
        raise ValueError("Unsupported or non-portable UI preference")
    if set(preferences["appearance"]) != {"themeId", "faviconColor"}:
        raise ValueError("Expected themeId and faviconColor only")
    commands = []
    for key, value in preferences["general"].items():
        commands.append(["settings", "general", key, cli_value(value)])
    commands.append(["theme", "set", preferences["appearance"]["themeId"]])
    commands.append(["theme", "favicon", "set", preferences["appearance"]["faviconColor"]])
    for key, value in preferences["ui"].items():
        commands.append(["settings", "ui", "set", key, cli_value(value)])
    return commands


def cli_value(value):
    return value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))
