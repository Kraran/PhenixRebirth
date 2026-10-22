# Roadmap — Phenix Rebirth
Current release: **v1.5.0**

## Unreleased (towards 1.5.1)

- UI polish: the help of the "Control" option no longer says "Ou impose le clavier, ou la manette" (now "Tu peux aussi imposer le
  clavier ou la manette", rewritten in the 13 languages) and the help of "GPU render" no longer talks about "SDL upscale (SCALED)":
  "Lets the graphics card scale the picture". Text overlaps fixed: on the "new record" screen the score no longer sits on the bottom
  of the plate (everything under it hangs from the plate's real bottom), and on the help page 1 the subtitle no longer touches the
  title nor the text under it (`HELP_TITLE_Y`, `HELP_SUB_Y`). Tests: `tests/test_text_overlaps.py` (13 languages)
- Help screen: the keys and buttons it names are the ones the player really set (Options > Keys and buttons), no longer the
  defaults written in the texts. The "Controls" lines (keyboard 2 = the solo keys, first pad's table), the Phenix and Shield
  texts and the caption under their columns use the placeholders `{kb_move}`, `{kb_fire}`, `{kb_phenix}`, `{pad_fire}`,
  `{pad_pause}`, `{pad_phenix}` (13 languages), filled by `bindings.help_values` / `bindings.fill`. Tests: `tests/test_help_keys.py`
- Pause menu: a new "HELP / CONTROLS" row (between Options and Quit) opens the same two-page help as the main menu,
  drawn over the paused game, with the real keys; Left / Right (or the pad) turn the page, Esc / B comes back to the pause
  menu. Works with the keyboard, the pad buttons, the D-pad and the stick. Tests: `tests/test_pause_help.py`
- Enemy shots: a soft pink halo (18 px, additive, built once) lights the background around the shots of the enemies, of the
  Galaga / Invaders missions and of the saucer boss, so they stay readable over the stars and the sprites. The shot and its
  hitbox are unchanged (`src/bullet_halo.py`). Tests: `tests/test_bullet_halo.py`
- Adventure map and workshop (ergonomics): after the introduction the player lands on the Mission map (not on an empty
  locked Hangar) with the cursor on the next mission to fly, marked "NEXT"; the cursor goes on to the next mission after
  a story win. The map is grouped under headings (Act 1: replayable hunts, then the story, then bonus; Acts 2 and 3: the
  story first), a locked mission says "Opens after: <mission>", and the first sortie's text no longer says "dark birds" nor
  that the dome is offline (it stayed on the map in Acts 2 and 3), and the English journal tab is "STORY LOG" (the map
  is the "MISSION MAP"). HUD: the "DOME OFFLINE" reminder is quiet (grey, clear of the title) and is no longer shown for
  the Phenix, which never had a dome. Workshop: rows already at MAX go last, arrows show
  that more rows are above / below, a locked row says "Opens after: <mission>", and the French wall label reads
  "IMMUNISÉ". Texts in the 13 languages. Tests: `tests/test_story_map_ux.py`
- Adventure pause menu: in a mission the last row reads "ABANDON MISSION" (the arcade keeps "QUIT RUN") and asks
  "Abandon?" first, NO lit by default (Esc / B = NO); with the keyboard, the pad buttons, the D-pad and the stick.
  Leaving still gains and loses nothing. Texts in the 13 languages. Tests: `tests/test_pause_abandon.py`
- Adventure scenes and first sortie: B / Esc on the scene read before a mission (first launch) no longer drops back to
  the map, the mission flies at once like at the end of the scene. The very first sortie of a new pilot shows for 5 s
  (fade in / out, once the ship is in play) a reminder of the controls with the player's real keys and buttons:
  move, fire, pause. Texts in the 13 languages. Tests: `tests/test_story_skip_scene_help.py`

## Done in 1.5.0

**Adventure (beta)** — the story mode, Acts 1 to 3, is playable from the main menu ("Adventure (BETA)").

- Adventure: 4 save slots (pilot name, act, date, mode), Novice / Normal / Veteran (permanent death), a spoken and
  animated introduction, a journal, a Bestiary, a mission map, a hangar with a workshop, a paint shop
- Act 1: the weak Shield, Bestiary hunts, the dome series and its swarm, the gateway to Act 2
- Act 2: the Phenix, the paint series (a Space Invaders clone with our own enemies), the Avioid commander,
  the BONUS "two-dimensional impulse reactor" missions (Galaga-like chains), the VIP rescue (escort a cruise ship)
- Act 3: the attack of Phobos, the choice of the ship that keeps the quantum anchor, the refit to 100 %,
  wreck and convoy BONUS missions, the final series "la Riposte", the epilogue
- Story scenes with pictures and looping video clips, the introduction read aloud (French), the Phobos bar (Add-On)
- Loot items (Singularity Core, Genesis Core, Hyperion Reactor, Tesla Seal), 64 achievements in two pages
  (ARCADE 32, ADVENTURE 32)
- TEST mission "Asteroids": a free-flight level in the spirit of the Atari arcade game, with a differential
  multidirectional sky (nothing is won or lost)

**Game and controls**

- Rebindable controls: keys of the two keyboards and buttons of the pads (screen "Touches et boutons"),
  automatic "last device used" in solo, the control of each coop player
- Announcer up to level 31; "To boldly go" now asks for stage 31; cheat codes `LV02`–`LV99`
- In-game music: the four songs of Lyra Voss join the jukebox themes, and your own tracks can be dropped in the
  `musique_perso` folder
- New engine jets for every ship; the small asteroid Dinkinesh animated in the background
- Announcements (1UP, achievements, codes) are drawn in the scene, under the aliens and their shots
- From level 6 every enemy is worth more points (+10 per 5-level round)

**Quality**

- English comments and developer tools for the public repository; translations of the new texts in the 13 languages
- Many new automated tests (Adventure rules, controls, music, asteroids, translations...)

The detailed notes of the development are in [`docs/DEV_LOG_1.5.0.md`](docs/DEV_LOG_1.5.0.md).

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
