---
name: workout-whiteboard
description: Write one day's workout, or a run of days, as whiteboard cards for a hybrid athlete (Hyrox and CrossFit) — challenging, fully spelled out, ready to follow in the gym.
---

# Workout whiteboard

Turns a planned session into the card the athlete trains from. The app renders the card;
this skill returns its content in the output schema.

## Inputs

The session (date, type, goal, targets), the athlete profile (division, equipment, paces,
strength baselines, preferences) and the last results for the same work.

## Rules for every card

1. **Challenging by default.** The athlete asked for hard sessions. Scale down only for a
   logged reason (fatigue, pain, three hard days in a row) and say why on the card.
2. **Spell out the flow.** What follows what, and exactly where rest goes. For runs after
   stations, write the whole order: run, station, run, rest.
3. **Superset order.** "A then straight into B, rest 1:30, repeat 4 times total."
4. **Machine per rep.** Air runner, motorised treadmill (1% incline) or track; row or SkiErg.
   Air runner work in km/h, track and treadmill work in min/km or km/h as the profile says.
5. **Mat lengths.** The sled mat is 12.5 m one way unless the profile says otherwise:
   50 m = 4 lengths, 80 m = 6 lengths + 5 m, 100 m = 8 lengths.
6. **Timer settings** for the interval app (tabata mode): work, rest, rounds, cycles.
7. **A fallback** for any load that may be too heavy (e.g. "sled won't move at a steady
   walk: remove plates and log the load").
8. **Pro weights** when the profile says Men's Pro: sled push 202 kg, sled pull 153 kg (both
   including the sled), farmers 2 × 32 kg, lunges 30 kg, wall balls 9 kg to 3 m.
9. **Hide the daily push and core block.** It is done every day but never drawn on the card.
10. **A `Log:` footer** naming exactly what to record.

## Card shape

Date and duration pill, a serif title, a coloured tag (why this session, or "Moved from
Tue"), then sections. Each section has a kind that sets its colour: `warmup` and `cooldown`
grey, `strength` purple, `engine` coral, `core` teal. Notes and flows are separate boxes.
