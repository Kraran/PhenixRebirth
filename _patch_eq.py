# -*- coding: utf-8 -*-
"""Surgical patch: restore original PHEQ1 equalizer in src/game.py."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.join(ROOT, "src", "game.py")

IMPORT = "from pheq import load_pheq, resolve_path as pheq_resolve, sample as pheq_sample, tick as pheq_tick, draw as pheq_draw, clock_y as pheq_clock_y\n"

METHODS = '''
    def _eq_ensure(self, key):
        """Load original PHEQ1 file from assets/music/ (not music/eq remakes)."""
        seqs = getattr(self, "_eq_seq", None)
        if seqs is None:
            self._eq_seq = seqs = {}
        if key in seqs:
            return
        path = pheq_resolve(asset_path, key)
        seqs[key] = load_pheq(path) if path else None

    def _eq_tick(self, key, pos, playing, dt):
        self._eq_ensure(key)
        seq = (getattr(self, "_eq_seq", {}) or {}).get(key)
        n = int(seq["n"]) if seq else 40
        if len(getattr(self, "_eq_bands", [])) != n:
            self._eq_n = n
            self._eq_bands = [0.0] * n
            self._eq_peaks = [0.0] * n
        target = pheq_sample(seq, pos) if (playing and seq) else [0.0] * n
        pheq_tick(self._eq_bands, self._eq_peaks, target, playing and bool(seq), dt)

    def _draw_eq(self, surface):
        """Original neon bars from .pheq — no frame, no panel."""
        pheq_draw(
            surface, pygame,
            getattr(self, "_eq_bands", []),
            getattr(self, "_eq_peaks", []),
            BASE_WIDTH, BASE_HEIGHT,
        )

'''


def main():
    if not os.path.isfile(GAME):
        print("src/game.py introuvable. Place ce dossier dans D:\\PhenixRebirth")
        return 1
    text = open(GAME, encoding="utf-8").read()
    if "from pheq import" not in text:
        needle = "from sounds import SoundManager\n"
        if needle not in text:
            needle = "from starfield import Starfield\n"
        if needle not in text:
            print("Impossible de trouver le bloc d'imports.")
            return 1
        text = text.replace(needle, needle + IMPORT, 1)
    elif "pheq_clock_y" not in text:
        import re
        text = re.sub(r"from pheq import[^\n]+\n", IMPORT, text, count=1)

    start = text.find("    def _eq_ensure(self, key):")
    end = text.find("    def _update_jukebox(self):")
    if start < 0 or end < 0 or end <= start:
        # insert before _draw_jukebox if EQ methods missing
        mark = text.find("    def _draw_jukebox(self")
        if mark < 0:
            print("Pas de jukebox dans game.py — EQ non branche.")
            return 1
        text = text[:mark] + METHODS + text[mark:]
    else:
        text = text[:start] + METHODS + text[end:]

    # force draw path to call _eq_ensure/_eq_tick/_draw_eq (already there if previous patch)
    if "self._draw_eq(surface)" not in text and "self._draw_eq(self.game_surface)" not in text:
        print("ATTENTION: _draw_eq n'est pas appele dans draw jukebox.")
        print("Cherche le bloc 'Progress of current audio' et ajoute:")
        print("    self._eq_tick(key, pos, playing, self.dt)")
        print("    self._draw_eq(surface)")

    # Time label above the EQ, never across the bars
    old_clock = "BASE_WIDTH // 2 - clock.get_width() // 2, by - 26"
    new_clock = "BASE_WIDTH // 2 - clock.get_width() // 2, pheq_clock_y(BASE_HEIGHT)"
    if old_clock in text:
        text = text.replace(old_clock, new_clock)
    elif "by - 122" in text:
        text = text.replace(
            "BASE_WIDTH // 2 - clock.get_width() // 2, by - 122",
            new_clock,
        )
    elif "pheq_clock_y(BASE_HEIGHT)" not in text and "clock.get_width()" in text:
        text = text.replace(", by - 26)", ", pheq_clock_y(BASE_HEIGHT))")

    text = _patch_ingame_music(text)

    open(GAME, "w", encoding="utf-8", newline="\n").write(text)
    print("Patch EQ + musique en jeu applique.")
    return 0


INGAME_IMPORT = (
    "from ingame_music import cycle as ingame_cycle, label as ingame_label, normalize as ingame_normalize\n"
    "from mp3_title import title_from_path, title_for_key\n"
)


def _patch_ingame_music(text):
    if "from ingame_music import" not in text:
        if IMPORT in text:
            text = text.replace(IMPORT, IMPORT + INGAME_IMPORT, 1)
        elif "from pheq import" in text:
            text = text.replace(
                [ln for ln in text.splitlines(True) if ln.startswith("from pheq import")][0],
                [ln for ln in text.splitlines(True) if ln.startswith("from pheq import")][0] + INGAME_IMPORT,
                1,
            )

    if "self.ingame_music" not in text:
        needle = "self.juke_paused = False\n"
        if needle in text:
            text = text.replace(
                needle,
                needle + "        self.ingame_music = getattr(self, \"ingame_music\", \"none\")\n",
                1,
            )

    # Options spec list
    if '"ingame_music"' not in text:
        for a, b in (
            ('"audio_mix", "rumble"', '"audio_mix", "ingame_music", "rumble"'),
            ('"audio_mix",\n', '"audio_mix", "ingame_music",\n'),
            ("\"audio_mix\", \"rumble\"", "\"audio_mix\", \"ingame_music\", \"rumble\""),
        ):
            if a in text:
                text = text.replace(a, b, 1)
                break

    # Labels mapping
    if '"ingame_music":' not in text and '"audio_mix":' in text:
        old = '''            "audio_mix": f"{t('opt_audio')} :  <  {t('audio_' + getattr(self, 'audio_mix', 'sfx'))}  >",'''
        new = old + '''
            "ingame_music": f"{t('opt_ingame_music') if False else 'Musique en jeu'} :  <  {ingame_label(getattr(self, 'ingame_music', 'none'), t, asset_path)}  >",'''
        if old in text:
            text = text.replace(old, new, 1)
        else:
            # looser insert after audio_mix line
            lines = text.splitlines(True)
            out = []
            done = False
            for ln in lines:
                out.append(ln)
                if (not done) and '"audio_mix":' in ln and "opt_audio" in ln:
                    out.append(
                        '            "ingame_music": f"Musique en jeu :  <  {ingame_label(getattr(self, \'ingame_music\', \'none\'), t)}  >",\n'
                    )
                    done = True
            text = "".join(out)

    # Left/right handler
    if 'key == "ingame_music"' not in text and 'key == "audio_mix"' in text:
        marker = 'elif key == "audio_mix":'
        idx = text.find(marker)
        if idx >= 0:
            # insert after that elif block (next elif or next def-level)
            insert_at = text.find("\n        elif key ==", idx + 5)
            if insert_at < 0:
                insert_at = text.find("\n        if key ==", idx + 5)
            block = '''
        elif key == "ingame_music":
            self.ingame_music = ingame_cycle(getattr(self, "ingame_music", "none"), direction)
'''
            if insert_at > 0:
                text = text[:insert_at] + "\n" + block + text[insert_at:]

    # Help panel key list
    if '"ingame_music"' in text and "opt_help_ingame" not in text:
        text = text.replace(
            '"audio_mix", "rumble", "display"',
            '"audio_mix", "ingame_music", "rumble", "display"',
        )

    if "def _tick_ingame_music" not in text:
        mark = text.find("    def _update_music")
        if mark < 0:
            mark = text.find("    def _eq_ensure")
        if mark >= 0:
            text = text[:mark] + '''
    def _tick_ingame_music(self):
        """Play the Options in-game track during a run (Off + 5 jukebox themes)."""
        if not getattr(self, "started", False) or getattr(self, "game_over", False):
            return
        if getattr(self, "attract_mode", False):
            return
        if getattr(self, "menu_screen", "") == "jukebox":
            return
        want = ingame_normalize(getattr(self, "ingame_music", "none"))
        if want == "none":
            return
        try:
            self.sounds.play_music(want)
        except Exception:
            pass

''' + text[mark:]

    if "self._tick_ingame_music()" not in text:
        if "self._update_music()" in text:
            text = text.replace(
                "self._update_music()",
                "self._update_music(); self._tick_ingame_music()",
                1,
            )


    # Jukebox list: ID3 Title, never filename
    if "def _juke_title" not in text:
        mark = text.find("    def _draw_jukebox")
        if mark >= 0:
            text = text[:mark] + """    def _juke_title(self, key, path=None):
        if path:
            return title_from_path(path)
        return title_for_key(asset_path, key)

""" + text[mark:]
    if "def _juke_title" in text:
        start = text.find("    def _juke_title")
        end = text.find("\n    def ", start + 10)
        if start >= 0 and end > start:
            text = text[:start] + """    def _juke_title(self, key, path=None):
        if path:
            return title_from_path(path)
        return title_for_key(asset_path, key)

""" + text[end:]

    return text


if __name__ == "__main__":
    sys.exit(main())
