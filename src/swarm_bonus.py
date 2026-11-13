"""BONUS FINAL - Nuée (story_state.MISSIONS "bonus_swarm"): the last wave of Défense de Phobos II without an end.

The four kinds of enemies at level 16, 30 % more on screen at once than a plain swarm, and the fallen always come back
(enemy.EnemyFormation.spawn_swarm `ramp`): it starts with a few blue birds and grows to its full screen in a minute
(RAMP: the khaki birds, then the grey gargoyles, then the dark ones). Then three Guardians come, and three more each time
the last of them falls (GUARDIANS_AGAIN s later). The run goes on until the ship is lost (the GAME OVER); everything of
the workshop flies with the pilot's ship.

Who flies is chosen in a menu (story.py, the screen of the choices of the final BONUS missions), VARIANTS:

  solo        the pilot's ship alone
  sacha_ai    the pilot's ship, and Sacha in his EDF-17 C flown by the computer (src/wingman.py), sharper than in the
              story missions (wingman.ACE); after his third hit he goes back to Phobos and comes back repaired
              (wingman.COMEBACK s later)
  duo         the pilot's ship (player 1) and Sacha's EDF-17 C flown by a second player (the devices of the coop game,
              Options > CONTROLS): three hits and it is destroyed; the run goes on while one of them flies
  sacha       Sacha's EDF-17 C alone, flown by the player: three hits (its lives) and the run is over
  sacha_lead  Sacha's EDF-17 C flown by the player, and the pilot's ship (its hull, its speed and its lives from the
              workshop) flown by the computer; the run is over when the EDF-17 C is destroyed

Each version keeps its own record in the save (story_state.ENDLESS_BEST "bonus_swarm:<version>"; two at two: the pilot's
and Sacha's), shown at the top right. Leaving the run gains nothing; at the GAME OVER, PAY of the score is paid in
credits (PAY_DUO of the two scores together at two).
"""
import random
import threading

import pygame

from errlog import log_exc
from i18n import t
from settings import BASE_HEIGHT, BASE_WIDTH

MISSION = "bonus_swarm"
VARIANTS = ("solo", "sacha_ai", "duo", "sacha", "sacha_lead")
EDF_VARIANTS = ("sacha", "sacha_lead")     # the player flies Sacha's EDF-17 C: no item, no missile, no module
PAY = 0.10                                 # the share of the score paid at the GAME OVER
PAY_DUO = 0.05                             # ... of the two scores together, at two
# {kind: (s when it starts coming, s when it is all there)}: the blue birds at once, the dark gargoyles last
RAMP = {1: (0.0, 20.0), 2: (10.0, 30.0), 3: (25.0, 45.0), 4: (40.0, 60.0)}
GUARDIANS = 3                              # Guardians at a time...
GUARDIANS_FROM = 60.0                      # ... once the swarm is full (s)...
GUARDIANS_AGAIN = 12.0                     # ... and again this long after the last of them fell

PREVIEW_SIZE = (720, 405)                  # (the pictures of the menu: the size of the others)
_LOCK = threading.Lock()
_PREVIEWS = {}


# --- the launch ------------------------------------------------------------------------------------------------------
def launch_spec(spec, variant):
    """The launch spec of the mission (story.StoryHub._launch_selected): endless, the version chosen; on Sacha's EDF-17 C
    no item, no missile, no escort module (they belong to the pilot's ship)."""
    variant = variant if variant in VARIANTS else VARIANTS[0]
    spec.update(swarm_bonus=True, endless=True, variant=variant)
    spec.pop("guardians_wave", None)
    if variant in EDF_VARIANTS:
        spec["items"] = []
        spec.pop("antimatter", None)
        spec.pop("modules", None)
    return spec


def record_keys(variant):
    """Where the records of a version are kept (two at two: the pilot's, then Sacha's)."""
    if variant == "duo":
        return MISSION + ":duo", MISSION + ":duo_sacha"
    return (MISSION + ":" + str(variant),)


def records_text(state, variant):
    """The record(s) of a version, for the menu."""
    import story_state as ss
    keys = record_keys(variant)
    best = [ss.endless_best(state, k) for k in keys]
    if variant == "duo":
        return t("swarm_menu_records_duo").format(p1=_fmt(best[0]), p2=_fmt(best[1]))
    return t("swarm_menu_record").format(pts=_fmt(best[0]))


def _fmt(n):
    return "{:,}".format(int(n)).replace(",", " ")


def state(game):
    adv = getattr(game, "adventure", None) or {}
    if not adv.get("swarm_bonus"):
        return None
    return getattr(game, "swarm_bonus", None)


def variant(game):
    st = state(game)
    return st["variant"] if st else None


def start(game, spec):
    """At the start of the mission (Game._begin_adventure, after wingman.start): who flies."""
    game.swarm_bonus = None
    if not (spec or {}).get("swarm_bonus"):
        return
    import wingman
    v = spec.get("variant") if spec.get("variant") in VARIANTS else VARIANTS[0]
    game.swarm_bonus = {"variant": v, "guardian_wait": GUARDIANS_FROM, "skin": None, "clock": 0.0}
    game.wingman = None
    try:
        if v == "sacha_ai":
            game.wingman = wingman.Wingman(game, "sacha", ace=True, comeback=True)
        elif v == "duo":
            _, b2 = game._coop_bindings()
            game.wingman = wingman.Wingman(game, "sacha", control="human", binding=b2)
        elif v in EDF_VARIANTS:
            loadout = game.story.loadout() if getattr(game, "story", None) else {}
            _fly_edf17(game)
            if v == "sacha_lead":
                name = ((getattr(game, "story", None) and game.story.state) or {}).get("name") or None
                game.wingman = wingman.Wingman(game, "pilot", look="hull", ace=True, loadout=loadout, tag=name)
    except Exception:
        log_exc("swarm_bonus.start")


def _fly_edf17(game):
    """The player flies Sacha's EDF-17 C: a new ship in place of the pilot's, three hits (its lives)."""
    import wingman
    from player import Player
    old = game.player
    p = Player(old.x, old.y, ship_id="phoenix", tint="gold")
    wingman.dress_edf17(p, game)
    p.pid = 1
    p.lives = wingman.HITS
    p.adventure_wall = "instant"
    p.bullet_speed_mult = 1.0
    game.player = p
    game.swarm_bonus["skin"] = wingman.Wingman(game, "sacha", control="skin", ship=p)


def after_begin(game):
    """After the start of the mission: the little ships of the lives are EDF-17 C when the player flies it."""
    if variant(game) not in EDF_VARIANTS:
        return
    try:
        import wingman
        pic = wingman.pictures()[0]
        h = 22
        w = max(1, int(pic.get_width() * h / pic.get_height()))
        game.life_icon = pygame.transform.smoothscale(pic, (w, h))
    except Exception:
        log_exc("swarm_bonus.after_begin")


def binding_of(game, ship):
    """At two (duo): the device of the pilot's ship, player 1 of the coop game (else None: the solo controls)."""
    if variant(game) != "duo" or ship is not getattr(game, "player", None):
        return None
    try:
        b1, _ = game._coop_bindings()
        return b1
    except Exception:
        log_exc("swarm_bonus.binding_of")
        return None


# --- every frame -----------------------------------------------------------------------------------------------------
def tick(game):
    """The Guardians, again and again once the swarm is full; the smoke of the EDF-17 C flown by the player."""
    st = state(game)
    if st is None or not getattr(game, "started", False):
        return
    dt = float(getattr(game, "dt", 0.0) or 0.0)
    skin = st.get("skin")
    if skin is not None:
        try:
            skin.update(game, dt)
        except Exception:
            log_exc("swarm_bonus.tick")
    if game.stage_transition is not None:
        return
    st["clock"] += dt
    sq = getattr(game, "guardian_squad", None)
    if sq is not None and not sq.clear():
        return
    st["guardian_wait"] -= dt
    if st["guardian_wait"] > 0:
        return
    st["guardian_wait"] = GUARDIANS_AGAIN
    try:
        from guardian import SQUAD_Y, GuardianSquad
        from ship_burn import prepare as prepare_ship_burn
        prepare_ship_burn(game.player)              # (the burning ship of a laser, made before it is needed)
        game.guardian_squad = GuardianSquad(GUARDIANS, game.sounds, SQUAD_Y)
    except Exception:
        log_exc("swarm_bonus.tick")


def holds(game):
    """At two, the run goes on while Sacha's EDF-17 C still flies (the pilot's ship is lost)."""
    if variant(game) != "duo":
        return False
    w = getattr(game, "wingman", None)
    return w is not None and w.in_play()


def result(game):
    """(what is paid, {record key: score}) at the GAME OVER."""
    v = variant(game) or VARIANTS[0]
    score = int(getattr(game, "score", 0) or 0)
    keys = record_keys(v)
    if v == "duo":
        w = getattr(game, "wingman", None)
        sacha = int(getattr(getattr(w, "ship", None), "score", 0) or 0)
        return int((score + sacha) * PAY_DUO + 0.5), {keys[0]: score, keys[1]: sacha}
    return int(score * PAY + 0.5), {keys[0]: score}


# --- drawing ---------------------------------------------------------------------------------------------------------
def draw(game, surface):
    """The smoke of the EDF-17 C flown by the player (under the ships)."""
    st = state(game)
    skin = (st or {}).get("skin")
    if skin is not None:
        skin.draw(surface, game)


def draw_hud(game):
    """The record(s) of the version at the top right; at two, Sacha's score under them."""
    import story_state as ss
    import announce
    tc = game.text_cache
    st_save = getattr(getattr(game, "story", None), "state", None) or {}
    v = variant(game) or VARIANTS[0]
    keys = record_keys(v)
    surf = game.game_surface
    y = 44
    if v == "duo":
        w = getattr(game, "wingman", None)
        sacha = int(getattr(getattr(w, "ship", None), "score", 0) or 0)
        p1 = max(ss.endless_best(st_save, keys[0]), int(getattr(game, "score", 0) or 0))
        p2 = max(ss.endless_best(st_save, keys[1]), sacha)
        line = tc.get(game.font, t("swarm_records_duo").format(p1=game.format_score(p1), p2=game.format_score(p2)),
                      announce.REWARD)
        surf.blit(line, (BASE_WIDTH - 16 - line.get_width(), y))
        score = tc.get(game.font, t("swarm_sacha_score").format(pts=game.format_score(sacha)), (150, 235, 170))
        surf.blit(score, (BASE_WIDTH - 16 - score.get_width(), y + 28))
        return
    best = max(ss.endless_best(st_save, keys[0]), int(getattr(game, "score", 0) or 0))
    rec = tc.get(game.font, t("story_ast_record").format(pts=game.format_score(best)), announce.REWARD)
    surf.blit(rec, (BASE_WIDTH - 16 - rec.get_width(), y))


# --- the pictures of the menu ----------------------------------------------------------------------------------------
def preview(key, loadout=None):
    """A picture of a version for the menu (made once): who flies, on a dark sky under a few birds."""
    lo = loadout or {}
    ck = (key, lo.get("ship_id") or "shield", lo.get("tint") or "red")
    pic = _PREVIEWS.get(ck)
    if pic is None:
        with _LOCK:
            pic = _PREVIEWS.get(ck)
            if pic is None:
                pic = _PREVIEWS[ck] = _make_preview(key, ck[1], ck[2])
    return pic


def warm(order):
    """(The pictures are quick to make: nothing to do in the background.)"""
    return None


def _ship_picture(sid, tint):
    from player import Player
    return Player(0, 0, ship_id=sid, tint=tint).image


def _make_preview(key, sid, tint):
    import fonts
    import wingman
    from enemy import BigBird, Enemy
    from guardian import gargoyle_picture
    w, h = PREVIEW_SIZE
    surf = pygame.Surface((w, h))
    surf.fill((4, 6, 16))
    rng = random.Random(hash(key) & 0xFFFFFFFF)
    for _ in range(110):
        b = rng.randint(120, 255)
        surf.set_at((rng.randint(0, w - 1), rng.randint(0, h - 1)), (b, b, min(255, b + 20)))
    try:
        birds = [Enemy(0, 0, stage=1).frames[0], Enemy(0, 0, stage=2).frames[0],
                 gargoyle_picture(BigBird(0, 0, stage=3)), gargoyle_picture(BigBird(0, 0, stage=4))]
    except Exception:
        log_exc("swarm_bonus._make_preview")
        birds = []
    for i in range(9):
        if not birds:
            break
        img = birds[(0, 1, 2, 1, 0, 3, 1, 0, 1)[i] % len(birds)]
        scale = 0.7 if img.get_width() > 70 else 1.0
        img = pygame.transform.rotozoom(img, 0, scale)
        x = 60 + i * (w - 120) / 8.0
        y = 50 + (i % 3) * 34
        surf.blit(img, (int(x - img.get_width() / 2), int(y - img.get_height() / 2)))
    edf = wingman.pictures()[0]
    try:
        own = _ship_picture(sid, tint)
    except Exception:
        log_exc("swarm_bonus._make_preview")
        own = edf
    ships = {
        "solo": [(own, "swarm_tag_you")],
        "sacha_ai": [(own, "swarm_tag_you"), (edf, "swarm_tag_ai")],
        "duo": [(own, "swarm_tag_p1"), (edf, "swarm_tag_p2")],
        "sacha": [(edf, "swarm_tag_you")],
        "sacha_lead": [(own, "swarm_tag_ai"), (edf, "swarm_tag_you")],
    }.get(key, [(own, "swarm_tag_you")])
    font = fonts.text(22)
    n = len(ships)
    for i, (img, tag) in enumerate(ships):
        big = pygame.transform.rotozoom(img, 0, 1.6)
        cx = w / 2 + (i - (n - 1) / 2.0) * 210
        cy = h - 150
        surf.blit(big, (int(cx - big.get_width() / 2), int(cy - big.get_height() / 2)))
        label = font.render(t(tag), True, (150, 235, 170) if tag == "swarm_tag_ai" else (255, 230, 140))
        surf.blit(label, (int(cx - label.get_width() / 2), int(cy + big.get_height() / 2 + 10)))
    return surf
