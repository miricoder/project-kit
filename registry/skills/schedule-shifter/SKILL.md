---
name: schedule-shifter
description: Insert a new session (a box class, a race, a missed day) into the week and push the planned sessions to the next free days, keeping rest and recovery sensible.
---

# Schedule shifter

## Steps

1. Read the week (`sessions.read`) and the new session (from text or an image already read
   by `screenshot-reader`).
2. Put the new session on its date. Every planned session from that date on moves to the
   next free day, in order. Set `status: Moved` and `movedFrom` on each.
3. Keep at least one rest day in every 7. The profile names the default rest day; keep it
   unless the athlete says otherwise.
4. Check load: name any run of three hard days and any two days that hit the same thing
   (heavy sleds the day after heavy deadlifts, pressing the day after a heavy bench). Lower
   the second (fewer rounds, a fallback) and say so in that session's tag.
5. Remove duplicated work: if the new class covers what a later session drills, trim the
   later one and say what changed.
6. Write the week with `sessions.write` and return the list of changes.

## Rules

- Never drop a session silently. A session pushed past the end of the week goes to the next
  week, and the output says so.
- The athlete's own class wins over a planned session on the same day.
