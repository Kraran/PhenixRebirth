#!/usr/bin/env python3
"""Idempotent: add x= pan args to play() calls in this install."""
import os
import re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")


def sub_once(text, old, new):
    if new in text:
        return text, False
    if old not in text:
        return text, False
    return text.replace(old, new), True


def patch_player(t):
    n = 0
    t, c = sub_once(t, 'self.sounds.play("shoot", volume=0.45)',
                    'self.sounds.play("shoot", volume=0.45, x=self.x)')
    n += int(c)
    t, c = sub_once(t, 'self.sounds.play("phenix_activate")',
                    'self.sounds.play("phenix_activate", x=self.x)')
    n += int(c)
    t, c = sub_once(t, 'self.sounds.play("phenix_end")',
                    'self.sounds.play("phenix_end", x=self.x)')
    n += int(c)
    # remaining phenix_end without x
    t2 = t.replace('self.sounds.play("phenix_end")',
                   'self.sounds.play("phenix_end", x=self.x)')
    if t2 != t:
        n += t.count('self.sounds.play("phenix_end")')
        t = t2
    return t, n


def patch_enemy(t):
    t, c = sub_once(t, 'self.sounds.play("enemy_shoot")',
                    'self.sounds.play("enemy_shoot", x=enemy.x)')
    return t, int(c)


def patch_game(t):
    n = 0
    reps = [
        ('self.sounds.play("explosion_big" if ship.dying else "explosion")',
         'self.sounds.play("explosion_big" if ship.dying else "explosion", x=ship.x)'),
        ('self.sounds.play("enemy_explosion", volume=0.4)',
         'self.sounds.play("enemy_explosion", volume=0.4, x=target.x)'),
        ('self.sounds.play("enemy_explosion", volume=0.5)',
         'self.sounds.play("enemy_explosion", volume=0.5, x=enemy.x)'),
        ('self.sounds.play("explosion")',
         'self.sounds.play("explosion", x=ship.x)'),
        ('self.sounds.play_electric(True)',
         'self.sounds.play_electric(True, x=ship.x)'),
        ('self.sounds.play_electric(tesla_on or flash_on)',
         'self.sounds.play_electric(tesla_on or flash_on, x=self._sfx_electric_x())'),
        ('self.sounds.play_electric(tesla_on)',
         'self.sounds.play_electric(tesla_on, x=self._sfx_electric_x())'),
    ]
    for old, new in reps:
        t, c = sub_once(t, old, new)
        n += int(c)
    # remaining enemy_explosion without x= (body hits)
    def add_enemy_x(m):
        return m.group(0)[:-1] + ", x=enemy.x)"
    t2, k = re.subn(
        r'self\.sounds\.play\("enemy_explosion"\)',
        'self.sounds.play("enemy_explosion", x=enemy.x)',
        t,
    )
    t, n = t2, n + k
    t2, k = re.subn(
        r'self\.sounds\.play\("explosion_big"\)',
        'self.sounds.play("explosion_big", x=ship.x)',
        t,
    )
    t, n = t2, n + k
    helper = '''
    def _sfx_electric_x(self):
        """Pan tesla/edge crackle to the wall or the sparking ship."""
        fx = getattr(self, "tesla_fx", None)
        if fx is not None:
            return getattr(fx, "x", 0)
        for p in self._ships():
            if getattr(p, "edge_flash", 0) > 0.08:
                return p.x
        return None
'''
    if "def _sfx_electric_x" not in t:
        # insert before _start_coop or after _ships
        if "def _start_coop(self):" in t:
            t = t.replace("def _start_coop(self):", helper + "\n    def _start_coop(self):", 1)
            n += 1
        elif "def _ships(self):" in t:
            t = t.replace("def _ships(self):", "def _ships(self):", 1)
            # append after class methods is harder; skip
    return t, n


def apply(name, fn):
    path = os.path.join(ROOT, name)
    if not os.path.isfile(path):
        print("skip", name)
        return
    raw = open(path, encoding="utf-8").read()
    new, n = fn(raw)
    if n and new != raw:
        open(path, "w", encoding="utf-8", newline="\n").write(new)
        print("patched", name, n, "edits")
    else:
        print("ok", name, "(already panned or no match)")


def main():
    apply("player.py", patch_player)
    apply("enemy.py", patch_enemy)
    apply("game.py", patch_game)
    print("Done.")


if __name__ == "__main__":
    main()
