---
name: screenshot-reader
description: Read numbers and workouts out of screenshots (Hyrox and Roxfit results, Runna and Strava runs, box-class apps) into structured data for the athlete to confirm before saving.
---

# Screenshot reader

## Steps

1. Identify what the image is: a race result, a run summary, a class workout, or other.
2. Extract every value in the output schema for that kind. Keep times as `mm:ss` or
   `h:mm:ss` exactly as shown; keep units as shown.
3. Mark any value you could not read with confidence as `uncertain` and quote what you saw.
4. Return the data. The app shows it to the athlete to confirm or correct before anything is
   saved; never write it straight to the database.

## Rules

- Read only what is in the image. Never fill a missing split from an average.
- One image can hold part of a table; when several images are given, merge them and flag
  any overlap that disagrees.
- Ignore personal data that is not training data (other athletes' names, notifications).
