# Roadmap — Phenix Rebirth
Current release: **v1.4.5**

## Unreleased (towards 1.5.0 — Adventure)

- Adventure code reorganised, nothing changes on screen: rules and save data now live in
  `story_state.py` (tested without a window), `story.py` only draws the menus
- Adventure save is now one file per slot (`story_1.json` … `story_3.json`, version 3).
  The old draft `story.json` is no longer read; start a new adventure
- Dome time and recharge are saved in seconds (no longer tied to 60 Hz)
- The adventure journal follows the language chosen in Options
- Adventure menus: texts are now centred inside their boxes (hangar, workshop, mission map, journal)
- No more frozen explosion pieces on the menu after an adventure mission
- Adventure start: slot list (3 saves with pilot name, act, date and mode), pilot name entry, Normal / Veteran choice

### Planned for 1.5.0 (Adventure, 3 acts)

- Done: 3 save slots (name, date, act, mode), name entry with keyboard or gamepad (on-screen
  keyboard), Normal / Veteran choice, delete with confirmation. The Veteran rules themselves come with the failure rules
- Failed mission: back to the workshop, no gain, a penalty that is higher when the score was low;
  Veteran = permanent death
- Act 1: weak Shield upgraded to about 80 % of the arcade ship
- Act 2: quests to obtain the Phenix (boss at the end) and first upgrades
- Act 3: both ships up to 100 %, epic final quest
- Story written together, French first, translations later

## Done in 1.4.5

- 144 Hz option (Options: 60 / 75 / 120 / 144) with an exact frame limiter
  (60 / 75 / 120 / 144 images per second instead of about 62 / 77 / 125 / 166)
- Smoother fullscreen on ultrawide screens: bezels no longer rebuilt every frame,
  the frame is drawn straight onto the screen (no 5 MB copy) and the redundant clear is gone
- No more stutter when a haut-fait progresses: achievements are saved in the background
- Title menu no longer rescans the Add-on (MAME) folders on every frame
- Explosions look the same at any refresh rate (60 / 75 / 120 / 144 Hz)
- Safer saves: settings, high scores, achievements and story are written atomically
  (a crash or power cut can no longer leave a truncated file); an unreadable file is kept as `.corrupt`
- `errors.log` next to the game records unexpected errors that used to be silent
- Developer tools: `tools/bench.py` (smoothness benchmark, `--profile`) and `tools/probe_present.py`

## Done in 1.4.4

- Starfield comet update
- New Add-on menu

## Done in 1.4.3

- Title-only seasonal overlays (Christmas / Halloween)
- April Fools logo gag (boot, 1 April)
- Starfield comet (1 per cycle, stages 1–4, rare on menus)

## Done in 1.4.0

- Stage-1 intro: ship arrives from the bottom (same as mid-run transitions)
- English announcer VO for stages 1–15 (5 / 10 / 15 include warning)
- Ship select: Welcome aboard Phenix / Shield
- Boss saucer rebuilt from photo tiles (rotating 2-row shield, pair-deco systems)
- Boss 500 / 1000 pts; ports glow; destructible keel beacon
- LVL5 draw cache (band, glows, living hit-order)
- i18n pass: UI still 13 languages; announcer remains English audio

## Done in 1.3.0

- Shield ship + select screen (solo / hot-seat / coop combos)
- Achievements page
- Jukebox + PHEQ1 visualizer + ID3 titles
- In-game music track option
- Stereo SFX, extra OST tracks
- Help page 2: Phenix and Shield
- Starfield: two extra asteroids (Dinkinesh pair + Pallas)
- Credits OST list uses the five ID3 titles
- i18n: jukebox hints and locked achievements in all 13 languages

## Done in 1.2.1

- Attract keeps the menu theme; session-only in-game audio mix (SFX / SFX+music / music / off)
- Music loops natively (no MP3 reload hitch)
- Help: animated stage-1/2 birds, looping Phenix, looping boss core
- Boss core tentacle cycle in the saucer (preloaded frames, centered blit)
- HUD: Novice / Veteran label (solo top-right, coop & hot seat centered under lives)
- Input swallows: quit-confirm No, attract Exit, Options/Credits Esc = back
- Help pages 13 s each; FPS counter shifted off the difficulty label

## Done in 1.2.0

- GPU present via pygame.SCALED (60 FPS with bezels on ultrawide)
- Refresh cap 60 / 75 / 120 Hz + VSync On / Adaptive / Off
- Options help panel (focused row)
- Packed pause Options list
- Stage-clear: leftover enemy shots removed before fly-up
- Collision restore + swept player / enemy bullets
- High-score cheats no longer abort on empty unicode (LVL2–5, LIVE, PHEN)
- Credits: hold to speed / reverse / drift; D-pad no longer leaves the screen
- Credits: beta testers, GPU line, GitHub + itch links
- Desktop cover + pad refocus when rebuilding the display

## Done in 1.1.0

- 2-player hot-seat and coop
- Autofire option, rumble, coop high-score mark
- Bezel GPU path experiments (superseded in 1.2.0)

## Done in 1.0.0

- PHENIX transform mode (gauge, morph, dual fire, cancel + cooldown)
- Ship / firebird art, boss core, enemy pass
- CRT scanlines (3 levels)
- Ultrawide bezels (Phenix, Tesla, Blue, Flame)
- Two-page help + starfield (planets & galaxies)
- i18n (13 languages), pause, difficulties
- Windows build via `build_exe.bat`

## Done earlier

- **0.2.0-rc.1** — feature-complete release candidate
- **0.1.0** — stages 1–5, boss, difficulties, high scores, 13 languages, attract mode

## Planned (post-1.2.1)

### Play & feel
- [ ] Native **144 Hz** path (cap already easy; exclusive modes still report 60 on some GPUs)
- [ ] Attract AI polish
- [ ] Optional separate lives in coop

### Packaging
- [ ] Optional one-file Windows build
- [ ] Linux package notes
- [ ] Batocera / `.pygame` pack (after a final PC freeze)

### Code health
- [ ] Split `src/game.py` into menus / combat / present modules
- [ ] Broader automated tests

### Meta
- [ ] Additional languages from contributors

Suggestions welcome via GitHub Issues.
