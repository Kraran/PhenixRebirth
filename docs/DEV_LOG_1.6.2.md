# Development log — Phenix Rebirth 1.6.2

The detailed notes kept while the Scramble level, the concert of Lyra Voss after the visual novel and the new jukebox were made. The
short version is in the [ROADMAP](../ROADMAP.md) ("Done in 1.6.2"). Some game texts are quoted in French, the language they were first
written in.

- **Fixes (Act III, workshop, credits).** The two scenes after the fall of the NX01 or of the Phenix (Act III) now say what Huygens is:
  "Triton, in orbit around Neptune, where the Huygens station fell silent two years ago, taking its 91 occupants." The antimatter
  missile costs 1000 credits (it was 500). Credits: the songs of Lyra Voss in the music, "Phoenix (1980 - Taito)" (was 1978), "Claude -
  Anthropic" in the technical assistance, "Pleiades (1981 - Tehkan)" in the inspiration. Tests: `tests/test_credits_and_scenes.py`,
  `tests/test_missile_shop.py`.

- **TEST - Scramble, steps 1 to 5.** A remake of Konami's 1981 Scramble (`src/scramble.py`, `src/scramble_base.py`,
  `src/scramble_view.py`): a side-scrolling flight through the rock of one of the five settings of the Lunar Lander (chosen in the same
  menu), the ceiling and the floor drawn from the setting; missile stations on the rock and on the ceiling (their missiles leave
  straight, set to cross your path, and home in a little; the one standing on its rail can be shot); waves of birds and twice as many
  comets; then the enemy base, its walls of bricks (some of metal) and its red boss behind them, with its sounds and the HUD of the base.
  On the map of every act, after the Lunar Lander; a training mission: the score is shown, nothing won, nothing lost. Tests:
  `tests/test_scramble.py`.

- **The red Avioid commander, the Phenix, the Bestiary, BONUS - Scramble.** The red boss takes three hits, with a life bar; the dome of
  the Shield and the Phenix mode work in the level; the birds, the missiles and the launchers charge the Phenix gauge (the bricks of the
  base are neutral). The launchers ("LANCE-MISSILE") and the boss join the Bestiary once destroyed in a mission that counts; the boss is
  named "COMMANDANT AVIOÏDE ROUGE" / "RED AVIOID COMMANDER" (it was "CHEF ROUGE"). BONUS - Scramble is the same level for real (its points
  pay in credits, a failure costs what a failure costs), secret until the game is finished, then on the map of every act, like BONUS -
  Lunar Lander. Tests: `tests/test_scramble.py`, `tests/test_story_boss_bestiary.py`.

- **Codes in the Adventure.** LIVE and PHEN work in the missions of the Adventure, Scramble included. Tests: `tests/test_scramble.py`.

- **The concert of Lyra Voss after the visual novel.** The two best endings go on with a scene of their own: Romance with `concertmars`,
  Amitié with `concertmars_ecran`. The picture alone for 2 s, then the film once with its song (`assets/video/concertmars*.mp4` +
  `.ogg`), then the picture again, the text going by over it as in every scene (Kraran's texts, the pilot's name in the Romance). Also
  shown when the ending is watched again from the journal; B / Esc skips it and stops the song. Without its files, or when the film
  cannot play, the picture alone. Fâcherie and Distance have no concert. Tests: `tests/test_vn_concert.py`.

- **When We Looked Up.** The song of the concert (the sound of its film, so it is not twice in the game) and its Unplugged version
  (`assets/music/Lyra-Voss-When-We-Looked-Up-Unplugged.mp3`) in the jukebox and the in-game music, each with its `.pheq`. The Unplugged
  version plays under scenes 3 (the observation deck) and 4 (the refuge) of the visual novel, at the usual level of the music. Tests:
  `tests/test_vn_music.py`, `tests/test_jukebox_lyra.py`, `tests/test_ingame_music.py`.

- **Jukebox with the lyrics.** The lyrics of the six songs of Lyra Voss (`assets/music/lyrics/<key>.json`: the line sung, its time, its
  translation in the 12 other languages) and the cover of the album *Eternal Dawn*. The French translations were reviewed: the words of
  the game (Avioïdes, vaisseau-mère), a few misreadings and smoother turns; the father calls Lyra "Ma puce". The titles of the songs of
  her private concert no longer end with "(Aventure)". Tests: `tests/test_jukebox_lyra.py`.

- **A new layout for the jukebox** (`src/jukebox_ui.py`). On the left, the whole list in groups (Phenix, Lyra Voss · Eternal Dawn, the
  video): number, title (what is in brackets smaller, squeezed rather than cut), length; the track playing has the amber play mark, the
  cursor the lit frame; the list scrolls only when it no longer fits. On the right, the card of the track playing (cover, title, artist
  and album, a compact LED rack, the seek bar and the clock on one line) and the lyrics: the line sung in the middle, bigger, with its
  translation, the lines sung before it dimmed, a fade at the top and the bottom instead of a line cut in half. Opened from the
  Adventure, it wears the station of Phobos: the bar behind it, a steel plate for the list, holographic glass for the card and the CRT of
  the journal for the lyrics. Tests: `tests/test_jukebox_lyra.py`.

- **The lyrics synced on the voice.** The first times came from a transcription that missed many lines, spread at a regular step (up to
  71 s off). Each song again: the voice of Lyra isolated (UVR-MDX-NET-Voc_FT), a forced alignment of the whole text on it (wav2vec2), a
  check by a word transcription (faster-whisper large-v3-turbo); where the alignment is unsure, or the words of a line were heard
  elsewhere (the sung intros that are not in the lyrics), the time heard wins. 267 lines out of 267 checked. The tools:
  `tools/lyrics_align.py` and `tools/lyrics_align_merge.py` (how to use them at the top of the first one). Tests:
  `tests/test_jukebox_lyra.py` (`test_the_lyrics_are_synced_on_the_song`).
