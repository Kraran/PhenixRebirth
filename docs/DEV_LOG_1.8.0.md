# Development log — Phenix Rebirth 1.8.0

The detailed notes of the changes since 1.7.2. The short version is in the [ROADMAP](../ROADMAP.md) ("Done in 1.8.0").

- **The antimatter missile and the Guardians** (`src/antimatter.py`, PR #283). The missile only looked at the birds of
  the formation, the boss saucer and the mothership; the Guardians are in their own squad (`game.guardian_squad`), so it
  flew through them and its blast left them whole. It now blows up on a Guardian (`get_hitbox`, or a wing:
  `get_left_wing_hitbox` / `get_right_wing_hitbox`), and the blast (`_blast_guardians`) destroys the Guardians whose
  body or wings are within `BLAST_RADIUS`, whatever their health, with their points, the Bestiary and an explosion. The
  Alpha Guardian loses `ALPHA_BLAST_DAMAGE` = 3 of its 6 HP (as the boss saucer, which takes a smaller blast): a second
  missile brings it down. Same code for the Adventure and the Adventure style of the arcade game. Tests:
  `tests/test_antimatter.py` (the missile touching a Guardian, by its wing, the Alpha).

- **The flags of the languages** (`src/lang_flags.py`, PR #284). Thirteen flags drawn with pygame (no picture file):
  bands, the Nordic crosses (Sweden, Norway, Denmark), the Union Jack for English, the crescent and the star of Turkey,
  the sphere of Portugal, drawn four times bigger then smoothed down and kept once made. The Language row of the
  options draws its flag just before the name of the language (`draw_frame._value_with_arrows`, `icon`), between the ‹ ›
  of the chosen row.

- **The language of the system** (`src/sys_lang.py`, PR #284). At the very first start (no `settings.json`, or one
  without a valid language) `user_settings.clean_user_settings` asks `sys_lang.detect()`: on Windows the language of
  the interface (`GetUserDefaultUILanguage`), then of the user's locale (`GetUserDefaultLCID`), through
  `locale.windows_locale`; elsewhere (and on Windows if that failed) `LANGUAGE`, `LC_ALL`, `LC_MESSAGES`, `LANG`, then
  the locale of Python. "nb"/"nn" are Norwegian; a Windows name such as "French_France" is read too. A language the
  game does not have, or no answer, gives English; `i18n.set_lang` of an unknown code also falls back on English now.
  The tests start on a "French system" (`tests/conftest.py`) so that they read the same everywhere. Tests:
  `tests/test_lang_flags_and_system_lang.py`.

- **The pictures of the last scenes** (`assets/story/`, PR #285, #286, #287). `epave_phenix`, `epave_nx01`,
  `remise_en_etat` (both overhauls), `riposte`, `epilogue_1`, `epilogue_2`, `sacha_hangar`, `defense_phobos_1` to `_3`:
  cropped at the centre to 16:9 like the others (1792x1008 or 1280x720). The scenes already asked for these names; they
  showed a dark sky until now. Still without a picture: the attack on Phobos (`phobos_attaque`, `ancrage_unique`), the
  loss of a hull (`perte_phenix`, `perte_shield`) and the Guardians series (`gardiens_premier_feu`, `gardiens_bestiaire`,
  `gardiens_hybrides`, `gardien_alpha`, `revetement_reflechissant`).
