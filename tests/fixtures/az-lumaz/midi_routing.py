"""Explicit LUMAZ JACK MIDI routing and physical-port discovery."""
from __future__ import annotations
import json, os, subprocess
from pathlib import Path

MIDI_SETTINGS_PATH = Path("/root/lumaz/config/midi-settings.json")
DEFAULT_VIDEO_INPUTS = ("ttymidi:MIDI_in", "system:midi_capture_2")
DEFAULT_LIGHT_INPUTS = ()
DEFAULT_OUTPUT = "ttymidi:MIDI_out"

def normalize_midi_settings(payload):
    payload = payload if isinstance(payload, dict) else {}
    def clean(value):
        return list(dict.fromkeys(str(port or "").strip() for port in value if str(port or "").strip())) if isinstance(value, list) else []
    # Existing shared selections retain their former video-control behaviour.
    legacy = clean(payload.get("input_ports", []))
    output = str(payload.get("output_port") or "").strip()
    return {"version": 2, "video_input_ports": clean(payload.get("video_input_ports", legacy)),
            "light_input_ports": clean(payload.get("light_input_ports", DEFAULT_LIGHT_INPUTS)),
            "output_port": output, "midi_through": bool(payload.get("midi_through", True))}

def load_midi_settings(path=MIDI_SETTINGS_PATH):
    path = Path(path)
    try:
        return normalize_midi_settings(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        # Safe migration: only direct physical ports, never ZynMidiRouter fan-in.
        return normalize_midi_settings({"video_input_ports": list(DEFAULT_VIDEO_INPUTS), "light_input_ports": list(DEFAULT_LIGHT_INPUTS),
                                        "output_port": DEFAULT_OUTPUT, "midi_through": True})

def save_midi_settings(settings, path=MIDI_SETTINGS_PATH):
    path = Path(path); normalized = normalize_midi_settings(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return normalized

def jack_physical_ports(command=("jack_lsp", "-A", "-p")):
    """Return physical JACK MIDI sources and destinations for the settings UI.

    Zynthian can expose many router ports.  One second is not enough for
    jack_lsp to enumerate them on a Pi, which used to turn a slow response
    into the false message “NO PHYSICAL MIDI … DETECTED”.
    """
    try:
        output = subprocess.run(command, check=False, text=True, capture_output=True,
                                timeout=4.0).stdout
    except (OSError, subprocess.SubprocessError):
        return {"inputs": [], "outputs": []}
    result, current, aliases, properties = {"inputs": [], "outputs": []}, None, [], ""
    def finish():
        if not current or "physical" not in properties:
            return
        # Some Zynthian JACK builds omit the “8 bit raw midi” line from
        # jack_lsp -A -p.  Identify the physical MIDI endpoints from their
        # standard port names / aliases instead of rejecting valid hardware.
        alias_text = " ".join(aliases).casefold()
        is_midi = (current.startswith(("system:midi_", "ttymidi:")) or
                   "midi" in alias_text)
        if not is_midi or current.startswith("a2j:Midi Through"):
            return
        # JACK exposes a technical port alias first and the human device name last.
        label = aliases[-1] if aliases else current
        entry = {"port": current, "label": label}
        if "output" in properties:
            result["inputs"].append(entry)
        if "input" in properties:
            result["outputs"].append(entry)
    for line in output.splitlines() + [""]:
        if line and not line.startswith((" ", "\t")):
            finish(); current, aliases, properties = line.strip(), [], ""
        elif line.strip().startswith("properties:"):
            properties += " " + line.strip()
        elif line.startswith((" ", "\t")) and current:
            value = line.strip()
            if "bit raw midi" in value:
                properties += " " + value
            elif value and not value.startswith("properties:"):
                aliases.append(value)
        elif not line:
            finish(); current, aliases, properties = None, [], ""
    for key in result:
        result[key].sort(key=lambda item: (item["label"].casefold(), item["port"]))
    return result
