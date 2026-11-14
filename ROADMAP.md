# Roadmap — Phenix Rebirth
Current release: **v1.7.2**

## Done in 1.7.2

**Adventure** — Defence of Phobos with Sacha the wingman, FINAL BONUS - Swarm, and the fixes of a full playthrough.

- Defence of Phobos I, II and III: one compulsory mission per act (after Dome V, after Phenix II, after Guardians III).
  The swarm rushes at Phobos in four waves, each adding a kind (blue, khaki, gargoyles, dark gargoyles), at level 11,
  16 then 21; 3 Guardians in the last wave of II and III, more enemies in II and more again in III. Each has its
  scene; a save already further on is not held back
- Sacha, a young pilot of Phobos, flies beside the ship in his old EDF-17 C, flown by the computer: he comes in from
  below a few seconds into the first wave, dodges like a good pilot (not a perfect one), shoots the birds above him
  (his points are his own), and gets a little better from one Defence to the next. He cannot die: three hits or a
  collision and he flies home to Phobos; his ship shows its damage and its jets smoke more and more. He talks on the
  radio, with his voice. His story is told after the first victory
- FINAL BONUS - Swarm (Nuée), once the game is finished: the last wave of Defence of Phobos II without an end, then
  Guardians again and again. Five versions: alone, with Sacha flown by the computer (sharper, he comes back repaired),
  two players (Sacha flown by player 2), Sacha alone (you fly the EDF-17 C) or Sacha leading (the computer flies your
  ship). 10 % of the score in credits at the GAME OVER (5 % of the two scores at two), one record per version
- The map suggests the Silent Sentinels before la Riposte (Neptune before Triton, as the story tells it; they stay
  optional), and never suggests an optional mission (the paint series, a BONUS)

**Game**

- The achievement banners wait their turn in a queue: never two at once, none lost; one cut by a 1UP, a code or the pad
  comes back after it
- The results of a mission read "Failed · nothing lost", "Failed · -X PTS", "Mission clear · +X PTS" (13 languages)

**Fixes**

- With infinite lives (the LIVE code), invaders reaching the ship or the boss saucer reaching the floor no longer
  freeze the mission: the ship blows up once and the grid (or the saucer) goes back up
- The explosion of the ship no longer slows the game: its big glows are drawn from rings prepared at the start, the
  same pixels as before
- The arrival of the Guardians and the ash of the gargoyles no longer freeze the game for a moment (prepared behind
  the loading bar); the fire of a burnt enemy is drawn about twice as fast
- Texts: the Avioid commander scene (Bestiary V) names the birds that really come, Silent Sentinels IV still makes
  sense after the victory, typographic apostrophes in the Act IV text
- Details: [docs/DEV_LOG_1.7.2.md](docs/DEV_LOG_1.7.2.md)

## Done in 1.7.1

**Adventure** — FINAL BONUS - Space War, a tighter gate after Bestiary I, tighter landing tanks, and the intros of the asteroid belt.

- FINAL BONUS - Space War: an endless run around the gas giant chosen in the menu (Jupiter, Saturn, Uranus or Neptune)
  and its gravity. 20 torpedoes, renewed at each level; one life; a saucer every five levels. The run ends when the ship
  is lost, or when no missiles are left while enemies remain: its points pay in credits, without a penalty. Nothing is
  won if it is left from the pause. One record per planet. The workshop antimatter missile, if it is unlocked, is one
  per run
- Bestiary I - First sortie, once won, unlocks Asteroid belt I and EDF - Silent Sentinels I: Jupiter, which are no
  longer open from the start; a save that already had them keeps them
- The intros of Asteroid belt I, II and III have their pictures and looping clips
- Tighter starting fuel on the landings: Deimos 90, the asteroid 80, Europa and Titan 70, Triton 60, and 90 at the start
  of FINAL BONUS - Lunar Lander; the descriptions follow

**Game**

- Options > GAMEPLAY, Adventure style: a Guardians option, as in FINAL BONUS - Guardians (off by default; the game
  always starts in Classic)

**Fixes**

- The boss saucer: destroying both dishes halves the descent speed instead of stopping it
- Details: [docs/DEV_LOG_1.7.1.md](docs/DEV_LOG_1.7.1.md)

## Done in 1.7.0

**Adventure** — escort modules, landings and raids, the Guardians, and endless bonus runs once the game is finished.

- Landings and raids: five optional Lunar Lander missions (Deimos, an asteroid, Europa, Titan, Triton) and five raids on the Avioid
  bases of the same places, from the gentlest scroll to the full Scramble (the red commander takes 3 to 5 hits), each with its scene
- Escort modules: two gyroscope satellites that fly beside the ship and fire with it (shots ×2, then ×3). Their pieces are found in the
  landings and raids, they are assembled at the workshop, they take the shots meant for the ship, and a destroyed one is bought again at
  half price
- The Guardians: the series Guardians I, II, III and Bestiary VI, with the Alpha Guardian; once Guardians III is won, a reflective
  coating lets the dome and the Phenix form split their laser in two; Guardians also come as reinforcements in some waves (Phenix III,
  the great raid, the repairs, la Riposte); gargoyles burnt by a laser fall in ashes
- END BONUS, once the game is finished: FINAL BONUS - Asteroids, - Guardians, - Lunar Lander and - Scramble, endless runs that pay their
  points in credits without a penalty until the ship is lost, each with its record and the voice announcing every level
- Scramble: armoured casemates for the missile launchers of the base (a first shot leaves a wreck that stops your shots, a second one
  blows it away); comets that come from behind; the far cry of the red commander echoes through his fortress 2 s after the last
  missile station has left the screen
- The scenes of Bestiary I and of the VIP rescue (Lyra Voss) are read aloud in French, like the intro
- The four TEST missions are gone, and the Adventure is no longer marked "(Beta)"
- Credits are capped at 99 999

**Game**

- Options > GAMEPLAY: an Adventure style for a solo arcade game, with escort modules, antimatter missiles (1 to 20) and the 2D reactor
  (no high score; the game always starts in Classic)
- A loading bar at the start of the game and when a heavy mission of the Adventure starts; the setting menus of Lunar Lander and Scramble
  are fully prepared behind it
- A level ends once the last explosions are over (the Guardians' too)

**Fixes**

- The boss alien is solid: no see-through body or tentacles, the inside of its mouth opaque black (green saucer and red commander)
- Asteroids: three rock shapes per size; the saucer no longer wraps round the screen and its sound no longer stops after a moment
- Lunar Lander missions no longer carry the antimatter missile
- Texts: the GAMEPLAY options, the key of the missile and the codes of the high scores are translated in the 13 languages; the help of
  the refresh cap lists 144 Hz
- Details: [docs/DEV_LOG_1.7.0.md](docs/DEV_LOG_1.7.0.md)

## Done in 1.6.2

**Adventure** — a Scramble level, and Lyra Voss sings again.

- Scramble, a remake of Konami's 1981 arcade game: TEST - Scramble on the map of every act, and BONUS - Scramble once the game is
  finished. A flight through the rock of one of the five Lander settings, missile stations, waves of birds and comets, the enemy base and
  its red Avioid commander (3 hits, a life bar); the Shield dome and the Phenix mode work there, the launchers and the commander join the
  Bestiary
- The codes LIVE and PHEN work in the missions of the Adventure
- Visual novel: the two best endings (Amitié, Romance) go on with the concert of Lyra Voss in Eloncity, a film and its song
- "When We Looked Up" (and its Unplugged version, under scenes 3 and 4 of the visual novel) in the jukebox and the in-game music

**Jukebox**

- A new layout: the whole list in groups, a card for the track playing, and the lyrics of the six songs of Lyra Voss, synced on her voice
  and translated in the 13 languages; in the style of the station of Phobos when opened from the Adventure

**Fixes**

- The scenes after the fall of the NX01 or of the Phenix say what Huygens is; the antimatter missile costs 1000 credits; the credits
  name the songs of Lyra Voss, "Phoenix (1980 - Taito)", "Claude - Anthropic" and "Pleiades (1981 - Tehkan)"
- Details: [docs/DEV_LOG_1.6.2.md](docs/DEV_LOG_1.6.2.md)

## Done in 1.6.1

**Adventure** — the menus change clothes, and the story gets its endings.

- Menus of the Adventure rebuilt as the station of Phobos: riveted black steel plates with hazard bands, holographic hull cards, CRT
  terminals for the bestiary and the journal, a steel help bar; the saves, the pilot name, the mode, the hull and the Lander menu follow,
  and the Jukebox and the Add-On show the bar of the station when opened from the Extras. Airier layouts and smaller letters; the text of
  the mission under the cursor is written in up to four lines; checked in the 13 languages (`tests/test_phobos_fit.py`)
- Visual novel: four endings (Amitié, Romance, ...) told after the last scene; Romance makes every price of the workshop 10 % lower
- Lunar Lander: five settings (asteroid, Titan, Europa, Deimos, Triton) and a menu to choose one; the BONUS mission
- Review of the texts of the Adventure (veteran variants of four scenes)
- Details: [docs/DEV_LOG_1.6.1.md](docs/DEV_LOG_1.6.1.md)


## Done in 1.6.0

**Adventure** — the story goes on, and now ends.

- Open ending, "Acte IV - No Mercy Left": once Triton is won, the mission "Alcyone - Le Grand Saut" (a scene, the film "The End", the
  credits, with "No Mercy Left" by Lyra Voss playing); after it every mission can be flown again and all the acts are on the map
- Visual novel: five scenes with Lyra Voss between the missions (Phobos bar, hangar, observation deck, refuge, transit terminal), four
  answers each, a reaction to each
- EDF - Silent Sentinels I-IV (a remake of the 1977 Spacewar, one mission per gas giant) and the antimatter missile: the workshop sells the
  launcher (5000, permanent) and the missiles (500 in 1.6.0, 1000 since 1.6.2, consumable)
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
