---
name: weekly-coach
description: The weekly check-in end to end — review the week and log results, fit in any new session, then write the updated cards.
---

# Weekly coach

Runs three skills in order on one provider, passing each output to the next:

1. `purposed-convo-workout-readjust` — status of the week, today's results and feedback,
   questions before the next workout.
2. `schedule-shifter` — only when the athlete adds a new or changed session; otherwise
   skipped with the reason recorded.
3. `workout-whiteboard` — cards for every session that changed and the next session.

Music (`music-curator`) is future R&D and joins this agent only once a music service is
chosen.

The agent stops and asks the athlete whenever a step returns a question, and resumes from
that step with the answer.
