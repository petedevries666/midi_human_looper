#!/usr/bin/env python3
"""Read-only MBMF MIDI/XRUN sampler with a single emergency JACK disconnect.

Does not connect JACK ports, modify native Zynthian routes, launch/stop
transport, or send synth MIDI. Safe default: observe idle for two seconds.
During a physical REC smoke test, run --seconds 15 in another terminal.
"""
import argparse
import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_CONTROL = Path(
    "/zynthian/zynthian-my-data/midi-human-looper/processor-1/control.sock"
)
SOURCE = "mbh_1:midi_out"
DEST = re.compile(r"ZynMidiRouter:dev[0-9]+_in")


def status(path):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(4)
        connection.connect(str(path))
        connection.sendall(b"1 0 0 0 1 0 0 0\n")
        data = b""
        while b"\n" not in data:
            packet = connection.recv(65536)
            if not packet:
                raise RuntimeError("MBMF control socket closed before status")
            data += packet
            if len(data) > 4 * 1024 * 1024:
                raise RuntimeError("MBMF status response exceeds 4 MB")
    return json.loads(data.split(b"\n", 1)[0])


def virtual_targets():
    lines = subprocess.check_output(
        ["jack_lsp", "-c", SOURCE], text=True
    ).splitlines()
    return [line.strip() for line in lines[1:]
            if DEST.fullmatch(line.strip())]


def emergency_disconnect(targets):
    for destination in targets:
        result = subprocess.run(
            ["jack_disconnect", SOURCE, destination], check=False
        )
        if result.returncode:
            print("DISCONNECT FAILED:", destination, file=sys.stderr)
        else:
            print("SAFETY DISCONNECT:", SOURCE, "->", destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=2)
    parser.add_argument("--control", type=Path, default=DEFAULT_CONTROL)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 120:
        parser.error("--seconds must be 1..120")

    targets = virtual_targets()
    if len(targets) != 1:
        print("REFUSED: expected exactly one native virtual destination;"
              " found:", targets)
        return 2
    previous = status(args.control)
    if previous.get("status") != "ok" or previous.get("chainError"):
        print("REFUSED: engine not clean at start:", previous.get("status"),
              "chainError=", previous.get("chainError"))
        emergency_disconnect(targets)
        return 3
    for field in ("midiCount", "lateBlocks"):
        if type(previous.get(field)) not in (int, float):
            print("REFUSED: absent/malformed counter", field)
            emergency_disconnect(targets)
            return 3

    # Legacy midiCount is an output-generation counter, not proof of delivery.
    # New runtimes expose the actual JACK boundaries independently.
    counter = 'midiGenerated' if 'midiGenerated' in previous else 'midiCount'
    fields = [counter] + [f for f in ('midiReceived', 'midiWritten', 'midiDropped',
                                      'midiWriteFailures', 'midiRecoveries')
                          if f in previous]
    totals = dict.fromkeys(fields, 0)
    midi_total = 0
    late_total = 0
    end = time.monotonic() + args.seconds
    print("Observing", SOURCE, "->", targets[0],
          "for", args.seconds, "seconds")
    while time.monotonic() < end:
        time.sleep(min(0.25, max(0, end - time.monotonic())))
        current = status(args.control)
        deltas = {f: current[f]-previous[f] for f in fields}
        for field, delta in deltas.items():
            totals[field] += delta
        midi = deltas[counter]
        late = current["lateBlocks"] - previous["lateBlocks"]
        midi_total += midi
        late_total += late
        # Keep the existing generation/XRUN guard. Also detect a receive/write
        # storm; successful JACK writes do not prove a synth received the data.
        if (any(v < 0 for v in deltas.values()) or late < 0
                or any(deltas.get(f, 0) > 500 for f in
                       (counter, 'midiReceived', 'midiWritten')) or late > 5
                or current.get("chainError")
                or current.get("outputOverflow", 0)):
            print("ALERT! MIDI boundary deltas=", deltas, "lateBlocks delta=", late,
                  "chainError=", current.get("chainError"),
                  "outputOverflow=", current.get("outputOverflow"))
            emergency_disconnect(targets)
            return 1
        previous = current

    print("PASS sampled period: MIDI counters=", totals,
          "legacy generation counter" if counter == 'midiCount' else 'JACK boundaries measured',
          "lateBlocks=", late_total, "chainError=0")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("Diagnostic failed:", exc, file=sys.stderr)
        # Readability / control-socket failures are also unsafe during REC.
        try:
            emergency_disconnect(virtual_targets())
        except Exception:
            pass
        sys.exit(4)
