# Phenix Rebirth

**Version 1.5.0**

A modern, ultra-responsive PC remake of the classic arcade shooter **Phoenix** (1978 / 1980).

Free to play · Open source · MIT License

> **Unofficial fan project.** *Phenix Rebirth* is inspired by the arcade game *Phoenix*.
> It is **not** an official port, sequel, or product of Amstar Electronics, Centuri, Taito,
> or any related rights holder.

---

## Screenshots

| Menu | Help | In-game (demo) |
|------|------|----------------|
| ![Title screen](docs/screenshots/accueil.png) | ![Help](docs/screenshots/aide.png) | ![Gameplay](docs/screenshots/ingame.png) |

## Gameplay

[![Phenix Rebirth gameplay](https://img.youtube.com/vi/NIiuKcSgEOk/maxresdefault.jpg)](https://youtu.be/NIiuKcSgEOk)

[Watch on YouTube](https://youtu.be/NIiuKcSgEOk) · [Play on itch.io](https://kraran.itch.io/phenix-rebirth)

## Features

- **Main menu**: Play, Adventure (Beta), Extras, Options, Quit. *Play* opens the arcade game screen (mode: 1 player / hot seat / coop, difficulty) before the ship select; *Extras* gathers High Scores, Achievements, Jukebox, Credits, Help and the Add-On
- **Adventure (Beta)** — a story mode in three acts: Act 1 (the weak Shield, the dome), Act 2 (the Phenix, the paint series, the Avioid commander), Act 3 (the attack of Phobos, the choice of the ship, the final series). 4 save slots, Novice / Normal / Veteran (permanent death), mission map, journal, Bestiary, hangar and workshop, loot items, story scenes in pictures and video, a French spoken introduction. An Extras tab at its far left opens Achievements, Jukebox, Credits and Options. It is still in beta: bugs and balance are expected, please report them on GitHub Issues
- **VIP rescue** (Act 2 BONUS, needs the two-dimensional reactor) — escort a luxury cruise ship across the bottom of the screen while the level 3 birds dive at it (`src/escort.py`); who was on board is told after the victory, then her private concert plays, three songs in a row (films with their sound, `assets/video/`, each one watched again from the journal)
- **Visual novel** (begins after the concert of Lyra Voss) — a scene between the story missions: a film, then a picture with Lyra's words (in pages, with narration) and four answers to choose from (in a random order for scene 1), then Lyra's reaction to the answer. Each answer is worth hidden points that will decide the ending (`src/story_vn.py`). The answer is final and the scene can be watched again from the journal. Scene 1 (the Phobos bar) comes after the concert, scenes 2 (the hangar) and 3 (the observation deck) each after the next story mission won; the next ones are to come
- **Adventure intro read aloud** (French) — the text follows the voice (`assets/story/voice/`, made with `tools/make_intro_voice.py`)
- **Adventure intro in video** — the story slides (Huygens, Phobos, Kamarasov; Kamarasov's death in Veteran mode) are short looping clips in `assets/story/`, like Wallems' workshop
- **Return to base** — a lost mission (Normal mode) is drawn into a blue whirlwind, a flash, and the mission map comes back; Enter / Esc / a pad button skips it (`python tools/make_anchor_sound.py` makes its sound, numpy only)
- **Asteroids belt** (Adventure, the prelude of the main series of each act: 60, 80 then 100 rocks to destroy) — free flight in the spirit of the Atari arcade game; replayable, and its first victory opens the Dome, the Phenix and la Riposte series
- **Shield ship** — second craft: freeze + explosive barrier (2 s, 5 s cooldown)
- Ship select at start (and P2 in hot-seat); blue tint only when both pick the same hull
- Achievements in two pages, ARCADE (32) and ADVENTURE (32, Acts 1 to 3): a grid of illustrated cards (the frame's metal is the tier: steel, bronze, silver, gold; grey when locked) and a panel that tells how to get the one under the cursor, its tiers and the date; some are secret until found. The cursor turns the page at the edges of the grid (Tab / LB / RB: High Scores, Jukebox). The pictures are made by `tools/make_achievement_art.py`
- Jukebox (ID3 titles, PHEQ1 equalizer, intro video)
- In-game music picker (Off, the soundtrack themes, the songs of Lyra Voss, and your own tracks dropped in the `musique_perso` folder next to the game)
- Announcer up to level 31
- Stereo SFX panned to the event
- Seasonal title overlay (Christmas 1 Dec–6 Jan, Halloween 24 Oct–1 Nov)
- April Fools logo gag (1 April, once per boot)
- Rare animated comet in the starfield (once per stage cycle, never spawned on the boss)

## Requirements

- Python **3.10+** (3.11 / 3.12 / 3.13 recommended)
- [Pygame](https://www.pygame.org/) 2.5+
- [imageio-ffmpeg](https://pypi.org/project/imageio-ffmpeg/) (brings its own ffmpeg, used for the video clips; a
  `bin/ffmpeg.exe` placed next to the game takes precedence, then the PATH)

## Install

```bash
git clone https://github.com/Kraran/PhenixRebirth.git
cd PhenixRebirth
python -m pip install -r requirements.txt
```

## Video clips

Scenes can play a short looping video behind their text. Turn any video into a clip (no sound, H.264, seamless loop):

```bash
python tools/encode_clip.py my_video.mp4 picture_name
```

This writes `assets/story/picture_name.mp4` and, if there is none yet, the poster `picture_name.jpg`. The scene whose
slide uses `picture_name` plays the clip by itself. Without ffmpeg the poster is shown instead.

The boot intro and the jukebox video are one more clip, `assets/video/intro.mp4`, with its music `assets/video/intro.ogg`
(`python tools/encode_clip.py my_intro.mp4 intro --no-loop --no-poster --crf 23 --out-dir assets/video`).

## Phenix frames

The Phenix flight frames are drawn on a canvas larger than the ship (`src/phenix_art.py`): the margin holds the wing tips.
Always scale a frame by the size of the ship (`phenix_art.ship_size`), never by the size of the picture. The wing tips were
added to the original frames by `python tools/extend_wings.py ORIGINAL_DIR OUT_DIR` (needs only pygame and numpy).

The transformation (ship to Phenix and back) is the few pictures drawn by hand plus cross-dissolves between them, made when the
ship is chosen (`phenix_art.morph_sequence`, needs numpy: without it the drawn pictures are used as they are); the pace is `PHENIX_MORPH_IN_SEC` / `PHENIX_MORPH_OUT_SEC`.
The pictures between the drawn ones move the details along a flow calculated once (`assets/sprites/morph_flow.npz`, made by
`python tools/bake_morph_flow.py`, which needs OpenCV; the game needs only numpy), so the hull does not show through the wings as a ghost.
A flash (lighter ship and a halo, in the colour of the Phenix's fire) peaks when the wings open (`FLASH_*` in the same file).
The Shield dome forms and goes away the same way, from its drawn pictures with cross-dissolves between them (`dissolve`, `SHIELD_*`).

## Run

```bash
python main.py
```

**Windows:** double-click `lancer.bat` (installs pygame if needed, then launches the game).

## Controls

| Action | Keyboard | Gamepad |
|--------|----------|---------|
| Move | Arrow keys (keyboard 2) · W/Z A/Q S D (keyboard 1) | Left stick / D-Pad |
| Fire | Space / Right Ctrl (keyboard 2) · Left Ctrl (keyboard 1) | A (or face buttons) |
| **PHENIX** / Shield activate | Right Shift (keyboard 2) · Left Shift (keyboard 1) | **B** |
| Pause | Esc | Start |
| Menus | Arrows + Enter | Stick / D-Pad + A · B = back |

These are the defaults. In *Options > Game > Touches et boutons* every key (two per action, on two keyboards) and
every pad button can be changed; in solo the last device used flies the ship, and in coop each player can be given
a keyboard half or a pad.

- One player shot on screen at a time (classic Phoenix rule); dual shots only in PHENIX form.
- PHENIX gauge: **+1** per valid kill, **−1** per miss; activate from **3**. Cancel early with B / Shift to keep remaining gauge.

## Stages (cycle 1–5, then faster loops)

| Stage | Enemies | Points (Normal, levels 1–5) |
|-------|---------|----------------------|
| 1 | Dark birds | 10 |
| 2 | Green / khaki birds | 20 |
| 3 | Gargoyles | 30 (body only; wings neutral) |
| 4 | Violet / dark-red gargoyles | 40 |
| 5 | Boss saucer + escort birds | Core 500 · cells 1 · decorations 50 |

- Level bonus: levels 1–5 pay the prices above. From level 6 every enemy, the boss core and the saucer decorations
  get **+10 in levels 6–10, +20 in 11–15**, and so on (a 10-point bird is worth 20 at level 6, 30 at level 11).
  Armor cells stay at 1.
- Veteran: bird scores **+10**, boss core **1000**.
- Novice: slower enemies, 5 lives, no high-score entry; PHENIX lasts longer.
- Bonus lives at **1 337** and **8 086** points.

## Options

Four tabs: **Game**, **Audio**, **Display**, **Advanced** (Tab / Page Up / Page Down on the keyboard, LB / RB on the pad, or Left / Right on the row of tabs). Persisted in `settings.json` (created at runtime, **not** shipped in the repo):

- Control (Auto / keyboard / pad), the control of each coop player, key and button bindings, display (window / fullscreen / borderless)
- SFX & music volume, rumble, autofire
- Language (13 locales)
- FPS counter, scanlines OFF / 1 / 2 / 3
- GPU render, VSync, refresh cap (60 / 75 / 120 / 144)
- Bezel style (fullscreen ultrawide)
- Reset high scores
- Focused-option help panel on the Options screen

Manual advanced key (edit `settings.json` when the game is closed): `monitor_index` for multi-monitor fullscreen.

## Project layout

```
PhenixRebirth/
├── main.py
├── lancer.bat
├── build_exe.bat
├── requirements.txt
├── LICENSE
├── VERSION
├── assets/          # sprites, music, SFX, logo, fonts
├── docs/screenshots/
└── src/             # game, player, enemies, boss, i18n…
```

## Development

Franck Fornasari (Kraran)

Music: *Phenix — Eternal Dawn*, *Eternal Dawn (Game Over)*, *Last Coin (Credits)* — created with [Suno](https://suno.com).

Fonts: [Audiowide](https://fonts.google.com/specimen/Audiowide) (titles) and [Play](https://fonts.google.com/specimen/Play) (text), SIL Open Font License 1.1; [DejaVu Sans](https://dejavu-fonts.github.io/) Bold, reduced to Latin, Greek, Cyrillic and symbols, for what they lack (Bitstream Vera licence). The licences ship with them in `assets/fonts`.

Tech: Python 3, Pygame 2 (SCALED GPU present), delta-time action loop.

## License

MIT — see [LICENSE](LICENSE). The fonts in `assets/fonts` keep their own licences (the `.txt` files next to them).

## Disclaimer

This is a fan-made tribute. All trademarks belong to their respective owners.
