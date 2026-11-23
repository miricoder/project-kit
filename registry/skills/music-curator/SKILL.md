---
name: music-curator
description: Build the music for a session — a tempo band per section, running cadence for runs, and a playlist from the athlete's connected music service — with ducking for timer cues.
---

# Music curator

> **Future R&D.** Not in PANKRA v1 and not in any plugin yet. Which service (Spotify,
> which needs Premium for a developer app, or Apple Music, which needs the paid Apple
> Developer Program) is still to be decided.

## Steps

1. Read the session (`sessions.read`) and the athlete's music preferences from the profile
   (genres, artists to avoid, explicit allowed or not).
2. Give each section a tempo band: warm-up 110 to 125 BPM, strength 90 to 110, engine and
   race simulation 150 to 175, cool-down under 100. Runs follow the target cadence
   (170 to 180 steps a minute) when the athlete wants that.
3. Find tracks with `music.search` and build the playlist with `music.playlist`, ordered to
   the section timings so the change of tempo lands on the change of section.
4. Return the playlist and the cue points where the timer will lower the music.

## Rules

- Use only the athlete's connected service. With none connected, return the tempo plan and
  ask them to connect one.
- Never download or copy audio; playback is through the service's own player.
