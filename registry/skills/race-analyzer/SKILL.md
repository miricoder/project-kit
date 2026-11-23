---
name: race-analyzer
description: Break down Hyrox race results (8 runs, 8 stations, Roxzone) against a target time and earlier races, and rank where the time to gain is.
---

# Race analyser

## Steps

1. Read the race (`races.read`): total, the 8 runs, the 8 stations, Roxzone, ranks,
   division. Check the parts add up to the total within a few seconds; if not, say which
   number looks wrong and ask.
2. Read the athlete's target (for example sub-60 Pro) from the profile. Split the target
   into a plausible time per run, station and Roxzone. Show that split, as it is a model,
   not a fact.
3. Rank every segment by seconds to gain against the target. The output feeds a bar chart.
4. Compare with earlier races: what held steady (a limit) and what moved (a bad day).
5. Look for causes the numbers point to (pacing fade, fuel, a slow station) and ask about
   the ones you cannot see, such as what was eaten before the race.
6. Give the training changes that follow, ranked by seconds they can save.

## Rules

- A run lap count matters: confirm how many laps made 1 km on that course before comparing
  run times between races.
- Never invent splits. Missing segments are reported as missing.
