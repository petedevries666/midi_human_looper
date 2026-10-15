"""Persistent, per-view audio routing for LUMAZ's shared MPV instance."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

AUDIO_SETTINGS_PATH = Path("/root/lumaz/config/audio-playback.json")
VIEWS = ("sampler", "editor", "showcase")
OUTPUT_LABELS = ("ZYNADAC L/R", "ZYNTHIAN HEADPHONES",
                 "RASPBERRY PI HEADPHONES", "HDMI")


def default_settings():
    """Return safe migration defaults: every context starts silent."""
    return {view: {"enabled": False, "output": None} for view in VIEWS}


def load_audio_settings(path=AUDIO_SETTINGS_PATH):
    settings = default_settings()
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return settings
    for view in VIEWS:
        value = payload.get(view, {})
        if isinstance(value, dict):
            settings[view]["enabled"] = value.get("enabled") is True
            output = value.get("output")
            settings[view]["output"] = output if output in OUTPUT_LABELS else None
    return settings


def save_audio_settings(settings, path=AUDIO_SETTINGS_PATH):
    """Atomically persist only the stable, public settings schema."""
    clean = default_settings()
    for view in VIEWS:
        value = settings.get(view, {})
        clean[view]["enabled"] = value.get("enabled") is True
        output = value.get("output")
        clean[view]["output"] = output if output in OUTPUT_LABELS else None
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def output_label(device):
    """Map an MPV device record to one of LUMAZ's hardware labels.

    MPV supplies backend-specific names (ALSA/PipeWire/JACK) and descriptions;
    keeping this heuristic here prevents hardware identifiers leaking into view
    logic. Unknown devices are deliberately not offered as named hardware.
    """
    text = f"{device.get('name', '')} {device.get('description', '')}".lower()
    if "hdmi" in text:
        return "HDMI"
    if any(word in text for word in ("zynadac", "hifiberry", "audioinjector")):
        return "ZYNADAC L/R"
    if "zynthian" in text and any(word in text for word in ("headphone", "phones")):
        return "ZYNTHIAN HEADPHONES"
    if any(word in text for word in ("bcm2835 headphones", "raspberry pi headphones",
                                     "vc4 headphones", "headphones bcm")):
        return "RASPBERRY PI HEADPHONES"
    return None


def available_outputs(devices):
    """Return detected labelled outputs mapped to their real MPV device name."""
    candidates = {}
    for device in devices or ():
        if not isinstance(device, dict) or not device.get("name"):
            continue
        label = output_label(device)
        if label:
            candidates.setdefault(label, []).append(device["name"])

    def preference(name):
        """Prefer ALSA's stable card-level default over plughw/hw endpoints."""
        lowered = name.lower()
        if lowered.startswith("alsa/default:"):
            return 0
        if "default" in lowered:
            return 1
        if "plughw" in lowered:
            return 3
        if "hw:" in lowered:
            return 4
        return 2

    return {label: min(candidates[label], key=preference)
            for label in OUTPUT_LABELS if label in candidates}


def selected_device(view, devices, settings=None):
    """Resolve one view's preference against devices available right now."""
    settings = settings or load_audio_settings()
    outputs = available_outputs(devices)
    preferred = settings[view].get("output")
    label = preferred if preferred in outputs else next(iter(outputs), None)
    return (label, outputs.get(label))


def audio_commands(view, devices, settings=None):
    """Build MPV commands for a newly loaded file in the given context."""
    settings = settings or load_audio_settings()
    label, device = selected_device(view, devices, settings)
    if not settings[view]["enabled"] or device is None:
        return [["set_property", "aid", "no"]]
    return [["set_property", "audio-device", device],
            ["set_property", "aid", "auto"]]


def audio_track_selected(tracks):
    """Return whether MPV reports an audio track as selected."""
    return any(isinstance(track, dict) and track.get("type") == "audio" and
               track.get("selected") is True for track in (tracks or ()))


def activate_loaded_audio(view, get_property, send_command, settings=None,
                          attempts=25, interval=0.04, sleep=time.sleep,
                          expected_path=None, cancelled=None):
    """Enable audio after MPV exposes the intended file, without stale launches."""
    def is_cancelled():
        return bool(cancelled and cancelled())

    settings = settings or load_audio_settings()
    if not settings[view]["enabled"]:
        send_command(["set_property", "aid", "no"])
        return False

    _label, device = selected_device(view, get_property("audio-device-list"), settings)
    if device is None or is_cancelled():
        send_command(["set_property", "aid", "no"])
        return False

    for attempt in range(attempts):
        if is_cancelled():
            return False
        if expected_path is not None and str(get_property("path")) != str(expected_path):
            if attempt + 1 < attempts:
                sleep(interval)
            continue
        tracks = get_property("track-list") or []
        if any(isinstance(track, dict) and track.get("type") == "audio" for track in tracks):
            if is_cancelled():
                return False
            send_command(["set_property", "audio-device", device])
            send_command(["set_property", "aid", "auto"])
            for verify_attempt in range(attempts):
                if is_cancelled():
                    send_command(["set_property", "aid", "no"])
                    return False
                if audio_track_selected(get_property("track-list")):
                    return True
                if verify_attempt + 1 < attempts:
                    sleep(interval)
            return False
        if attempt + 1 < attempts:
            sleep(interval)
    return False
