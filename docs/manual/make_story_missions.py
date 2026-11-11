"""
Write docs/STORY_MISSIONS.md, the list of the missions of the Adventure, from src/story_state.py (MISSIONS) and the
French and English titles of src/i18n.py. Run it again whenever a mission or an unlock changes:

    python docs/manual/make_story_missions.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

import i18n            # noqa: E402
import story_state as ss   # noqa: E402

OUT = os.path.join(ROOT, "docs", "STORY_MISSIONS.md")
VERSION = open(os.path.join(ROOT, "VERSION"), encoding="utf-8").read().strip()

# flags that are not in an `unlock` list: who sets them
EXTRA_SETTERS = {"act3": "act3_gate", ss.ENDING_DONE: ss.ENDING_MISSION}
ACT_NAMES = {1: "Acte 1 - le Shield", 2: "Acte 2 - le Phenix", 3: "Acte 3 - la Riposte",
             4: "Acte IV - No Mercy Left (fin ouverte et BONUS DE FIN)"}


def title(m, lang):
    i18n.set_lang(lang)
    return i18n.t(m["title"]).replace("|", "/")


def setters():
    out = {}
    for m in ss.MISSIONS:
        for flag in m.get("unlock") or []:
            out.setdefault(flag, []).append(m["id"])
    for flag, mid in EXTRA_SETTERS.items():
        out.setdefault(flag, []).append(mid)
    return out


def need_text(m, who, by_id):
    need = m.get("need")
    if m.get("needs_reactor"):
        return "un réacteur 2D installé sur un vaisseau"
    if not need:
        return "dès le départ"
    ids = [i for i in who.get(need, []) if i != m["id"]] or who.get(need, [])
    names = sorted({title(by_id[i], "fr") for i in ids})
    return "%s (`%s`)" % (" ou ".join(names), need) if names else "`%s`" % need


def notes(m):
    n = []
    if m.get("secret"):
        n.append("secrète jusqu'à son ouverture")
    if m.get("hull"):
        n.append("vaisseau gardé : %s" % m["hull"])
    if m.get("extra"):
        n.append("facultative")
    if m.get("final_bonus"):
        n.append("BONUS FINAL, sans fin")
    if m.get("once"):
        n.append("une seule fois" + (" (rejouable après `%s`)" % m["replay"] if m.get("replay") else ""))
    elif (m.get("hunt") or m.get("asteroids") or m.get("paint")) and not m.get("final_bonus"):
        n.append("rejouable")
    if m.get("fuel"):
        n.append("carburant %d" % m["fuel"])
    if m.get("target"):
        n.append("%d astéroïdes" % m["target"])
    if m.get("raid"):
        n.append("raid niveau %d" % m["raid"])
    if m.get("planet"):
        n.append(m["planet"])
    if m.get("carry"):
        n.append("reste sur la carte des actes suivants tant qu'elle n'est pas gagnée")
    if m.get("playable") is False:
        n.append("non jouable (annonce)")
    return ", ".join(n)


def first_act(m):
    """The act a mission is first on the map of (`acts`, else its `home` act, else Act 1)."""
    return min(m.get("acts") or (m.get("home") or 1,))


def kind(m):
    for k, label in (("lander", "Lunar Lander"), ("scramble", "Scramble"), ("spacewar", "Space War"),
                     ("asteroids", "Asteroids"), ("invaders", "Space Invaders"), ("galaga", "Galaga"),
                     ("escort", "escorte"), ("swarm", "nuée"), ("ending", "fin")):
        if m.get(k):
            return label
    return "vagues"


def main():
    by_id = {m["id"]: m for m in ss.MISSIONS}
    who = setters()
    lines = ["# Phenix Rebirth - Missions de l'Aventure (v%s)" % VERSION, "",
             "Liste des %d missions de `src/story_state.py` (`MISSIONS`), écrite par "
             "`python docs/manual/make_story_missions.py` : ne pas la modifier à la main." % len(ss.MISSIONS), "",
             "- `id` : identifiant stable (une sauvegarde le garde ; une mission retirée va dans `REMOVED_MISSIONS`)",
             "- `need` : le drapeau qui ouvre la mission ; il est posé par la victoire d'une mission (`unlock`)",
             "- *une seule fois* : jouée une fois jusqu'à la fin ouverte de l'acte IV (`ending_done`), "
             "puis toutes les missions sont rejouables",
             "- Titres français et anglais : `src/i18n.py`. Le manuel du joueur (docs/manual) en reprend l'ordre.",
             ""]
    for act in (1, 2, 3, 4):
        ms = [m for m in ss.MISSIONS if first_act(m) == act]
        lines += ["## %s" % ACT_NAMES[act], "", "| id | Mission (FR) | Mission (EN) | Type | S'ouvre après | Notes |",
                  "|---|---|---|---|---|---|"]
        for m in ms:
            lines.append("| `%s` | %s | %s | %s | %s | %s |" % (m["id"], title(m, "fr"), title(m, "en"), kind(m),
                                                             need_text(m, who, by_id), notes(m)))
        lines.append("")
    lines += ["Une mission listée dans plusieurs actes (atterrissages, raids, Sentinelles, BONUS) n'apparaît ici "
              "que dans le premier.", ""]
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(OUT)


if __name__ == "__main__":
    main()
