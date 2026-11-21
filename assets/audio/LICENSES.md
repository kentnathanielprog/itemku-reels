# Background music: sources and licenses

All five tracks are **original works synthesized from scratch** by `short/music_gen.py` (numpy + ffmpeg) in this repository.
**No samples, recordings, loops, presets or downloaded material of any kind** were used, and none of the melodies reproduces an existing song:
the chord progressions are generic (i-VI-III-VII, I-V-vi-IV, ...) and the rhythms/melodies come from a seeded random generator.
Nothing here comes from YouTube, a music library, a streaming service or any third party, so there is no third-party license to honour and no attribution is required.

| File | Title | Style | BPM / key | Moods (catalog tags) |
|---|---|---|---|---|
| `pulse-arena.m4a` | Pulse Arena | EDM, four-on-the-floor, sidechain pad | 128 / F minor | hype, edm |
| `pixel-jump.m4a` | Pixel Jump | chiptune (square leads, triangle bass) | 120 / C major | fun, upbeat |
| `low-tide.m4a` | Low Tide | lo-fi, swung, electric piano | 84 / A minor | chill |
| `sunny-lane.m4a` | Sunny Lane | upbeat plucked pop | 110 / G major | upbeat, fun |
| `dark-alley.m4a` | Dark Alley | dark trap, half-time | 140 / D minor | dark, trap |

## License
Created for the itemku Reels project; the copyright holder is the repository owner. The tracks are released under **CC0 1.0 (public-domain dedication)**:
free for commercial use, for posting on Instagram/Reels, and for modification, with no attribution. `auto/music/catalog.json` records `license: CC0-1.0` and an empty `attribution`.
(The owner should confirm this dedication; until then the tracks are at minimum the owner's own original work, usable in this project without restriction.)

## Format
AAC-LC, 44.1 kHz, stereo, 128 kbps, 60 s, loudness-normalised to **-18 LUFS** integrated (two-pass `loudnorm`, true peak <= -2 dBTP).
At render time (`short/make_short.py`) the track is trimmed/looped to the video length with a 0.8 s fade-in and a 1.5 s fade-out.

## Reproduce
`python3 short/music_gen.py assets/audio` (about 40 s). Output is deterministic in notes; the AAC bytes can differ slightly between ffmpeg builds.

## Not guaranteed
Instagram's automatic audio matching can, in rare cases, flag any audio as a match to someone else's registered work. These tracks contain no third-party material, so a claim would be a false positive and can be disputed.
