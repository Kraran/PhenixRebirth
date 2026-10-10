# Phenix Rebirth

**Version 1.4.5**

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

- **Adventure** (an Extras tab at its far left opens Options, Jukebox and Credits) — chapter 1: Shield with a broken dome, mission map, bestiary unlocks, hangar credits
- **Return to base** — a lost mission (Normal mode) is drawn into a blue whirlwind, a flash, and the mission map comes back; Enter / Esc / a pad button skips it (`python tools/make_anchor_sound.py` makes its sound, numpy only)
- **Shield ship** — second craft: freeze + explosive barrier (2 s, 5 s cooldown)
- Ship select at start (and P2 in hot-seat); blue tint only when both pick the same hull
- Achievements (scrollable, dated)
- Jukebox (ID3 titles, PHEQ1 equalizer, intro video)
- In-game music picker (Off + the 5 soundtrack themes)
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
| Move | Arrow keys / WASD | Left stick / D-Pad |
| Fire | Space / Up / W | A (or face buttons) |
| **PHENIX** activate / cancel | Left Shift / Right Shift / X | **B** |
| Pause | Esc | Start |
| Menus | Arrows + Enter | Stick / D-Pad + A · B = back |

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

Persisted in `settings.json` (created at runtime, **not** shipped in the repo):

- Input mode, display (window / fullscreen / borderless)
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
├── assets/          # sprites, music, SFX, logo
├── docs/screenshots/
└── src/             # game, player, enemies, boss, i18n…
```

## Development

Franck Fornasari (Kraran)

Music: *Phenix — Eternal Dawn*, *Eternal Dawn (Game Over)*, *Last Coin (Credits)* — created with [Suno](https://suno.com).

Tech: Python 3, Pygame 2 (SCALED GPU present), delta-time action loop.

## License

MIT — see [LICENSE](LICENSE).

## Disclaimer

This is a fan-made tribute. All trademarks belong to their respective owners.
