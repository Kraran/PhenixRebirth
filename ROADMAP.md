# Roadmap — Phenix Rebirth
Current release: **v1.6.0**

## Unreleased (towards 1.6.1)

- **Menus of the Adventure, station of Phobos (steps 1 to 3 of the upgrade).** The hub wears riveted black steel: plates with a hazard
  strip, a copper cartouche for the title, steel badges for the pilot and the hull, lit rows with a gold edge, steel tabs and a steel
  help bar with copper keys. Each pane has its own picture behind it (the bar of Phobos for the map, the hangar, the corridor, the cabin and the
  walkway), made by `tools/make_ui_backdrops.py` and loaded on first use; the starfield is no longer drawn under the hub. The classic
  menus are untouched. The insides of the hangar, bestiary, journal and extras follow in the next steps. Tests: `tests/test_phobos_ui.py`.

- **Lunar Lander test: five settings and a menu to choose one.** Europa (bright ice with long red-brown fractures, Jupiter in the sky),
  Deimos (dark dusty rock with worn craters, Mars in the sky; almost no gravity) and Triton (pinkish "cantaloupe" ice with dark
  streaks, Neptune in the sky) join Titan (Saturn in the sky) and the asteroid (other asteroids in the sky). The mother planets
  come from the photographs of the game. A menu before the flight picks the setting (to be taken out of the final missions).
  Tests: `tests/test_lander_bodies.py`.

- **Review of the texts of the Adventure.** Veteran variants of the four scenes that counted on the quantum anchor (Kamarasov is dead
  there: "there is no anchor to bring me back"); "Acte" everywhere, never "chapitre"; the dead texts of the old gate mission
  (it unlocked the dome, Dôme V does now) taken out; the NX01 sleeps "in orbit of Mars, on Phobos"; the khaki birds have a
  metallic skin (no plumage); "Bleus"/"Kakis" written the same way; the VIP thanks you for what you did "near Phobos"; "more
  than two years after the silence"; the Guardians and the Lander speak to "tu"; the paint shop names the hull it paints
  (Shield or Phenix); Dôme I is named after its scene ("l'épave du Shield"); Alcyone is 440 light-years away; small fixes
  (Sentinelle I, "Phenix" without accent, Peinture I). French and English; the other languages follow where the change is
  mechanical. Tests: `tests/test_text_review_1_6_1.py`.

- **BONUS - Lunar Lander.** The same level as the test, with its menu of five settings (the menu stays), but for real: a landing
  pays its points (plus the fuel left) in credits, a crash costs what a failure costs. Secret until the game is finished (the
  open ending told), then on the map of every act, replayable. The test mission stays a test (nothing won, nothing lost).
  Also: the stars of Europa, Deimos and Triton now pass BEHIND the mother planet, and the pictures of the menu load about twice
  as fast (faster noise and cells, same pixels) and are made in the background while the menu is read.
  Tests: `tests/test_lander_bodies.py`.

- **Visual novel: the four endings.** After the reaction to the last scene, an ending is told on the same picture, chosen by the
  total of points: Fâcherie (5–8), Distance (9–12), Amitié (13–16), Romance (17–20), each ending on its last line.
  Amitié and Romance: Lyra gives points × 500 credits (paid once). Romance: every price of the workshop (upgrades, items,
  launcher, missiles, paint) is 10 % lower, for good. A save that had already answered the last scene gets its ending after
  its next story mission. The cheat VNOV tells the ending without gift nor sale. Tests: `tests/test_vn_endings.py`.

## Done in 1.6.0

**Adventure** — the story goes on, and now ends.

- Open ending, "Acte IV - No Mercy Left": once Triton is won, the mission "Alcyone - Le Grand Saut" (a scene, the film "The End", the
  credits, with "No Mercy Left" by Lyra Voss playing); after it every mission can be flown again and all the acts are on the map
- Visual novel: five scenes with Lyra Voss between the missions (Phobos bar, hangar, observation deck, refuge, transit terminal), four
  answers each, a reaction to each
- EDF - Silent Sentinels I-IV (a remake of the 1977 Spacewar, one mission per gas giant) and the antimatter missile: the workshop sells the
  launcher (5000, permanent) and the missiles (500, consumable)
- Asteroid belt as the prelude of the main series of each act; TEST mission "Lunar Lander"
- The Guardians: 3 HP, a life bar, wings that are shot off and grow back, fire bolt and death in the flames
- Mission map and workshop ergonomics (next mission marked, "Opens after...", Page up / Page down and LB / RB), journal in two
  zones, "Abandon mission" asks first, controls reminder in the first sortie, prices that follow the income of each act
- Fixes: the Singularity Core falls in its BONUS mission; no black hole nor ringed planet behind the missions and the menus of the Adventure

**Game and controls**

- Secret codes on the high-score screen work on an AZERTY keyboard, and take the codes of the Adventure (`UNLK`, `2222`, `3333`,
  `NIX2`, `FINE`) and `VNOV`
- The help screen shows the keys and buttons you really set; a "Help / Controls" row in the pause menu
- Enemy shots have a soft halo; the AI of the birds is the same at 60, 120 and 144 images/s; every explosion of the ship is the big blast
- Announcements are drawn over the boss saucer and under the enemies and their shots

**Quality**

- Many new automated tests (visual novel, SpaceWar, Lander, Guardians, cheats, workshop, map, translations...)

The detailed notes of the development are in [`docs/DEV_LOG_1.6.0.md`](docs/DEV_LOG_1.6.0.md).

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
