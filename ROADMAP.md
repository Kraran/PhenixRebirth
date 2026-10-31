# Roadmap — Phenix Rebirth
Current release: **v1.5.0**

## Unreleased (towards 1.5.1)

- Notifications (banners, loot notices, mission counters, HUD) are now drawn over the body of the boss saucer. The enemies and every shot,
  the shots of the saucer included, stay over them as before. (`BossSaucer.draw` is split into `draw_body` and `draw_shots`.) The small
  saucers that cross the paint missions and the asteroid belts are enemies like the others and stay over the notifications.
- Adventure: visual novel scene 5 (leaving for Eloncity, "Ce qu'on emporte avec soi"). In the transit terminal of Phobos, Lyra asks the
  pilot whether he would like to see her again: a staging in narration, six pages, four answers (hidden points 1, 2, 3, 4, random order)
  and a reaction to each (the last one in five pages). It comes after the next story mission won once scene 4 is answered. Lyra's face is
  near the middle of the picture, so the text panel is narrower and further right (a new `panel_x` setting of a scene) and the panel of
  the answers can now grow up to 840 px in more steps. New picture `assets/story/vn_5_depart.jpg`; the cheat `VNOV` lists it too.
- Adventure: visual novel scene 4 (the refuge, "Une chanson pour personne"). During a partial curfew the pilot hears a guitar and finds Lyra
  singing alone, without an audience, who asks him to forget it: a staging in narration, four pages, four answers (hidden points 2, 3, 4, 1,
  random order) and a two-page reaction to each. It comes after the next story mission won once scene 3 is answered (the series and the
  asteroid belts count). Lyra is on the right of the picture, so the text stays on the left. New picture `assets/story/vn_4_refuge.jpg`;
  the cheat `VNOV` lists it too.
- Adventure: visual novel scene 3 (the observation deck, "La femme derrière la voix"). Lyra listens to a demo for the Eloncity concert
  and asks for an opinion: a staging in narration, four pages, four answers (hidden points 1, 3, 4, 2, random order) and a reaction to
  each. It comes after the next story mission won once scene 2 is answered (the series and the asteroid belts count). The text sits on the
  right of the picture; the panel of the answers only grows as wide as it has to (up to 840 px) so that the face of Lyra stays seen as
  much as possible. New picture `assets/story/vn_3_pont.jpg`; the cheat `VNOV` lists it too.
- Adventure: scene 2 of the visual novel (the hangar) rewritten like scene 1: a staging in narration, Lyra's lines, four new answers
  (hidden points 1, 3, 2, 4, shown in a random order) and a reaction of Lyra to each, in four pages. A save that already answered scene 2
  keeps its pick number, which now means the answer with the same number in the new list. The picture is unchanged for now.
- Cheat code `VNOV` (typed on the HIGH SCORES screen, like `LIVE` / `PHEN`; typed again it goes off): in the Adventure every film and
  scene of the visual novel is listed in the journal and can be told at once, whatever the missions won or the scenes answered. Nothing is
  saved (the "CHEAT - NOT SAVED" banner, like `UNLK`), the answers are not kept (a scene answered for real is told afresh and its real
  answer is untouched) and Lyra still reacts to the answer chosen. It does not touch the arcade high scores. `story_state.journal_entries`
  takes `cheat_vn`; the Adventure reads `game.cheat_vn` when it is opened from the main menu.
- Adventure: scene 1 of the visual novel rewritten. The text is now a conversation in three pages (Lyra's words in white, the narration
  in blue-grey; A shows the page, then the next one), the four answers are new (hidden points 2, 3, 4, 3) and come in a random
  order each time (the saved pick is still the index in the list, so the points do not depend on the order shown; watched again, the
  list is in its own order). After the answer Lyra reacts (a text per answer, same pages), then the map comes back; watched again from the
  journal, the reaction follows too. A page of long answers uses a wider panel so everything fits. A save that already answered scene 1
  keeps its pick number, which now means the answer with the same number in the new list. New in `story_vn`: `pages`, `page_length`,
  `tidy`, `reaction`, `order`; the scene keys `shuffle` and the third item of an answer (its reaction).
- Adventure: visual novel scene 2 (the hangar). Lyra asks "Were you afraid, up there?" (four answers, hidden points 1 to 4) when the
  map is back after the next story mission won (the series and the asteroid belts count, hunts, bonuses and paint do not). A scene
  without a film comes after the previous one: `after` and `wins` in `story_vn.VN_SCENES`; the answer remembers the story missions won
  (`vn.marks`), a save made before counts from its next win. The text can sit on the right of the picture (`panel`). Watched again from the
  journal (`{"vn": id}` lines). New: `story_state.story_wins`, `vn_due`, picture `assets/story/vn_2_hangar.jpg`.
- Adventure: the visual novel begins. Right after the third song of Lyra Voss's concert, a film of the Phobos bar, then scene 1: Lyra's
  question and four answers (hidden points 1 to 4, kept in the save as `vn.picks`; the answer is final). The scene is watched again from
  the journal (the answer given is lit). A save made after the concert tells it when it is opened. Texts in French and English (the
  other languages show English for now). New: `src/story_vn.py`, `StoryHub` screen `vn`, `tests/test_story_vn.py`.
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
- Adventure journal: the "watch again" lines (the introduction, the scenes and films seen) no longer fill the screen.
  The tab has a "GOAL: <next mission>" line, then two zones: "SCENES TO WATCH AGAIN" (4 lines, the cursor is there)
  and "LOGBOOK" (6 lines, what happened; it scrolls), each with arrows when there is more above / below. Up / Down keep
  their meaning (cursor through the scenes, then the logbook scrolls). Texts in the 13 languages.
  Tests: `tests/test_story_journal_layout.py`
- Adventure workshop prices follow the income, which doubles with each act: the Phenix pays more than the Shield for the steps
  they share (speed 80 % 2 000, walls: slow down 3 000, lives 4 000, gauge 80 % 3 000) and the Act 3 rows are dear (speed 100 %
  4 000, lives 5 000, walls: immunity 4 000, gauge 100 % 5 000, the dome lasts longer in two steps: 2 000 then 3 000). The Act 1
  prices of the Shield, the paint shop (500) and the loot items are unchanged. Tests: `tests/test_story_prices.py`
- Adventure asteroid belt: the Asteroids level leaves the test missions and becomes the prelude of the main series of each act
  ("Asteroid belt I / II / III": 60, 80 then 100 rocks to destroy, a road through the belt). It sits on the map right before
  Dome I, Phenix I and Riposte I (Riposte: after the hull is at 100 %), which it now opens. It is replayable, paid every time
  and follows the usual rules of failure (Normal and Novice lose a share of the points, the Veteran falls). Each one is told by a
  scene before the first launch (the picture will come later, a dark sky until then, journal line, French and English). The
  cheats 2222 and NIX2 count the belts of their act as crossed, and an old save whose series is already started skips the
  belt. Tests: `tests/test_story_asteroids_series.py`
- TEST mission "SpaceWar" (`src/spacewar.py`): a remake of the 1977 arcade Spacewar, on the map of every act, replayable, a training mission
  (nothing won, nothing lost, nobody falls). A star (Jupiter) in the middle pulls the ships with a Newtonian gravity (g = GM / r^2; the
  torpedoes are not pulled), inertia with no friction (a constant turn does not change the way the ship travels), the screen joined on
  its four sides, the ship of the hangar (Shield or Phenix) with one life: destroyed by a torpedo, by the star or by touching another
  ship, it ends in pixel dust (`ship_burn`, turned to the nose). Three levels of birds with the same physics and a small pilot
  (1 blue / 1 blue and 1 green / 2 blue and 2 green, faster at each level), a stock of torpedoes (20 for the player, 8 per bird, a reload
  delay, a few in the air at once); the test ends when the ship is destroyed, when the three levels are won, or when nobody has a torpedo
  left. The constants are tuned so that the "CBS opening" (nose at right angles to the star, thrust for 2 to 3 s) gives a stable orbit.
  Tests: `tests/test_spacewar.py`
- SpaceWar, second round (Kraran's first tests): the ship starts farther from Jupiter (340 px), the player's ship is drawn and hit at
  half its size (its dust too), the hit zone of the star is the disc that is drawn, torpedoes (the birds' too) are stopped by the
  star, stronger thrusters for the player (75 against 58 for a bird, gravity raised to 1e7 so that the CBS opening of 2 to 3 s still
  gives an orbit), the torpedoes of the player are drawn as torpedoes (metal body, nose in the colour of the hull, fins, flame), the
  HUD no longer counts the birds, and a small asteroid of the Asteroids level crosses the screen now and then (comes in from
  outside, pulled by the star, no wrap, destroys the ship and the birds, a torpedo breaks it; its path ends on the star less than
  one time in three).
- SpaceWar, third round (Kraran's second tests): the pull of Jupiter is halved (GM 5e6, it was 1e7: far too hard), so the push of
  the CBS opening is now about 1.3 s (the ship also has more time to correct), no planet or asteroid behind the level (the
  starfield has `set_bare`), the torpedo of the player is drawn as an air-to-air missile (slim fuselage, ogive nose in the colour of
  the hull, canards, swept tail fins, red band, plume), and three more levels, TEST - SpaceWar with Saturn, Uranus or Neptune in the
  middle (same rules, same map of every act, `spacewar.PLANETS`: the disc (Saturn 64 px, Uranus 40, Neptune 38, rings of Saturn
  are drawn but not in the hit zone), the pull (2.7e6, 1.5e6, 1.6e6) and the thrust of the ships (x0.6) follow the real order but are
  brought closer to Jupiter's so that it stays playable; pictures made by `tools/make_spacewar_planets.py`). Tests:
  `tests/test_spacewar.py`
- SpaceWar, fourth round (Kraran's third tests): the thrusters of the player are stronger (110 px/s^2, it was 75; the pull is not
  touched), the birds collide far less (they start each on its own circular orbit, `LANES`, all going round the same way, and a bird
  only pushes when the orbit it makes stays out of the star and inside the screen and shares no distance from the star with
  another bird's orbit, `Bird._coast_is_safe` / `orbit_band`; it holds its heading while it pushes: in a simulation of 60 s the
  collisions went from about 0.7 (level 2) and 1.6 (level 3) a game to 0.03), and the torpedoes of the birds no longer come round the
  screen (they end at the edge; the player's still do). The CBS opening is now a push of about 0.9 s on Jupiter (1.4 Saturn, 1.0
  Uranus and Neptune). Tests: `tests/test_spacewar.py`
- SpaceWar, fifth round (Kraran's fourth tests): the torpedoes of the enemies are slow (230 px/s, they last 3.4 s) so that they can be dodged, the birds lead their aim with that speed; the third level is now 2 blue birds, 1 green bird and the small boss saucer (3 hits, a red flash and a life bar, 14 torpedoes, radius 27; a ram or a crashing bird does not hurt it, the ship dies) and is won when the saucer is destroyed; the ship ends in a big blast (`src/ship_blast.py`: the hull in glowing shards, flash, fireball, two shock rings, sparks, embers, smoke; the guardians keep the pixel dust). Tests: `tests/test_spacewar.py`, `tests/test_ship_blast.py`
- Every explosion of the ship of the player is now the big blast of the SpaceWar level (`Game._ship_boom` → `src/ship_blast.py`): in the arcade game and in the Adventure (bullets, divers, boss hull, edge lightning, the invaders' floor, the Asteroids mission, the guardian lasers, hot-seat and co-op); a ship that is hit but not lost hides its hull for 0.55 s while it breaks up and comes back blinking. The fantasy ringed planet (`fantasy_rings.png`) no longer appears in the background of any mission of the Adventure (`Starfield.set_adventure`); the arcade game keeps it. Tests: `tests/test_ship_boom.py`, `tests/test_ship_blast.py`
- EDF - Opération Sentinelles silencieuses I-IV (SpaceWar, seventh round): four Adventure missions built on the SpaceWar level, one per gas giant (`story_state.MISSIONS` `sentinelle_1..4`, `sw_levels` = (blue, green, saucers) per level: I 2 levels, II-IV 3 levels; a level with a saucer is won when it is destroyed). Not training missions: the birds pay their normal points (`SpaceWarFormation(points=True)`, blue 10 / green 20 / boss saucer) and a failure costs the normal penalty (Veteran: the pilot falls). Opened in order (I from the start of Act 1, II and III in Act 2, IV in Act 3), flown once each until IV is won (flag `sentinelles_done`, key `replay`), then all four are playable again. Briefings with the pilot's name over `sentinelle1_jupiter` / `sentinelle4_neptune` clips (slowed to 0.6x, loop, no sound: `tools/encode_clip.py --slow`) and the stills of Saturn and Uranus. Tests: `tests/test_sentinelles.py`. Still to come: the antimatter missile unlocked by IV.

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
