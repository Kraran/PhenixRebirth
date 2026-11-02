# Development log — Phenix Rebirth 1.6.0

The detailed notes kept while the visual novel, the open ending, the SpaceWar, Lunar Lander and Guardian work and the other 1.6.0
changes were written. The short version is in the [ROADMAP](../ROADMAP.md) ("Done in 1.6.0"). Some game texts are quoted in French,
the language they were first written in. The newest entries come first.

- Fix: the menus of the Adventure (and the screens opened from it: credits, options...) show neither the black hole (`galaxy_blackhole.png`) nor the fantasy ringed planet (`fantasy_rings.png`) in the background, like the missions (`Starfield.set_adventure` is now on in the Adventure menus too). Tests: `tests/test_story_menu_background.py`.
- Adventure: the antimatter missile is now bought in the workshop list (the fifth stat box, which overflowed, is gone). Once Silent
  Sentinels IV is won, the list offers the **launcher** (5000 PTS, permanent) and the **missile** (500 PTS, consumable, up to 9 held; it needs
  the launcher). A mission carries a missile only with the launcher and at least one missile held; a missile that is not fired stays for the
  next mission, a fired one is used up at once (written to the save).
- Fix: the Singularity Core now falls in the BONUS mission "le convoi de la Singularité" (the launch did not pass the item of the mission
  to the game, so no plan to drop it was made).
- Fix: the black hole (`galaxy_blackhole.png`) never shows behind a mission of the Adventure (the arcade game keeps it).
- Fix: the secret codes of the high-score screen. The digits (LV02, 2222...) come from the physical key, so they work on an AZERTY
  keyboard too (it gave "&", "é"...); the same on the mission map. The codes of the Adventure (`UNLK`, `2222`, `3333`, `NIX2`, `FINE`)
  are taken on the high-score screen as well, and take effect when the next pilot is opened (like `VNOV`).
- Adventure: the open ending, "Acte IV - No Mercy Left" (a pseudo act with one mission, "Alcyone - Le Grand Saut"). It appears on the map
  next to Act 3 once Triton (Riposte V) is won. It has no sortie: the scene (picture `assets/story/fin.jpg`, the text of the jump to the
  Pleiades), then the film `assets/video/theend.mp4` (no loop: its last picture waits for a key or a button), then the credits, then the
  workshop. "No Mercy Left" by Lyra Voss plays in a loop from the scene to the credits. Once told, the three acts and Act IV are on the map
  together and every story mission can be flown again; the scene and the film stay in the journal. Cheat code `FINE` (typed on the mission
  map, nothing saved): the ending from its first scene.
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
- EDF - Opération Sentinelles silencieuses I-IV (SpaceWar, seventh round): four Adventure missions built on the SpaceWar level, one per gas giant (`story_state.MISSIONS` `sentinelle_1..4`, `sw_levels` = (blue, green, saucers) per level: I 2 levels, II-IV 3 levels; a level with a saucer is won when it is destroyed). Not training missions: the birds pay their normal points (`SpaceWarFormation(points=True)`, blue 10 / green 20 / boss saucer) and a failure costs the normal penalty (Veteran: the pilot falls). Opened in order (I from the start of Act 1, II and III in Act 2, IV in Act 3), flown once each until IV is won (flag `sentinelles_done`, key `replay`), then all four are playable again. Briefings with the pilot's name over `sentinelle1_jupiter` / `sentinelle4_neptune` clips (slowed to 0.6x, loop, no sound: `tools/encode_clip.py --slow`) and the stills of Saturn and Uranus. Tests: `tests/test_sentinelles.py`.
- The antimatter missile (SpaceWar, eighth round, `src/antimatter.py`): unlocked by winning Silent Sentinels IV (flag `antimatter_missile`, `story_state.has_antimatter`), one per mission in every Adventure mission that is not a test (`spec["antimatter"]`; `Game._begin_adventure` makes the stock `game.antimatter`). New action "missile" in `bindings` (keyboard 2: M, keyboard 1: E, pad: LB; rebindable; a row on both keys screens, whose rows are a little tighter). Fired straight ahead (up in the scrolling missions, along the heading of the ship in Asteroids / SpaceWar), it is the SpaceWar torpedo drawn 1.35x bigger (`spacewar.draw_torpedo(k=)`), flies in a straight line (no wrap), is stopped by the star of SpaceWar and is lost when it leaves the screen or with the wave. On the first enemy it touches, `BLAST_RADIUS` = 180 px (a quarter of the screen height) destroys every enemy in reach, for the usual points (waves, Space Invaders mothership, SpaceWar birds and saucer, Asteroids rocks with their pieces and the saucer); on the armour of the boss saucer the blast is `SAUCER_BLAST` = 52 px (two bricks) round the impact. A reminder of the key at the top right, a fifth stat in the workshop, a toast when it is unlocked. Tests: `tests/test_antimatter.py`.
- TEST mission "Lunar Lander" (`src/lander.py`, `src/lander_view.py`): a remake of Atari's 1979 Lunar Lander with the ship of the hangar, on the map of every act, replayable, a training mission (the score is shown, nothing won or lost). The ship is always in the middle, the ground (6000 px, random, on Titan's ice or an asteroid's rock; pictures made in real time from tileable textures) scrolls and loops under it; constant gravity (Titan 55 px/s^2, asteroid 26), inertia, thrust along the axis of the ship (controls as in Asteroids: left/right turn, up = full thrust), limited fuel (120 units, 6 per second of thrust; an empty tank = a dead thruster), no time limit. Three zoom levels with the altitude (the largest = the normal size of the ship), one to three flat zones (1.5x / 2x / 3x the width of the ship, bonus x5 / x2 / x1). Perfect landing (nearly vertical and slow) 500 points + 50 per unit of fuel, rough landing 100 + 10 per unit (the zone bonus counts for the 500 or the 100 only); too fast, too tilted or off a zone = the big blast of the ship. Warning beeps when the fuel is low, engine, landing and crash sounds (`tools/make_lander_sounds.py`). Tests: `tests/test_lander.py`.
- Lunar Lander, second round (Kraran's first tests): the peaks of the relief no longer blink when the ground scrolls (the points of the outline are now fixed in the world, every 8 px of the ground, and slide with the camera; sampled on a grid of the screen, a narrow peak slipped between two samples: `lander_view.relief`); the tank gauge moves under the four readings at the top right (it covered the hull gauge of the top left) and the labels are placed from the width of the longest label and value (INCLINAISON no longer touches its value: `lander_view.hud_layout`). Tests: `tests/test_lander.py`.
- Lunar Lander, third round (Kraran's second tests): the texture of the rock and of the ice no longer swims inside the ground when the view zooms: the zoom drawn is a multiple of 1/256 (`lander_view.snap_zoom`), so each tile has exactly the size of its world square (1024 and 768 px of the world) and starts where the world puts it (`tile_origin`); before, the tiles were scaled in 1/64 steps while the ground moved at the true zoom, and the phase of the texture jumped at each step. The ring round the ship is removed. Tests: `tests/test_lander.py`.
- Lunar Lander, speed (Kraran's third tests: 50 images/s and less): the picture of the level draws about 35-40 % faster at the same look (at most one colour level apart on 80 test pictures). The boulders are in arrays and only those on the screen are drawn (colours made once); the light on the slopes is a table made once per terrain; the outline work (light, cut-out) is done on a band along the outline only, the ground under it is whole; the shade of the depth is a multiplication by grey bars (fast blit); the sky and stars of an asteroid are one opaque picture; the background of the game is no longer painted under the level. Tests: `tests/test_lander.py`.
- The birds are as aggressive at 120 or 144 images/s as at 60 (frame-rate independent AI): their dives and shots were rolled once per image (`ENEMY_DIVE_CHANCE`, `ENEMY_SHOOT_CHANCE`), so they doubled at 120 Hz. They are now rates per second (`ENEMY_DIVE_RATE`, `ENEMY_SHOOT_RATE` = the old chance x 60) rolled with `enemy.happens(rate, dt)` = 1 - exp(-rate x dt) (a Poisson event: same count per second whatever the frame rate, never above 1). Identical to the old behaviour at 60 Hz (0.1 % apart). Tests: `tests/test_framerate_ai.py`.
- The fire bolt of the Guardians is the "fire comet" (`assets/sprites/guardian/laser.png`, 3 animation frames baked by `tools/make_guardian_laser.py`: fireball head, long tail of flames fading to dark red) and is 10 % longer (`LASER_LENGTH` 144 → 158 px); the hitbox width (10 px) is unchanged. Tests: `tests/test_guardian.py`
- Death in the flames under the fire bolt of the Guardians (`src/fire_death.py`): the birds and the ship burn (flames rise from the burning pixels, the hull glows orange then chars) and fall apart in embers that cool into grey ash flakes scattered by the wind. The birds die in a short blaze (1.35 s); the ship in a far bigger one (2.4 s: flash, ring of heat, a tall fire, a wide cloud of ash blown away). All the pictures are baked at mission setup (`ship_burn.prepare`); the other deaths of the ship keep the big blast (`Player.burn_by_guardian(blaze=True)` is only for the fire bolt). Tests: `tests/test_fire_death.py`, `tests/test_guardian.py`, `tests/test_guardian_ship_burn.py`
- The Guardians have 3 HP, a life bar (green, amber, pulsing red; the segment just lost blinks) and wings that behave like the gargoyles': a shot at a wing destroys it (no damage to the bird), it tumbles away burning and grows back after 3.2 s with an unfolding animation (`WING_REGEN`, `WING_GROW`); without both wings it cannot dive, without any it cannot shoot (a charge in progress is cancelled). The sheet is cut once into body + 2 wings along a torn line (`src/guardian_parts.py`, exact partition of the original cells) with wounds baked at 3 levels: 2 HP = soot, glowing cracks, a burnt tear in each wing, smoke; 1 HP = deep cracks pulsing, shot-out eye, red failing eye, broken crest, ragged wings, shudder, slower wingbeat, flames, falling embers, sparks. Hit = white flash, knock-back, chips and embers; death sheds both wings. Effects use a private random generator. Tests: `tests/test_guardian_health.py`
- Page up / Page down (LB / RB on the pad) on the mission map and in the journal: the cursor (the map) or the scrolling (the journal: first the scenes to watch again, then what happened) jumps by a page at once, and goes to the very end when there is less than a page (`StoryHub.page_v`). The four TEST - SpaceWar entries of the map and their texts are removed (the SpaceWar engine stays: the Sentinelles missions fly it; its tests inject the old training missions from `tests/sw_missions.py`). Tests: `tests/test_story_pages.py`, `tests/test_spacewar.py`
