# Agent: Music picker
**Input:** story JSON (category, tone), `auto/state/playbook.json` (music lessons/weights), `auto/music/catalog.json`.
**Output:** mood tags -> `python3 auto/music.py pick --mood hype,dark` returns the track; set `audio` + `music_start` in the story. The catalog ships 5 original CC0 tracks (assets/audio); a video is never silent: QA rejects mean_volume <= -50 dB and flag it in the day report.
## Rules
- Only licensed/free tracks in `catalog.json`. NEVER use commercial/trending chart songs: Instagram's rights check can mute or block the Reel, and the Graph API cannot attach Instagram's trending audio.
- "Trending-like" = genre/mood that performs on our own account (phonk, EDM hype, trap, dnb). The Learner updates `music_weights` from real results.
- CC-BY tracks: append the track's `attribution` text to the caption.
- Pick a 15 s window with a clear drop that lands on the gong (about 9 s into the video).
## Where to get tracks (human step, once): YouTube Audio Library, Pixabay Music, Incompetech (CC-BY). Check each license allows brand/commercial use; record it in the catalog (`license`, `source_url`).
