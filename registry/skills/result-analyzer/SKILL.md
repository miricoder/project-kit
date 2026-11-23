---
name: result-analyzer
description: Analyse a logged workout against what was prescribed and earlier results, then give key feedback, two or three practical tips and the changes to make to the next sessions.
---

# Result analyser

## Steps

1. Read the session as prescribed (`sessions.read`) and the result (`results.read`, plus any
   screenshot already read into numbers).
2. Compare prescribed and done for each part: load, reps, time, pace, rounds. Convert pace
   to the machine it was run on (Air runner speed is slower than a treadmill or track for
   the same effort; use the athlete's logged ratio, not a fixed one).
3. Compare with the last result for the same work. Name PRs and drops with the numbers.
4. Find the pattern behind the numbers: fading reps, a slow start, a station that cost time.
5. Give 2 to 3 tips the athlete can act on next session: pacing, recovery, scaling,
   technique cues.
6. Propose changes to upcoming sessions (paces, loads, rounds) as `adjustments`; the app
   asks the athlete before saving them.

## Rules

- Own a wrong prescription plainly: if the target was unrealistic, say the target was wrong,
  not the athlete.
- Loads in kg, with lb beside them when the profile asks.
- Pain or injury: stop the analysis there, say to see a professional, and suggest a lighter
  plan until cleared. Not medical advice.
- Ask for any number that is missing; never estimate a result the athlete did not give.
