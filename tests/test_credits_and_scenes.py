"""The credits and the two scenes that name the station Huygens (Act III)."""
import i18n


def _lines(lang):
    i18n.set_lang(lang)
    try:
        return [text for _kind, text in i18n.get_credits_lines()]
    finally:
        i18n.set_lang("fr")


def test_the_credits_name_the_music_of_lyra_voss_and_the_right_year_of_phoenix():
    for lang in i18n.LANG_CODES:
        lines = _lines(lang)
        for title in ("Eternal Dawn", "What We Lost", "Oldest Fear", "When We Looked Up", "No Mercy Left"):
            assert title + " (Lyra Voss)" in lines, (lang, title)
        assert "Phoenix (1980 - Taito)" in lines and "Pleiades (1981 - Tehkan)" in lines
        assert not any("1978" in line for line in lines)
        assert "Claude  —  Anthropic" in lines


def test_the_credits_put_claude_with_the_technical_assistance_and_pleiades_with_the_inspiration():
    lines = _lines("fr")
    assert lines.index("Grok  —  xAI") < lines.index("Claude  —  Anthropic") < lines.index("Phoenix (1980 - Taito)")
    assert lines.index("Phoenix (1980 - Taito)") < lines.index("Pleiades (1981 - Tehkan)") < lines.index("Eternal Dawn (Lyra Voss)")


def test_the_two_scenes_after_the_fall_say_what_huygens_is():
    for key in ("story_scene_lostp", "story_scene_losts"):
        fr, en = i18n.T[key]["fr"], i18n.T[key]["en"]
        assert "où la station Huygens s’est tue il y a deux ans, emportant ses 91 occupants." in fr
        assert "where the Huygens station fell silent two years ago, taking its 91 occupants with it." in en
        assert "Neptune. Huygens." not in fr + en                                   # a lone "Huygens" meant nothing
