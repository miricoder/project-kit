---
name: purposed-convo-workout-readjust
description: Purposed convo, weekly workout check-in. Use when the athlete wants to review this week's workouts, log results, reschedule around a new session, and get an updated schedule.
---

# Purposed convo: workout readjust

Label: **purposed convo**. When the athlete asks for "my purposed convos", list every skill
whose name starts with `purposed-convo-` with its one-line description, and let them pick
one to run again.

Ported from the Claude skill of the same name. Claude-only tools are replaced by app tools:
past chats → `sessions.read` and `results.read`; the Sheets schedule → `sessions.write`;
artifacts → `uploads.read`.

## Where the data lives

1. `profile.read` for division, goals, units and preferences.
2. `sessions.read` for this week (Sunday to Saturday unless the profile says otherwise) and
   `results.read` for what is already logged.
3. `uploads.read` for screenshots attached to this run (class workouts, results).
4. Never invent sessions or results. If something is missing, ask.

## Task 1: where the week stands

- Return a status table: Day, Date, Session, Status (Done, Today, Scheduled, Moved,
  Skipped), Result.
- Ask for today's results, per part: strength top set and RPE, metcon time or rounds,
  chipper time, scaling used, how it felt, any pain.
- Analyse and give feedback: compare with earlier logged numbers, note PRs or drops, 2 to 3
  practical tips (pacing, recovery, scaling, technique cues). Pain is a reason to see a
  professional; this is not medical advice.

## Task 2: a new or changed workout

- Ask whether a new or different workout is planned. If yes, insert it and push the next
  session in line (and any after it) to the next available day. Keep at least one rest day.
  Say so when two heavy sessions land on back-to-back days.
- Ask for doubts or questions **before** the next workout (movements, weights, scaling,
  warm-up), and again after its data is logged.

## Task 3: always end with the schedule

- Save the week with `sessions.write` (status and `movedFrom` on every moved session).
- Return the schedule as whiteboard cards (the `workout-whiteboard` output shape), never as
  a plain table: the athlete asked for the card look.

## Style

- Dates in the athlete's time zone; kg by default, lb beside kg when asked.
- Short, scannable replies; questions together at the end.
