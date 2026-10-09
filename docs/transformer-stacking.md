# Stateless Transformer instances

v1.25 adds independent TRANSPOSE, NOTE RANGE and VELOCITY instances to the same
registry used by additional CC MOD instances. Each extra record stores its actual
processor type, stable creation ID, parameters and expression curves. NOTE RANGE
has a third curve for its high endpoint. The existing six block capacity applies
per instrument; additions beyond capacity are rejected rather than truncated.

A single legacy instance retains the original fixed routing stages. Once an
active stateless duplicate is added, transpose and range processors form a serial
chain in visible left-to-right order. A range before a transpose filters the
original pitch; reversing them filters the transposed pitch. Velocity multipliers
compose multiplicatively and clamp/round once at output. Both live input and
phrase playback use the same pipeline, without modifying recorded events.

Structural edits are bounded queued commands, consumed by DSP. Note-transform
add/remove/bypass waits for the instrument's live and phrase input ownership count
to reach zero. Pitch/range expression edits also wait. This preserves the chain
that produced each held Note On until its Note Off. Velocity amount edits and CC
changes remain immediate. Removing/bypassing ARP clears its generated active note
and held-source state; no stale HOLD notes resume accidentally.

Polyphony and ARP remain single-instance per instrument. Their state is owned by
the instrument, so serial or parallel duplication would require a new explicit
branch/ownership model. The add menu hides a second stateful instance. This is a
deliberate restriction, rather than a pair of blocks sharing runtime state. Smart
Switch module targets continue to refer to legacy instrument/type identities;
additional stateless instances have independent block controls.

Schema 5 appends type metadata, legacy processor IDs and third curves after the
complete schema-4 payload. Existing data addresses remain frozen. Schema 4 loads
with additional records interpreted as CC generators, preserving their original
IDs, destinations and curves. Schemas 1–3 retain their previous migrations.
Internal patch banks and external SAVE/LOAD include the appended registry.

Regression coverage includes serial ordering, multiplicative velocity, live and
phrase Note On/Off pairing, deferred edits, independently mapped third curves,
recorded-data preservation, internal/external persistence and schema-4 migration.
The original expression, Smart Switch, phrase, timing and CC regressions still run.

Real REAPER testing should include held notes while removing or bypassing a pitch
processor, expression changes during held notes, multiple velocity processors,
range/transpose order, SAVE/LOAD and STOP/PANIC. Hardware acceptance is pending.
