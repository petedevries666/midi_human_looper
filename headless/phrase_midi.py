"""Bounded SMF interchange. Runs only in the HTTP worker, never JACK.
Phrase timestamps are source seconds; tempo maps are interpreted on import.
"""
import bisect
import math
import struct

MAX_BYTES = 1024 * 1024
MAX_EVENTS = 2048
MAX_SECONDS = 3600


def vlq(data, pos, end):
    value = 0
    for _ in range(4):
        if pos >= end:
            raise ValueError('Truncated MIDI variable-length quantity')
        byte = data[pos]; pos += 1
        value = (value << 7) | (byte & 127)
        if byte < 128:
            return value, pos
    raise ValueError('Invalid MIDI variable-length quantity')


def encode_vlq(value):
    if not 0 <= value <= 0xfffffff:
        raise ValueError('MIDI delta time out of range')
    out = [value & 127]
    while value >> 7:
        value >>= 7; out.insert(0, (value & 127) | 128)
    return bytes(out)


def validate_notes(events):
    held = {}
    for _, status, note, value in events:
        key = (status & 15, note)
        if status & 240 == 144 and value:
            held[key] = held.get(key, 0) + 1
        elif held.get(key, 0):
            held[key] -= 1
        else:
            raise ValueError('Unpaired Note Off: import cancelled')
    if any(held.values()):
        raise ValueError('Missing Note Off: import cancelled; close notes in the source file')


def read_smf(data):
    if not 14 <= len(data) <= MAX_BYTES or data[:4] != b'MThd':
        raise ValueError('Invalid or oversized MIDI file (limit 1 MiB)')
    size = struct.unpack_from('>I', data, 4)[0]
    if size != 6:
        raise ValueError('Unsupported MIDI header length')
    fmt, tracks, ppq = struct.unpack_from('>HHH', data, 8)
    if fmt not in (0, 1) or not 1 <= tracks <= 64 or (fmt == 0 and tracks != 1):
        raise ValueError('Only SMF Format 0/1 with at most 64 tracks is supported')
    if not ppq or ppq & 0x8000:
        raise ValueError('SMPTE time division is unsupported; export a PPQ MIDI file')
    pos = 14; events = []; tempos = [(0, 500000)]; meters = []; last_tick = 0
    scanned = 0
    for track in range(tracks):
        if data[pos:pos+4] != b'MTrk' or pos+8 > len(data):
            raise ValueError('Missing MIDI track chunk')
        length = struct.unpack_from('>I', data, pos+4)[0]; pos += 8; end = pos+length
        if end > len(data):
            raise ValueError('Truncated MIDI track')
        tick = 0; running = None; ended = False
        while pos < end:
            scanned += 1
            if scanned > 16384:
                raise ValueError('Too many MIDI events')
            delta, pos = vlq(data, pos, end); tick += delta
            if tick > ppq * 1000000 or pos >= end:
                raise ValueError('Invalid or excessive MIDI duration')
            status = data[pos]
            if status >= 128:
                pos += 1
            elif running is not None:
                status = running
            else:
                raise ValueError('Invalid MIDI running status')
            if status == 255:
                running = None
                if pos >= end: raise ValueError('Truncated MIDI meta event')
                kind = data[pos]; pos += 1; n, pos = vlq(data, pos, end)
                if pos+n > end: raise ValueError('Truncated MIDI meta payload')
                payload = data[pos:pos+n]; pos += n
                if kind == 81:
                    if n != 3 or not int.from_bytes(payload, 'big'): raise ValueError('Invalid tempo')
                    tempos.append((tick, int.from_bytes(payload, 'big')))
                elif kind == 88:
                    if n != 4 or not payload[0] or payload[1] > 7: raise ValueError('Invalid time signature')
                    meters.append([tick, payload[0], 2**payload[1]])
                elif kind == 47:
                    if n or pos != end: raise ValueError('Invalid end-of-track')
                    ended = True; break
            elif status in (240, 247):
                raise ValueError('SysEx is unsupported by phrase interchange; import cancelled')
            elif 128 <= status < 240:
                running = status
                n = 1 if status & 240 in (192, 208) else 2
                if pos+n > end or any(v >= 128 for v in data[pos:pos+n]):
                    raise ValueError('Invalid MIDI channel event')
                payload = data[pos:pos+n]; pos += n
                if status & 240 not in (128, 144):
                    raise ValueError('Only notes are supported; CC/program/bend/aftertouch import cancelled')
                if status & 240 == 144 and payload[1] == 0: status = 128 | (status & 15)
                events.append([tick, status, payload[0], payload[1]])
                if len(events) > MAX_EVENTS: raise ValueError('Phrase capacity exceeded (2048 events); import cancelled')
            else:
                raise ValueError('Unsupported MIDI status')
        if not ended: raise ValueError('Missing end-of-track')
        last_tick = max(last_tick, tick); pos = end
    if pos != len(data): raise ValueError('Unexpected trailing MIDI data')
    if not events: raise ValueError('MIDI file has no notes')
    # Stable track/event order for equal timestamps, preserving authored pairing.
    events.sort(key=lambda e:e[0]); validate_notes(events)
    tempos.sort(key=lambda item:item[0]); points = []; accumulated = 0.; previous = 0; tempo = 500000
    for tick, new_tempo in tempos:
        accumulated += (tick-previous)*tempo/(ppq*1000000)
        if points and points[-1][0] == tick: points[-1] = (tick, accumulated, new_tempo)
        else: points.append((tick, accumulated, new_tempo))
        previous = tick; tempo = new_tempo
    ticks = [p[0] for p in points]
    def seconds(tick):
        start, elapsed, tempo = points[bisect.bisect_right(ticks, tick)-1]
        return elapsed+(tick-start)*tempo/(ppq*1000000)
    duration = seconds(last_tick)
    if duration <= 0 or duration > MAX_SECONDS: raise ValueError('MIDI duration must be between zero and one hour')
    for e in events: e[0] = seconds(e[0])
    return {'events':events, 'lengthSeconds':duration, 'format':fmt, 'tracks':tracks,
            'ppq':ppq, 'tempos':[[t,60000000/v] for t,v in tempos], 'meters':meters,
            'noteCount':sum(1 for e in events if e[1]&240 == 144),
            'tempoPolicy':'Preserve file tempo-map timing in seconds; never change global transport tempo.'}


def write_smf(phrase):
    events = phrase['events']; duration = phrase['lengthSeconds']; bpm = phrase.get('bpm',120)
    if not math.isfinite(duration) or not 0 <= duration <= MAX_SECONDS or not 4 <= bpm <= 1000:
        raise ValueError('Invalid phrase duration or tempo')
    if duration == 0 and events: raise ValueError('Nonempty phrase has no duration')
    if len(events) > MAX_EVENTS: raise ValueError('Phrase capacity exceeded')
    for e in events:
        if len(e) != 4 or not math.isfinite(e[0]) or not 0 <= e[0] <= duration or any(type(v) is not int for v in e[1:]) or not 128 <= e[1] < 240 or not 0 <= e[2] <= 127 or not 0 <= e[3] <= 127:
            raise ValueError('Invalid stored phrase event')
    ordered = sorted(events,key=lambda e:e[0])
    # Include stored compatible channel events on export, without transforming them.
    note_events = [e for e in ordered if e[1]&240 in (128,144)]
    validate_notes(note_events)
    tempo = round(60000000/bpm)
    ppq = min(24000,max(1,int(0xfffffff*tempo/(max(duration,1e-6)*1000000))))
    track = bytearray(b'\0\xff\x51\x03'+tempo.to_bytes(3,'big')+b'\0\xff\x58\x04\x04\x02\x18\x08')
    previous = 0
    for seconds, status, d1, d2 in ordered:
        tick = round(seconds*ppq*1000000/tempo)
        track.extend(encode_vlq(tick-previous)); track.extend((status,d1))
        if status & 240 not in (192,208): track.append(d2)
        previous = tick
    end = max(previous,round(duration*ppq*1000000/tempo))
    track.extend(encode_vlq(end-previous)+b'\xff\x2f\0')
    return b'MThd'+struct.pack('>IHHH',6,0,1,ppq)+b'MTrk'+struct.pack('>I',len(track))+track
