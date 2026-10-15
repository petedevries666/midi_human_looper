# Test excerpts from zynthian-ui Oram 11d4e858367db465a431c701d9035432742a5a7d.
# Copyright Zynthian contributors; GPL-3.0-or-later, matching upstream headers.
# Only LV2 discovery/hardware is stubbed; catalog loading/indexing below is upstream.
import os
import json
import logging
from enum import Enum
engines = {}
engines_by_type = None
engines_mtime = None
ENGINE_CONFIG_FILE = ''
JALV_LV2_CONFIG_FILE = ''

# Stub the LV2 scan, retaining all standalone metadata and enabled preferences.
def generate_engines_config_file(reset_rankings=None):
    global engines, engines_mtime
    engines = {key: {'NAME': row[0], 'TITLE': row[1], 'TYPE': row[2],
                    'CAT': row[3], 'ENABLED': engines.get(key, {}).get('ENABLED', row[4])}
               for key, row in standalone_engine_info.items()}
    with open(ENGINE_CONFIG_FILE, 'w') as stream:
        json.dump(engines, stream)
    engines_mtime = os.stat(ENGINE_CONFIG_FILE).st_mtime

class EngineType(Enum):
    MIDI_SYNTH = "MIDI Synth"
    MIDI_TOOL = "MIDI Tool"
    AUDIO_EFFECT = "Audio Effect"
    AUDIO_GENERATOR = "Audio Generator"
    SPECIAL = "Special"

engine_categories = {
    "MIDI Synth": (
        "Synth",
        "Sampler",
        "Piano",
        "Organ",
        "Acoustic",
        "Percussion",
        "Other"
    ),
    "Audio Effect": (
        "Delay",
        "Distortion",
        "Dynamics",
        "Filter & EQ",
        "Modulation",
        "Panning & Spatial",
        "Pitch",
        "Reverb",
        "Simulator",
        "Analyzer",
        "Other"
    ),
    "MIDI Tool": (
        "Arpeggiator",
        "Automation",
        "Filter",
        "Mapper",
        "Sequencer",
        "Other"
    ),
    "Audio Generator": (
        "Generator",
        "Oscillator",
        "Other"
    ),
    "Special": (
        "Language",
        "Patchbay",
        "Sampler",
        "Other"
    )
}

standalone_engine_info = {
    "ZY": ["ZynAddSubFX", "ZynAddSubFX", "MIDI Synth", "Synth", True],
    "FS": ["FluidSynth", "FluidSynth: SF2, SF3", "MIDI Synth", "Sampler", True],
    "SF": ["Sfizz", "Sfizz: SFZ", "MIDI Synth", "Sampler", True],
    "LS": ["LinuxSampler", "LinuxSampler: SFZ, GIG", "MIDI Synth", "Sampler", True],
    "BF": ["setBfree", "setBfree - Hammond Emulator", "MIDI Synth", "Organ", True],
    "AE": ["Aeolus", "Aeolus - Pipe Organ Emulator", "MIDI Synth", "Organ", True],
    "PT": ['Pianoteq', "Pianoteq", "MIDI Synth", "Piano", True],
    "AP": ["ZynSampler", "ZynSampler", "MIDI Synth", "Sampler", True],
    "SL": ["SooperLooper", "SooperLooper", "Audio Effect", "Delay", True],
    'SX': ["SysEx", "SysEx Manager", "MIDI Tool", "Other", True],
    'MC': ["MIDI Control", "MIDI Control External", "MIDI Tool", "Other", True],
    'IR': ["InternetRadio", "Internet Radio", "Audio Generator", "Other", True],
    'PD': ["PureData", "PureData - Visual Programming", "Special", "Language", True],
    'MD': ["MOD-UI", "MOD-UI - Plugin Host", "Special", "Language", True]
}

def get_engines():
    try:
        mtime = os.stat(ENGINE_CONFIG_FILE).st_mtime
    except:
        mtime = None
    if not mtime or not engines_mtime or engines_mtime != mtime:
        return load_engines()
    else:
        return engines

def load_engines():
    global engines, engines_mtime
    engines = {}

    if os.path.exists(ENGINE_CONFIG_FILE):
        fpath = ENGINE_CONFIG_FILE
    else:
        fpath = JALV_LV2_CONFIG_FILE

    try:
        with open(fpath) as f:
            engines = json.load(f)
        engines_mtime = os.stat(fpath).st_mtime
        logging.debug(f'Loaded engine config with timestamp: {engines_mtime}')
    except Exception as e:
        logging.error('Loading engine config failed: {}'.format(e))

    # Regenerate config file if it doesn't exist or is an older version
    if not os.path.exists(ENGINE_CONFIG_FILE) or 'AE' in engines and "ID" not in engines['AE']:
        generate_engines_config_file(reset_rankings=1)

    get_engines_by_type()
    return engines

def get_engines_by_type():
    global engines_by_type
    engines_by_type = {}

    for t in EngineType:
        engines_by_type[t.value] = {}

    for key, info in engines.items():
        engines_by_type[info['TYPE']][key] = info

    return engines_by_type
