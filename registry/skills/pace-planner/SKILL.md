---
name: pace-planner
description: Set and progress running paces for each machine (Air runner, motorised treadmill, track) from the athlete's own data, up to a race date.
---

# Pace planner

## Steps

1. Read logged runs (`results.read`, and Strava activities when connected).
2. Work out the athlete's ratio between machines from matched efforts, for example an Air
   runner speed against the treadmill speed they hold at the same effort. Never use a fixed
   ratio when the athlete's own data exists.
3. Set targets per session type: threshold, short reps, tempo, Zone 2, compromised runs.
   Air runner in km/h; treadmill in km/h at 1% incline; track in min/km.
4. Build the progression to the race date: a small step each week when every rep was held
   at an even pace, a deload week every 3 to 4 weeks, a taper before the race.
5. Return the table of targets and the week-by-week progression.

## Rules

- Progress only on even pacing: a fast first rep and a faded last rep is a hold, not a pass.
- Race pace for a run straight after a station is slower than a fresh run; say both.
