# Roadmap — Phenix Rebirth
Current release: **v1.4.5**

## Unreleased (towards 1.5.0 — Adventure)

- Adventure code reorganised, nothing changes on screen: rules and save data now live in
  `story_state.py` (tested without a window), `story.py` only draws the menus
- Adventure save is now one file per slot (`story_1.json` … `story_3.json`, version 4).
  The old draft `story.json` is no longer read; start a new adventure
- Dome time and recharge are saved in seconds (no longer tied to 60 Hz)
- The adventure journal follows the language chosen in Options
- Adventure menus: texts are now centred inside their boxes (hangar, workshop, mission map, journal)
- No more frozen explosion pieces on the menu after an adventure mission
- Adventure start: slot list (3 saves with pilot name, act, date and mode), pilot name entry, Normal / Veteran choice
- Adventure failure rules: a failed mission (death) gives no points and costs 5 % of your points; Veteran mode has permanent death. Quitting a mission by choice changes nothing
- Act 1 hangar: the Shield starts slow (40 % speed), with one life, no dome, and dies the moment
  it touches the screen edge. The workshop sells speed 60 % then 80 %, a second life, and the arcade
  edge rule (slowdown, then death if you stay too long). The dome becomes a series of quests (Act 2).
  Prices: 300 / 800 / 2000 / 1000. The Phenix slot shows as empty and cannot be selected in Act 1.
  Saves from the earlier draft are converted (speed steps move down, dome back offline)
- Adventure intro: after the name and the mode, 4 slides (Huygens, its destruction, Phobos, Kamarasov)
  scroll like the credits over a picture. Action button = next slide, B / Esc = skip. Shown once per
  adventure. Veteran mode has its own last slide: Professor Kamarasov died before finishing the
  quantum anchor. The last sentence carries the pilot's name. Up / Down (or the pad) change the
  scroll speed smoothly, as in the credits. The journal always starts with "Watch the introduction
  again". French text first (other languages show the same text until translated)
- Adventure Bestiary: a new screen left of the journal. Each enemy shows up once you have destroyed
  one (picture), then at 50 (picture twice as big), 100 (animated), 150 (presentation text) and 200
  (every such enemy is worth +10 points, the Veteran bonus of the arcade game). Bosses use a short
  table: 1, 2, 3, 5 and 10 defeats, the last one adding +1000 points per boss. Enemies destroyed
  count even when you lose a mission, but not when you leave one by choice. Names are drawn smaller
- The four Bestiary sorties of Act 1 are "hunt" missions that can be flown again as often as you like
  (shown as REPLAYABLE). The journal writes, under each one, how many enemies were destroyed in all
  its runs

- Adventure journal: only "Watch the introduction again" can be selected; Up / Down scroll the other
  lines (mission comments and kill totals are not selectable)
- Adventure cheat UNLK (typed on the mission map): every mission can be played without unlocking it.
  While it is on, nothing is saved (a small red banner at the top left says so); loading the save again starts clean

- Adventure, dome series (Act 1): four chained missions after the Bestiary sorties. Each one flies three
  waves in a row of one enemy kind at the speed of arcade levels 1 / 6 / 11 (Blues), 2 / 7 / 12 (Khakis),
  3 / 8 / 13 (Gargoyles) and 4 / 9 / 14 (Dark Gargoyles). Clearing one opens the next; a cleared one
  cannot be flown again (the four Bestiary sorties stay replayable). The old "chapter relief" mission is
  replaced by this series

- Adventure, Dome V "the swarm": the four enemies at once (levels 11 to 14, speed of level 11), each kind
  replaced as it falls, up to three times its normal count in all (39 / 66 / 21 / 30), but only a third of
  a normal screen at once (4 / 7 / 2 / 3 on screen). It is won when all of them are down; a counter shows how many are left. It brings the dome online and opens the
  first dome upgrade in the workshop
- Adventure, levels of the Bestiary sorties: each victory raises the mission one level (1, 2, 3...). Level 2
  flies the same enemies as arcade level +5 (a little faster each time, no limit). The level is shown on
  the mission map, in the journal and on the screen during the mission. A lost run keeps the level
- Adventure, Act 2: after the gateway the map changes (title "ACT 2"): the four Bestiary sorties stay (with their
  level), the dome missions are gone, and a series of five missions appears, each one opened by the previous
  and flown once only (arcade levels 16 and up, x1.3 speed): the signal (16-17), the jamming (the swarm at
  level 16), the relay (18-19), the approach (16-19) and the awakening (16-20, boss). The last one hands
  over the Phenix: slot 2 of the hangar opens, with its own workshop (speed 80 %, lives 2, walls, and the
  Phenix gauge 60 % -> 80 %: the Phenix form lasts 60 % of the arcade one at first)
- Adventure, Act 2 paint series: three optional missions flown in order, each a Space Invaders clone with our
  own enemies: 4 rows of 11 (bottom to top: blue birds, khaki birds, gargoyles, dark gargoyles, all animated)
  march in step from side to side and drop one line together when a wall is touched, then turn back; the
  march speeds up as the grid empties. Now and then a miniature of the boss saucer crosses the top: 500 to 1000
  points, the more centred the killing shot, the more it pays (it does not have to be killed to win). An enemy
  reaching the ship's line ends the run. The three missions are levels 1, 2, 3 (faster and lower each time);
  flown again as a whole series (to change colour again) they are levels 4, 5, 6, then 7, 8, 9, and so on.
  The 2nd and 3rd missions of a pass start one and two lines (grid rows) lower; the wings flap at a steady pace.
  Sounds: a step sound for every march step (very slightly higher the faster the march) and the saucer sound,
  waved to last as long as the saucer takes to cross the screen.
  Winning the third opens the paint shop in the Shield workshop for ONE change of colour (red, green, violet).
  The level is shown on the map, in the journal and on screen
- Adventure, hangar: the two hulls are drawn like the ship select screen (portrait in a frame, gold frame and
  slight bob for the chosen one, the other one dimmed the same way), without the Phenix / dome animations.
  The chosen hull flies every mission (the map shows "SHIP: ..."); a mission can impose a hull later
  (`ship` field of a mission, none uses it yet)
- Adventure, cheat code 2222 on the mission map: jumps to Act 2 (every Act 1 mission counts as won, the Phenix
  is not given). Nothing is saved any more afterwards (red banner, like UNLK); reloading the slot goes back
  to the real save
- Adventure, Phenix swarm (mission 2 of the Phenix series): one normal screen of each enemy in all (52), not three
- Adventure, cheat code NIX2 in the hangar: Act 2 on, the five Phenix missions won, the Phenix unlocked; nothing saved
- Adventure, gateway to Act 2: a full run of arcade levels 11 to 15 (wave counter on screen). The death of
  the boss starts Act 2 (the save shows ACT 2). The mission map scrolls now that it is longer

### Planned for 1.5.0 (Adventure, 3 acts)

- Done: 3 save slots (name, date, act, mode), name entry with keyboard or gamepad (on-screen
  keyboard), Normal / Veteran choice, delete with confirmation
- Done: failed mission = back to the workshop, no gain and 5 % of your points lost (rounded,
  never below 0); Veteran = permanent death (the save becomes a memorial).
  Quitting a mission by choice changes nothing (no gain, no loss, back to the hangar)
- Act 1: weak Shield upgraded to about 80 % of the arcade ship. Done: the Act 1 hangar and workshop
  (speed, lives, walls); to come: the Act 1 missions and story
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
