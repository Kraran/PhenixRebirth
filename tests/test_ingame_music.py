"""In-game music (Options > Audio > In-game music): the four songs of Lyra Voss after the five themes, the player's own
files of the folder `musique_perso` after them, the long titles that no longer run over the label of the row, and the
announcer who says "Achievement!" when a haut-fait is unlocked."""
import os
import shutil

import pygame
import pytest

import custom_music
import draw_frame
import game as game_mod
import ingame_music
import main_menu
from i18n import LANG_CODES, get_lang, set_lang, t
from settings import asset_path
from sounds import SoundManager
from test_smoke import run  # noqa: F401  (fixture)

LYRA = ("lyra_eternal_dawn", "lyra_what_we_lost", "lyra_no_mercy_left", "lyra_oldest_fear")
THEMES = ("none", "menu", "gameover", "credits", "nostalgie_start", "nostalgie_elise")


@pytest.fixture
def folder(tmp_path, monkeypatch):
    """An empty folder `musique_perso` of its own for the test (user_data_dir() is redirected)."""
    import settings
    monkeypatch.setattr(settings, "user_data_dir", lambda: str(tmp_path))
    custom_music.forget()
    yield os.path.join(str(tmp_path), custom_music.FOLDER_NAME)
    custom_music.forget()


def _drop(folder, name, src=None):
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, name)
    if src:
        shutil.copy(src, dest)
    else:
        with open(dest, "wb") as f:
            f.write(b"not a sound")
    custom_music.forget()
    return dest


def _wav():
    return asset_path("sounds", "level1.wav")


def _id3(title):
    """The head of an mp3 that only holds an ID3v2.3 tag with a title."""
    text = b"\x00" + title.encode("latin-1")
    frame = b"TIT2" + len(text).to_bytes(4, "big") + b"\x00\x00" + text
    n = len(frame)
    size = bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F])
    return b"ID3\x03\x00\x00" + size + frame


# --- the list of choices ---------------------------------------------------------------------------------------------
def test_the_choices_are_none_the_five_themes_then_the_four_songs_of_lyra_voss(folder):
    assert ingame_music.choices() == THEMES + LYRA


def test_the_arrows_go_through_every_choice_and_wrap_around(folder):
    seen, cur = [], "none"
    for _ in range(len(THEMES + LYRA)):
        seen.append(cur)
        cur = ingame_music.cycle(cur, 1)
    assert tuple(seen) == THEMES + LYRA
    assert cur == "none"                                           # all the way round
    assert ingame_music.cycle("none", -1) == "lyra_oldest_fear"     # and backwards from the start


def test_the_files_of_the_folder_come_after_the_game_tracks(folder):
    _drop(folder, "b_track.ogg")
    _drop(folder, "C_track.mp3")                                    # (sorted without regard to case: b before C)
    assert ingame_music.choices() == THEMES + LYRA + ("custom:b_track.ogg", "custom:C_track.mp3")
    assert ingame_music.cycle("lyra_oldest_fear", 1) == "custom:b_track.ogg"
    assert ingame_music.cycle("custom:C_track.mp3", 1) == "none"
    assert ingame_music.cycle("none", -1) == "custom:C_track.mp3"


@pytest.mark.parametrize("value", [None, "", "nope", "custom:missing.mp3", "custom:../secret.mp3", 12])
def test_an_unknown_choice_is_none(folder, value):
    assert ingame_music.normalize(value) == "none"


def test_a_saved_choice_is_kept_while_its_file_is_there_and_dropped_when_it_is_gone(folder):
    path = _drop(folder, "mine.mp3")
    assert ingame_music.normalize("custom:mine.mp3") == "custom:mine.mp3"
    os.remove(path)
    custom_music.forget()
    assert ingame_music.normalize("custom:mine.mp3") == "none"


@pytest.mark.parametrize("key", LYRA)
def test_lyra_voss_is_kept_as_chosen(folder, key):
    assert ingame_music.normalize(key) == key


# --- the folder ------------------------------------------------------------------------------------------------------
def test_the_folder_is_made_empty_next_to_the_game(folder, tmp_path):
    assert not os.path.exists(folder)
    assert custom_music.ensure_folder() is True
    assert os.path.isdir(folder) and os.listdir(folder) == []
    assert custom_music.folder() == os.path.join(str(tmp_path), "musique_perso")
    assert custom_music.ensure_folder() is True                    # twice is fine
    assert custom_music.files() == ()


def test_only_sound_files_are_offered(folder):
    for name in ("a.mp3", "b.WAV", "c.ogg", "d.flac", "e.opus", "f.mod", "g.txt", "h.jpg", "noext", ".hidden.mp3"):
        _drop(folder, name)
    os.makedirs(os.path.join(folder, "sub.mp3"))                   # a folder is not a file
    custom_music.forget()
    assert custom_music.files() == ("a.mp3", "b.WAV", "c.ogg", "d.flac", "e.opus", "f.mod")


def test_no_folder_is_no_custom_music(folder):
    assert custom_music.files() == ()
    assert custom_music.keys() == ()


def test_a_key_only_leads_to_a_bare_file_name_of_the_folder(folder):
    _drop(folder, "ok.mp3")
    assert custom_music.path_of("custom:ok.mp3") == os.path.join(folder, "ok.mp3")
    assert custom_music.path_of("custom:../ok.mp3") is None
    assert custom_music.path_of("custom:sub/../ok.mp3") is None
    assert custom_music.path_of("menu") is None
    assert custom_music.path_of("custom:gone.mp3") is None


def test_the_folder_is_read_again_soon_enough_to_see_a_new_file(folder, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(custom_music.time, "monotonic", lambda: clock[0])
    custom_music.forget()
    assert custom_music.files() == ()
    with open(os.path.join(os.makedirs(folder, exist_ok=True) or folder, "new.mp3"), "wb") as f:
        f.write(b"x")
    assert custom_music.files() == ()                              # (a name is asked for every frame: not read every time)
    clock[0] += custom_music.RESCAN_SEC + 0.1
    assert custom_music.files() == ("new.mp3",)


# --- what the Options show --------------------------------------------------------------------------------------------
def test_labels_are_the_jukebox_titles(folder):
    assert ingame_music.label("none", t) == t("no")
    assert ingame_music.label("menu", t, asset_path) == "Phenix - Eternal Dawn I (Opening)"
    before = get_lang()
    try:
        for lang in ("fr", "en", "ru"):                              # the songs of Lyra Voss are translated, as in the jukebox
            set_lang(lang)
            for key in LYRA:
                assert ingame_music.label(key, t, asset_path) == t("juke_" + key)
                assert "Lyra Voss" in ingame_music.label(key, t, asset_path)
        set_lang("en")
        assert ingame_music.label("lyra_eternal_dawn", t, asset_path) == "Lyra Voss - Eternal Dawn (Adventure)"
    finally:
        set_lang(before)


def test_a_file_shows_its_title_tag_else_its_name_without_the_extension(folder):
    path = _drop(folder, "song one.mp3")
    with open(path, "wb") as f:
        f.write(_id3("My Title") + b"\xff\xfb" * 10)
    _drop(folder, "plain name.ogg")
    assert ingame_music.label("custom:song one.mp3", t, asset_path) == "My Title"
    assert ingame_music.label("custom:plain name.ogg", t, asset_path) == "plain name"


# --- a long title never runs over the label --------------------------------------------------------------------------
class _Font:
    """A font of fixed width: size() is 10 px a character times `k`."""

    def __init__(self, k):
        self.k = k

    def size(self, text):
        return (len(text) * self.k, 20)


def test_a_text_that_fits_is_left_alone():
    big, small = _Font(10), _Font(6)
    assert draw_frame.fit_text((big, small), "x" * 10, 100) == (big, "x" * 10)


def test_a_text_that_only_fits_small_is_drawn_small():
    big, small = _Font(10), _Font(6)
    assert draw_frame.fit_text((big, small), "x" * 15, 100) == (small, "x" * 15)


def test_a_text_too_long_is_cut_in_the_middle_and_keeps_its_end():
    big, small = _Font(10), _Font(6)
    font, text = draw_frame.fit_text((big, small), "Phoenix - Nostalgie pour Elise (Final)", 150)
    assert font is small
    assert small.size(text)[0] <= 150
    assert text.startswith("Phoenix") and text.endswith("(Final)") and "..." in text
    _, other = draw_frame.fit_text((big, small), "Phoenix - Nostalgie interdite (Start)", 150)
    assert other.endswith("(Start)") and other != text            # the two themes are told apart in the row


def test_a_single_font_is_enough():
    f = _Font(10)
    font, text = draw_frame.fit_text((f,), "y" * 40, 120)
    assert font is f and f.size(text)[0] <= 120


def _open_audio_tab(g):
    tab = [name for name, _rows in main_menu.OPTION_TABS].index("audio")
    g.menu_screen = "options"
    g.opt_tab = tab
    g.menu_index = main_menu.tab_rows(tab).index("ingame_music")
    return tab


def _row_spy(monkeypatch):
    """Records, for the chosen row, where the value is drawn (font, text, right edge)."""
    calls = []
    real = draw_frame._value_with_arrows

    def spy(game, surf, font, text, right, cy, chosen, col):
        calls.append((font, text, right, chosen))
        return real(game, surf, font, text, right, cy, chosen, col)

    monkeypatch.setattr(draw_frame, "_value_with_arrows", spy)
    return calls


@pytest.mark.parametrize("lang", ["fr", "en", "de", "ru", "tr"])
def test_the_value_of_the_in_game_music_row_never_runs_over_its_label(run, folder, monkeypatch, lang):
    g = run.game
    before = get_lang()
    set_lang(lang)
    try:
        g.text_cache.clear()
        _drop(folder, "A very long name of a file that nobody would ever read to the end.mp3")
        _open_audio_tab(g)
        calls = _row_spy(monkeypatch)
        for value in LYRA + ("nostalgie_elise", "nostalgie_start", "menu",
                             "custom:A very long name of a file that nobody would ever read to the end.mp3"):
            g.ingame_music = value
            calls.clear()
            run.frames(2)
            row = [c for c in calls if c[3]]                         # the chosen row has its arrows
            assert row, value
            font, text, right, _chosen = row[-1]
            label_right = 60 + 28 + g.font.size(g._option_label("ingame_music"))[0]
            left = right - font.size(text)[0] - draw_frame.ARROW_ROOM
            assert left >= label_right, (lang, value, text, left, label_right)
    finally:
        set_lang(before)
        g.text_cache.clear()


def test_the_help_gives_the_whole_title_of_the_chosen_track(run, folder):
    g = run.game
    _open_audio_tab(g)
    g.ingame_music = "lyra_no_mercy_left"
    seen = []
    real = g._txt
    g._txt = lambda font, text, color: (seen.append(text), real(font, text, color))[1]
    run.frames(2)
    assert t("ingame_now") in seen
    assert t("juke_lyra_no_mercy_left") in seen


def test_the_help_names_the_folder_and_has_a_title_of_its_own():
    for lang in LANG_CODES:
        set_lang(lang)
        try:
            assert "musique_perso" in t("opt_help_ingame_music"), lang
            assert t("ingame_now") != "ingame_now", lang
        finally:
            set_lang("fr")


def test_the_arrows_of_the_option_row_go_through_lyra_voss_and_the_files(run, folder):
    import menu_actions
    g = run.game
    _drop(folder, "one.mp3")
    _drop(folder, "two.wav")
    _open_audio_tab(g)
    g.ingame_music = "none"
    seen = []
    for _ in range(len(THEMES + LYRA) + 2):
        menu_actions.menu_adjust(g, 1)
        seen.append(g.ingame_music)
    assert seen == list(THEMES[1:] + LYRA) + ["custom:one.mp3", "custom:two.wav", "none"]


# --- playing the player's own file ----------------------------------------------------------------------------------
class _Sounds:
    def __init__(self):
        self.calls = []

    def register_music(self, key, path):
        self.calls.append(("register", key, path))

    def play_music(self, key, **kw):
        self.calls.append(("play", key))

    def __getattr__(self, name):                       # every other call of the game to its sounds does nothing
        return lambda *a, **k: None


def test_a_file_of_the_folder_is_registered_then_played(run, folder):
    g = run.game
    path = _drop(folder, "mine.wav", _wav())
    g.sounds = _Sounds()
    g.started, g.game_over, g.attract_mode = True, False, False
    g.ingame_music = "custom:mine.wav"
    g._tick_ingame_music()
    assert g.sounds.calls == [("register", "custom:mine.wav", path), ("play", "custom:mine.wav")]


def test_a_lyra_voss_song_is_played_like_a_theme(run, folder):
    g = run.game
    g.sounds = _Sounds()
    g.started, g.game_over, g.attract_mode = True, False, False
    g.ingame_music = "lyra_what_we_lost"
    g._tick_ingame_music()
    assert g.sounds.calls == [("play", "lyra_what_we_lost")]


def test_a_file_that_is_gone_plays_nothing(run, folder):
    g = run.game
    path = _drop(folder, "mine.wav", _wav())
    g.sounds = _Sounds()
    g.started, g.game_over, g.attract_mode = True, False, False
    g.ingame_music = "custom:mine.wav"
    os.remove(path)
    custom_music.forget()
    g._tick_ingame_music()
    g._update_music()
    assert ("play", "custom:mine.wav") not in g.sounds.calls
    assert not any(c[0] == "register" for c in g.sounds.calls)


def test_the_music_of_a_run_is_the_chosen_file_not_the_menu_theme(run, folder):
    g = run.game
    _drop(folder, "mine.wav", _wav())
    g.sounds = _Sounds()
    g.started, g.game_over, g.attract_mode, g.menu_screen = True, False, False, "main"
    g.audio_mix = "sfx_music"
    g.ingame_music = "custom:mine.wav"
    g._update_music()
    assert ("register", "custom:mine.wav", os.path.join(folder, "mine.wav")) in g.sounds.calls
    assert ("play", "custom:mine.wav") in g.sounds.calls
    assert ("play", "menu") not in g.sounds.calls


def test_the_sound_manager_plays_a_real_file_of_the_player(run, folder):
    s = run.game.sounds
    path = _drop(folder, "real.wav", _wav())
    s.stop_music()
    s._current_music = None
    s.register_music("custom:real.wav", path)
    s.play_music("custom:real.wav", fade_ms=0)
    assert s.current_music_key() == "custom:real.wav"
    assert s.music_duration("custom:real.wav") is None             # no length known: it loops, with no end-fade
    s.stop_music()


def test_a_file_the_mixer_cannot_read_is_tried_once_not_every_frame(run, folder, monkeypatch):
    s = run.game.sounds
    path = _drop(folder, "broken.ogg")                             # not a sound at all
    s.stop_music()
    s._current_music = None
    loads = []
    real = pygame.mixer.music.load

    def count(p, *a, **k):
        loads.append(p)
        return real(p, *a, **k)

    monkeypatch.setattr(pygame.mixer.music, "load", count)
    s.register_music("custom:broken.ogg", path)
    for _ in range(5):
        s.play_music("custom:broken.ogg", fade_ms=0)
    assert loads == [path]
    assert s.current_music_key() is None
    # replacing the file by a good one lets it play again
    shutil.copy(_wav(), path)
    os.utime(path, (1_900_000_000, 1_900_000_000))
    s.play_music("custom:broken.ogg", fade_ms=0)
    assert len(loads) == 2
    s.stop_music()


def test_the_built_in_themes_are_not_affected_by_the_bad_track_guard(run, monkeypatch):
    s = run.game.sounds
    assert s._bad_music == {}
    s.stop_music()
    s._current_music = None
    s.play_music("menu", fade_ms=0)
    assert s.current_music_key() == "menu"
    s.stop_music()


# --- "Achievement!" ---------------------------------------------------------------------------------------------------
def test_the_voice_is_in_the_game_and_about_a_second_and_a_half(run):
    snd = run.game.sounds.sounds.get("achievement")
    assert snd is not None
    assert 1.2 < snd.get_length() < 1.8
    assert os.path.isfile(asset_path("sounds", "achievement.wav"))


def test_the_announcer_says_it_on_its_own_channel_when_it_is_free(run, monkeypatch):
    s = run.game.sounds
    calls = []
    monkeypatch.setattr(s, "vo_is_busy", lambda: False)
    monkeypatch.setattr(s, "play_vo", lambda name, volume=None: calls.append(("vo", name)))
    monkeypatch.setattr(s, "play", lambda name, volume=None, x=None: calls.append(("sfx", name)))
    s.sfx_muted = False
    s.play_achievement()
    assert calls == [("vo", "achievement")]


def test_it_never_cuts_another_announcement(run, monkeypatch):
    s = run.game.sounds
    calls = []
    monkeypatch.setattr(s, "vo_is_busy", lambda: True)
    monkeypatch.setattr(s, "play_vo", lambda name, volume=None: calls.append(("vo", name)))
    monkeypatch.setattr(s, "play", lambda name, volume=None, x=None: calls.append(("sfx", name)))
    s.sfx_muted = False
    s.play_achievement()
    assert calls == [("sfx", "achievement")]


def test_it_is_silent_when_the_sound_effects_are_off(run, monkeypatch):
    s = run.game.sounds
    calls = []
    monkeypatch.setattr(s, "play_vo", lambda *a, **k: calls.append("vo"))
    monkeypatch.setattr(s, "play", lambda *a, **k: calls.append("sfx"))
    s.sfx_muted = True
    try:
        s.play_achievement()
    finally:
        s.sfx_muted = False
    assert calls == []


def _count_voice(g, monkeypatch):
    said = []
    monkeypatch.setattr(g.sounds, "play_achievement", lambda: said.append(1))
    return said


def test_a_haut_fait_unlocked_in_a_run_is_announced(run, monkeypatch):
    g = run.game
    said = _count_voice(g, monkeypatch)
    g.attract_mode, g.used_cheat, g.adventure = False, False, None
    monkeypatch.setattr(game_mod, "unlock_achievement", lambda aid, data: True)
    assert g._unlock_ach("first_blood") is True
    assert said == [1]
    assert g.cheat_kind == "ach"


def test_the_voice_comes_even_when_a_one_up_holds_the_banner(run, monkeypatch):
    g = run.game
    said = _count_voice(g, monkeypatch)
    g.attract_mode, g.used_cheat, g.adventure = False, False, None
    g.cheat_kind, g.cheat_msg, g.cheat_msg_timer = "1up", "1UP", 3.0
    monkeypatch.setattr(game_mod, "unlock_achievement", lambda aid, data: True)
    g._unlock_ach("first_blood")
    assert g.cheat_kind == "1up"                                    # the banner is not taken over...
    assert said == [1]                                              # ...but the unlock is announced


def test_a_haut_fait_already_unlocked_is_not_announced_again(run, monkeypatch):
    g = run.game
    said = _count_voice(g, monkeypatch)
    g.attract_mode, g.used_cheat, g.adventure = False, False, None
    monkeypatch.setattr(game_mod, "unlock_achievement", lambda aid, data: False)
    assert g._unlock_ach("first_blood") is False
    assert g._unlock_ach_meta("listen_menu") is False
    assert said == []


def test_a_menu_haut_fait_is_announced(run, monkeypatch):
    g = run.game
    said = _count_voice(g, monkeypatch)
    g.attract_mode = False
    monkeypatch.setattr(game_mod, "unlock_achievement", lambda aid, data: True)
    assert g._unlock_ach_meta("listen_menu") is True
    assert said == [1]


def test_a_new_tier_is_announced_but_a_plain_count_is_not(run, monkeypatch):
    g = run.game
    said = _count_voice(g, monkeypatch)
    g.attract_mode, g.used_cheat, g.adventure = False, False, None
    monkeypatch.setattr(game_mod, "add_scalable", lambda aid, n, data: (True, "bronze"))
    g._note_scalable("first_blood", 1)
    assert said == [1]
    monkeypatch.setattr(game_mod, "add_scalable", lambda aid, n, data: (True, None))
    g._note_scalable("first_blood", 1)
    assert said == [1]


def test_a_haut_fait_of_the_adventure_page_is_announced_once_per_banner(run, monkeypatch):
    g = run.game
    said = _count_voice(g, monkeypatch)
    g.started, g.attract_mode = False, False
    g.menu_screen = "main"
    g.cheat_msg_timer = 0
    g.__dict__["_feat_queue"] = [("adv_pilot", "gold"), ("adv_raid", None)]
    g._tick_story_feats()
    assert said == [1]
    g.cheat_msg_timer = 0
    g._tick_story_feats()
    assert said == [1, 1]


def test_the_folder_is_made_at_the_start_of_the_game(run, folder):
    import game_init
    g = run.game
    assert not os.path.exists(folder)
    del g.ingame_music                                              # (as at a first start: the setting is read again)
    game_init.init_settings(g, False)
    assert os.path.isdir(folder) and os.listdir(folder) == []
