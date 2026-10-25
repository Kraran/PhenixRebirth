"""
Adventure rules and save data (no drawing, no window).

Everything the adventure *decides* lives here so it can be tested without a
screen: the default hangar, the mission list, the workshop upgrades, what a
mission result changes, and how a save slot is read, migrated and written.
`story.py` only draws these things and handles the menu input.

Save file: one JSON per slot (story_1.json ... story_4.json), version 4.
Durations (dome time and recharge) are stored in SECONDS, so they do not
depend on the frame rate. Version 2 files stored them in frames at 60 Hz.
Version 4 is the Act 1 hangar: the Shield starts at 40 % speed with one life,
no dome and deadly walls (see ACT_CAPS and UPGRADES).
"""
import json
import math
import os
import time
import unicodedata

import story_items
import story_vn
from safe_io import atomic_write_json, backup_unreadable
from settings import asset_path, user_data_dir, ENEMY_VETERAN_BONUS

SAVE_VERSION = 4
SLOT_COUNT = 4
MODES = ("novice", "normal", "veteran")
DEFAULT_MODE = "normal"
NAME_MAX = 12
# A failed mission (Normal and Novice modes) gains nothing and costs this share of the credits held.
# Veteran: a failure is a permanent death.
PENALTY_RATE = 0.05
NOVICE_PENALTY_RATE = 0.02
# Novice mode: the hulls start with three lives (the workshop sells the fourth, like the second one in Normal).
NOVICE_LIVES = 3
NAME_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- "

# Speed steps (% of the arcade ship) and what each act allows the workshop to reach.
SPEED_START = 40
ACT_CAPS = {
    1: {"speed": 80, "lives": 2},      # Act 1: about 80 % of the arcade ship, no dome
    2: {"speed": 80, "lives": 2},      # Act 2: the same, and the Phenix joins the hangar
    3: {"speed": 100, "lives": 3},     # Act 3: the hull kept is brought to 100 %, like the arcade ship
}

# Dome (Shield bubble): seconds. 2.0 s / 5.0 s is the arcade Shield.
DOME_DUR_START = 1.0
DOME_DUR_STEP = 0.5
DOME_DUR_MAX = 2.0
DOME_CD_START = 5.0
DOME_CD_STEP = 1.0
DOME_CD_MIN = 3.0
_EPS = 1e-6

ACT3_PENDING = "act3_pending"          # Act 2 is won: the scene of the attack and the choice of the hull wait
GAME_WON = "game_won"                  # the last mission of Act 3 is won: the Adventure is over (it can still be played)
HULLS = ("shield", "phoenix")

GALAGA_STAGE = 6                       # arcade stage the BONUS mission plays at: level 2 (x1.1 speed, +10 points a bird)
LEGACY_VERTICAL_FLAG = "vertical_thrust"   # the first BONUS mission (v1.5) gave the flight outright: such a save keeps it
PHENIX_FIRE_MULT = 1.5                 # the Phenix BONUS mission: the birds shoot one and a half times as often

# Chapter 1: main sorties are stage-1 birds only.
# Other hulls are met (and unlocked) in Bestiary nodes.
# Phoenix hull is not granted here — end of chapter 2.
MISSIONS = [
    {
        "id": "ch1_sortie",
        "hunt": True,
        "title": "story_m_sortie",
        "blurb": "story_m_sortie_b",
        "need": None,
        "content": 1,
        "speed": 1.0,
        "unlock": ["ch1_sortie", "ch1_speed"],
        "log": "story_log_sortie",
    },
    {
        "id": "best_s2",
        "hunt": True,
        "title": "story_m_best2",
        "blurb": "story_m_best2_b",
        "need": "ch1_sortie",
        "content": 2,
        "speed": 1.0,
        "unlock": ["bestiary_s2", "ch1_life_2"],
        "log": "story_log_best2",
    },
    {
        "id": "best_s3",
        "hunt": True,
        "title": "story_m_best3",
        "blurb": "story_m_best3_b",
        "need": "bestiary_s2",
        "content": 3,
        "speed": 1.0,
        "unlock": ["bestiary_s3", "ch1_wall"],
        "log": "story_log_best3",
    },
    {
        "id": "best_s4",
        "hunt": True,
        "title": "story_m_best4",
        "blurb": "story_m_best4_b",
        "need": "bestiary_s3",
        "content": 4,
        "speed": 1.0,
        "unlock": ["bestiary_s4"],
        "log": "story_log_best4",
    },
    # BONUS: the two-dimensional impulse reactor, in two versions. Hidden until the dark gargoyles are filed (the Phenix
    # one: until the Phenix is in the hangar), then on the map until the reactor is caught. Waves in the way of Namco's
    # Galaga (src/galaga.py), birds of level 2 (arcade stages 6 / 7). The reactor is an item that falls ONCE at a random
    # moment of the waves (src/story_items.py); a mission that ends without it is offered again. Caught, it goes on sale
    # in the hangar for its hull only (Shield 2000, Phenix 4000) and, installed, lets that hull fly up and down the
    # lower third of the screen for good. `ship` imposes the hull, `home` is the act the mission stays on the map for.
    {
        "id": "bonus_2d",
        "secret": True,
        "carry": True,                      # still on the map of the next acts while the reactor is not caught
        "home": 1,
        "galaga": True,
        "reactor": "shield",
        "ship": "shield",
        "title": "story_m_bonus2d",
        "hud_title": "story_m_bonus2d_hud",
        "blurb": "story_m_bonus2d_b",
        "need": "bestiary_s4",
        "content": 1,
        "stage": GALAGA_STAGE,
        "speed": 1.0,
        "log": "story_log_bonus2d",
    },
    {
        "id": "bonus_2d_phenix",
        "secret": True,
        "carry": True,
        "home": 2,
        "galaga": True,
        "reactor": "phoenix",
        "ship": "phoenix",
        "fire_mult": PHENIX_FIRE_MULT,      # the birds shoot more
        "title": "story_m_bonus2dp",
        "hud_title": "story_m_bonus2dp_hud",
        "blurb": "story_m_bonus2dp_b",
        "need": "phenix_owned",
        "content": 1,
        "stage": GALAGA_STAGE,
        "speed": 1.0,
        "log": "story_log_bonus2dp",
    },
    # BONUS of Act 2: the VIP rescue (src/escort.py). Open once a hull has its two-dimensional reactor installed, and
    # flown only by such a hull (`needs_reactor`: the one selected if it has it, else the other). Once only; still on
    # the map of Act 3 while it is not won. The victory tells who was on board (scene VIP_SCENE) and opens Lyra Voss's
    # concert in the Phobos bar (flag LYRA_FLAG, the videos come later).
    {
        "id": "bonus_vip",
        "acts": (2, 3),
        "secret": True,
        "carry": True,
        "home": 2,
        "needs_reactor": True,
        "escort": True,
        "title": "story_m_vip",
        "hud_title": "story_m_vip_hud",
        "blurb": "story_m_vip_b",
        "need": None,
        "content": 1,
        "stage": 6,                         # the birds of level 2 (arcade stages 6 / 7)
        "speed": 1.0,
        "once": True,
        "unlock": ["lyra_concert"],
        "win_scene": "vip_lyra",
        "log": "story_log_vip",
    },
    # The dome series: Dome I is open from the start, each mission opens the next one and can be flown only once.
    # `waves` are arcade stage numbers (1, 6, 11 = the same wave at 1.0x, 1.1x, 1.2x speed).
    {
        # the prelude of each act's main series (Act 1: the Dome; Act 2: the Phenix; Act 3: la Riposte): the Asteroids level
        # (src/asteroids.py) that opens a road through the belt. Replayable and paid every time; its first victory opens the
        # first mission of the series
        "id": "ast_1",
        "acts": (1,),
        "asteroids": True,
        "title": "story_m_ast1",
        "hud_title": "story_m_ast_hud",
        "blurb": "story_m_ast_b",
        "need": None,                       # open from the start, like the first Bestiary sortie
        "content": 1,
        "target": 60,
        "speed": 1.0,
        "unlock": ["ast_s1"],
        "log": "story_log_ast1",
    },
    {
        "id": "dome_1",
        "acts": (1,),
        "title": "story_m_dome1",
        "blurb": "story_m_dome1_b",
        "need": "ast_s1",                   # the road through the belt first (ast_1)
        "content": 1,
        "waves": [1, 6, 11],
        "speed": 1.0,
        "once": True,
        "unlock": ["dome_s1"],
        "log": "story_log_dome1",
    },
    {
        "id": "dome_2",
        "acts": (1,),
        "title": "story_m_dome2",
        "blurb": "story_m_dome2_b",
        "need": "dome_s1",
        "content": 2,
        "waves": [2, 7, 12],
        "speed": 1.0,
        "once": True,
        "unlock": ["dome_s2"],
        "log": "story_log_dome2",
    },
    {
        "id": "dome_3",
        "acts": (1,),
        "title": "story_m_dome3",
        "blurb": "story_m_dome3_b",
        "need": "dome_s2",
        "content": 3,
        "waves": [3, 8, 13],
        "speed": 1.0,
        "once": True,
        "unlock": ["dome_s3"],
        "log": "story_log_dome3",
    },
    {
        "id": "dome_4",
        "acts": (1,),
        "title": "story_m_dome4",
        "blurb": "story_m_dome4_b",
        "need": "dome_s3",
        "content": 4,
        "waves": [4, 9, 14],
        "speed": 1.0,
        "once": True,
        "unlock": ["dome_s4"],
        "log": "story_log_dome4",
    },
    {
        # all four enemies at once (levels 11 to 14), replaced as they fall; opens the dome
        "id": "dome_5",
        "acts": (1,),
        "title": "story_m_dome5",
        "blurb": "story_m_dome5_b",
        "need": "dome_s4",
        "content": 1,
        "swarm": True,
        "stage": 11,
        "speed": 1.0,
        "once": True,
        "unlock": ["dome_s5", "dome_online"],
        "log": "story_log_dome5",
    },
    {
        # a full run of the arcade levels 11 to 15; the death of the boss starts Act 2
        "id": "act2_gate",
        "acts": (1,),
        "title": "story_m_gate2",
        "blurb": "story_m_gate2_b",
        "need": "dome_s5",
        "content": 1,
        "waves": [11, 12, 13, 14, 15],
        "speed": 1.0,
        "once": True,
        "unlock": ["act2"],
        "act": 2,
        "log": "story_log_gate2",
    },
    {
        "id": "ch2_tease",
        "acts": (1,),
        "title": "story_m_ch2",
        "blurb": "story_m_ch2_b",
        "need": "act2",
        "content": 0,
        "speed": 1.0,
        "unlock": [],
        "log": "",
        "playable": False,
    },
    {
        # Act 2 Bestiary hunt: the saucer and its commander (the arcade boss level, 5). Replayable;
        # level 2 is the boss of level 10, level 3 that of level 15...
        "id": "best_boss",
        "hunt": True,
        "acts": (2, 3),
        "title": "story_m_bestboss",
        "blurb": "story_m_bestboss_b",
        "need": "act2",
        "content": 5,
        "waves": [5],
        "speed": 1.0,
        "unlock": [],
        "log": "story_log_bestboss",
    },
    # Act 2: the Phenix series. Five chained missions, flown once each (arcade levels 16 and up,
    # x1.3 speed). The last one hands over the Phenix and opens its workshop.
    {
        "id": "ast_2",
        "acts": (2,),
        "asteroids": True,
        "title": "story_m_ast2",
        "hud_title": "story_m_ast_hud",
        "blurb": "story_m_ast_b",
        "need": "act2",
        "content": 1,
        "target": 80,
        "speed": 1.0,
        "unlock": ["ast_s2"],
        "log": "story_log_ast2",
    },
    {
        "id": "phenix_1",
        "acts": (2,),
        "title": "story_m_ph1",
        "blurb": "story_m_ph1_b",
        "need": "ast_s2",
        "content": 1,
        "waves": [16, 17],
        "speed": 1.0,
        "once": True,
        "unlock": ["phenix_s1"],
        "log": "story_log_ph1",
    },
    {
        "id": "phenix_2",
        "acts": (2,),
        "title": "story_m_ph2",
        "blurb": "story_m_ph2_b",
        "need": "phenix_s1",
        "content": 1,
        "swarm": True,
        "swarm_screens": 1,          # one normal screen of each kind in all (the dome swarm has 2)
        "stage": 16,
        "speed": 1.0,
        "once": True,
        "unlock": ["phenix_s2"],
        "log": "story_log_ph2",
    },
    {
        "id": "phenix_3",
        "acts": (2,),
        "title": "story_m_ph3",
        "blurb": "story_m_ph3_b",
        "need": "phenix_s2",
        "content": 3,
        "waves": [18, 19],
        "speed": 1.0,
        "once": True,
        "unlock": ["phenix_s3"],
        "log": "story_log_ph3",
    },
    {
        "id": "phenix_4",
        "acts": (2,),
        "title": "story_m_ph4",
        "blurb": "story_m_ph4_b",
        "need": "phenix_s3",
        "content": 1,
        "waves": [16, 17, 18, 19],
        "speed": 1.0,
        "once": True,
        "unlock": ["phenix_s4"],
        "log": "story_log_ph4",
    },
    {
        # a full run of the arcade levels 16 to 20: the boss guards the Phenix
        "id": "phenix_5",
        "acts": (2,),
        "title": "story_m_ph5",
        "blurb": "story_m_ph5_b",
        "need": "phenix_s4",
        "content": 1,
        "waves": [16, 17, 18, 19, 20],
        "speed": 1.0,
        "once": True,
        "unlock": ["phenix_s5", "phenix_owned"],
        "grant_hull": "phoenix",
        "log": "story_log_ph5",
    },

    # Act 2: the paint series. Three optional missions, flown in order; when the third is won the
    # paint shop opens for ONE change of colour. The whole series can be flown again (harder each
    # time, like the Bestiary sorties) to earn another change. Each one is a Space Invaders grid (`invaders`)
    # whose level is 1, 2, 3 in the first pass, then 4, 5, 6, and so on.
    {
        "id": "paint_1",
        "acts": (2, 3),
        "paint": 1,
        "title": "story_m_pt1",
        "blurb": "story_m_pt1_b",
        "need": "act2",
        "content": 1,
        "invaders": True,
        "speed": 1.0,
        "unlock": [],
        "log": "story_log_pt1",
    },
    {
        "id": "paint_2",
        "acts": (2, 3),
        "paint": 2,
        "title": "story_m_pt2",
        "blurb": "story_m_pt2_b",
        "need": "act2",
        "content": 3,
        "invaders": True,
        "speed": 1.0,
        "unlock": [],
        "log": "story_log_pt2",
    },
    {
        "id": "paint_3",
        "acts": (2, 3),
        "paint": 3,
        "title": "story_m_pt3",
        "blurb": "story_m_pt3_b",
        "need": "act2",
        "content": 1,
        "invaders": True,
        "speed": 1.0,
        "unlock": [],
        "log": "story_log_pt3",
    },

    # The last mission of Act 2: a full run of the arcade levels 21 to 25, open once the Phenix is in the hangar.
    # Its victory does not start Act 3 at once: Phobos is attacked (scene "act3_attack"), the pilot must choose the
    # hull that keeps the quantum anchor, the other one is lost (see choose_act3_ship). Until the choice is made the
    # save waits with the flag ACT3_PENDING (the scene comes back when the save is opened).
    {
        "id": "act3_gate",
        "acts": (2,),
        "title": "story_m_gate3",
        "blurb": "story_m_gate3_b",
        "need": "phenix_owned",
        "content": 1,
        "waves": [21, 22, 23, 24, 25],
        "speed": 1.0,
        "once": True,
        "unlock": [],
        "act3": True,
        "log": "story_log_gate3",
    },

    # Act 3: the hull kept is brought to 100 % (the arcade ship) by a series of repair missions, one version for each
    # hull (`hull`: listed only when it is the one kept). Each mission opens one line of the workshop; the last one
    # opens the final series. Flown once each, in order.
    {
        "id": "up_shield_1", "hull": "shield", "acts": (3,), "title": "story_m_ups1", "blurb": "story_m_ups1_b",
        "need": "act3", "content": 1, "waves": [16, 17], "speed": 1.0, "once": True,
        "unlock": ["ch3_speed"], "log": "story_log_ups1",
    },
    {
        "id": "up_shield_2", "hull": "shield", "acts": (3,), "title": "story_m_ups2", "blurb": "story_m_ups2_b",
        "need": "ch3_speed", "content": 1, "waves": [18, 19], "speed": 1.0, "once": True,
        "unlock": ["ch3_lives"], "log": "story_log_ups2",
    },
    {
        "id": "up_shield_3", "hull": "shield", "acts": (3,), "title": "story_m_ups3", "blurb": "story_m_ups3_b",
        "need": "ch3_lives", "content": 1, "swarm": True, "swarm_screens": 1, "stage": 16, "speed": 1.0,
        "once": True, "unlock": ["ch3_wall"], "log": "story_log_ups3",
    },
    {
        "id": "up_shield_4", "hull": "shield", "acts": (3,), "title": "story_m_ups4", "blurb": "story_m_ups4_b",
        "need": "ch3_wall", "content": 1, "waves": [16, 17, 18, 19, 20], "speed": 1.0, "once": True,
        "unlock": ["ch3_dome", "ch3_ready"], "log": "story_log_ups4",
    },
    {
        "id": "up_phenix_1", "hull": "phoenix", "acts": (3,), "title": "story_m_upp1", "blurb": "story_m_upp1_b",
        "need": "act3", "content": 1, "waves": [16, 17], "speed": 1.0, "once": True,
        "unlock": ["ch3_speed"], "log": "story_log_upp1",
    },
    {
        "id": "up_phenix_2", "hull": "phoenix", "acts": (3,), "title": "story_m_upp2", "blurb": "story_m_upp2_b",
        "need": "ch3_speed", "content": 1, "waves": [18, 19], "speed": 1.0, "once": True,
        "unlock": ["ch3_lives"], "log": "story_log_upp2",
    },
    {
        "id": "up_phenix_3", "hull": "phoenix", "acts": (3,), "title": "story_m_upp3", "blurb": "story_m_upp3_b",
        "need": "ch3_lives", "content": 1, "waves": [16, 17, 18, 19, 20], "speed": 1.0, "once": True,
        "unlock": ["ch3_gauge", "ch3_ready"], "log": "story_log_upp3",
    },

    # Act 3 BONUS missions. The wreck of the hull that was lost (one version for each): a swarm around it, the parts
    # salvaged are worth `reward` credits, paid once with the first victory. The Singularity: Galaga waves, and the
    # Singularity Core falls once (`drop`), whenever in the waves; offered until it is caught in this Act.
    {
        "id": "bonus_wreck_phenix", "hull": "shield", "acts": (3,), "title": "story_m_wreckp",
        "hud_title": "story_m_wreckp_hud", "blurb": "story_m_wreckp_b", "need": "act3", "content": 1,
        "swarm": True, "swarm_screens": 1, "stage": 16, "speed": 1.0, "once": True, "reward": 5000,
        "unlock": [], "log": "story_log_wreckp",
    },
    {
        "id": "bonus_wreck_shield", "hull": "phoenix", "acts": (3,), "title": "story_m_wrecks",
        "hud_title": "story_m_wrecks_hud", "blurb": "story_m_wrecks_b", "need": "act3", "content": 1,
        "swarm": True, "swarm_screens": 1, "stage": 16, "speed": 1.0, "once": True, "reward": 5000,
        "unlock": [], "log": "story_log_wrecks",
    },
    {
        "id": "bonus_singularity", "acts": (3,), "title": "story_m_bsing", "hud_title": "story_m_bsing_hud",
        "blurb": "story_m_bsing_b", "need": "ch3_speed", "content": 1, "galaga": True, "stage": 21,
        "fire_mult": 1.2, "speed": 1.0, "drop": "singularity", "unlock": [], "log": "story_log_bsing",
    },

    # Act 3: the final series, "la Riposte", once the hull is at 100 % (ch3_ready): from Jupiter to Triton, where the
    # first station fell. Flown once each, in order; the last victory ends the Adventure (scene "epilogue").
    {
        "id": "ast_3", "acts": (3,), "asteroids": True, "title": "story_m_ast3", "hud_title": "story_m_ast_hud",
        "blurb": "story_m_ast_b", "need": "ch3_ready", "content": 1, "target": 100, "speed": 1.0,
        "unlock": ["ast_s3"], "log": "story_log_ast3",
    },
    {
        "id": "final_1", "acts": (3,), "title": "story_m_fin1", "blurb": "story_m_fin1_b", "need": "ast_s3",
        "content": 1, "waves": [21, 22], "speed": 1.0, "once": True, "unlock": ["final_s1"],
        "log": "story_log_fin1",
    },
    {
        "id": "final_2", "acts": (3,), "title": "story_m_fin2", "blurb": "story_m_fin2_b", "need": "final_s1",
        "content": 1, "swarm": True, "swarm_screens": 1.6, "stage": 21, "speed": 1.0, "once": True,
        "unlock": ["final_s2"], "log": "story_log_fin2",
    },
    {
        "id": "final_3", "acts": (3,), "title": "story_m_fin3", "blurb": "story_m_fin3_b", "need": "final_s2",
        "content": 1, "galaga": True, "stage": 21, "fire_mult": 1.3, "speed": 1.0, "once": True,
        "unlock": ["final_s3"], "log": "story_log_fin3",
    },
    {
        "id": "final_4", "acts": (3,), "title": "story_m_fin4", "blurb": "story_m_fin4_b", "need": "final_s3",
        "content": 1, "waves": [23, 24, 25], "speed": 1.0, "once": True, "unlock": ["final_s4"],
        "log": "story_log_fin4",
    },
    {
        "id": "final_5", "acts": (3,), "title": "story_m_fin5", "blurb": "story_m_fin5_b", "need": "final_s4",
        "content": 1, "waves": [26, 27, 28, 29, 30], "speed": 1.0, "once": True,
        "unlock": ["final_s5", GAME_WON], "epilogue": True, "log": "story_log_fin5",
    },
]


# ---------------------------------------------------------------- bestiary
# The enemies of the Adventure, in the order they are listed. `stage` is the content stage
# that spawns them. An entry shows up in the Bestiary once the pilot has destroyed one.
BESTIARY = [
    {"id": "bird1", "stage": 1, "name": "story_b_bird1", "text": "story_b_bird1_t"},
    {"id": "bird2", "stage": 2, "name": "story_b_bird2", "text": "story_b_bird2_t"},
    {"id": "garg3", "stage": 3, "name": "story_b_garg3", "text": "story_b_garg3_t"},
    {"id": "garg4", "stage": 4, "name": "story_b_garg4", "text": "story_b_garg4_t"},
    # the saucer that ends level 5 (and every fifth level): it shows up once the pilot has destroyed it
    {"id": "boss", "stage": 5, "name": "story_b_boss", "text": "story_b_boss_t", "boss": True},
]
# What each tier shows, by number of enemies of that kind destroyed:
# (picture, picture twice as big, animation, presentation text, bonus points).
BEST_TIERS_COMMON = (1, 50, 100, 150, 200)
BEST_TIERS_BOSS = (1, 2, 3, 5, 10)
BEST_SEEN = 1                          # first tier of both tables
BESTIARY_BONUS = ENEMY_VETERAN_BONUS   # common enemy: same bonus as Veteran difficulty
BOSS_BONUS = 1000                      # boss: extra points per boss destroyed


def enemy_kind(stage):
    """Bestiary id of an enemy spawned by content stage `stage`."""
    stage = int(_num(stage, 1))
    if stage >= 4:
        return "garg4"
    if stage == 3:
        return "garg3"
    return "bird2" if stage == 2 else "bird1"


def encounters(state, kind):
    """How many enemies of this kind the pilot has destroyed so far (saved total)."""
    data = state.get("bestiary")
    if not isinstance(data, dict):
        return 0
    return max(0, int(_num(data.get(kind), 0)))


def _entry(kind):
    return next((e for e in BESTIARY if e["id"] == kind), None)


def is_boss(kind):
    entry = _entry(kind)
    return bool(entry and entry.get("boss"))


def bestiary_bonus(kind):
    """Extra points per enemy of this kind once its last tier is reached."""
    return BOSS_BONUS if is_boss(kind) else BESTIARY_BONUS


def best_tiers(count, boss=False):
    """What an entry shows after `count` enemies destroyed (boss: the short table)."""
    count = int(_num(count, 0))
    seen, zoom, anim, text, bonus = BEST_TIERS_BOSS if boss else BEST_TIERS_COMMON
    return {
        "seen": count >= seen,
        "zoom": count >= zoom,
        "anim": count >= anim,
        "text": count >= text,
        "bonus": count >= bonus,
    }


def bestiary_entries(state):
    """The entries the pilot has unlocked, as (entry, count), in listing order."""
    out = []
    for entry in BESTIARY:
        n = encounters(state, entry["id"])
        if n >= BEST_SEEN:
            out.append((entry, n))
    return out


def kill_bonus(state, kind, run_kills):
    """Extra points for a kill once the last tier is reached (saved total + this run)."""
    entry = _entry(kind)
    if entry is None:
        return 0
    total = encounters(state, kind) + max(0, int(_num(run_kills, 0)))
    return bestiary_bonus(kind) if best_tiers(total, bool(entry.get("boss")))["bonus"] else 0


def record_kills(state, kills):
    """Add the enemies destroyed during a mission ({kind: n}) to the Bestiary."""
    if not isinstance(kills, dict):
        return
    data = state.get("bestiary")
    if not isinstance(data, dict):
        data = state["bestiary"] = {}
    known = {e["id"] for e in BESTIARY}
    for kind, n in kills.items():
        if kind in known:
            data[kind] = encounters(state, kind) + max(0, int(_num(n, 0)))


# ---------------------------------------------------------------- hunt missions
# The four Act 1 sorties that each face one kind of enemy ("hunt" missions) can be flown again
# as often as the pilot likes. The journal keeps the total of enemies destroyed in all their runs.
def mission_by_id(mission_id):
    return next((m for m in MISSIONS if m["id"] == mission_id), None)


def is_hunt(mission):
    return bool(mission and mission.get("hunt"))


def mission_total_kills(state, mission_id):
    """Enemies destroyed in every run of this mission so far (all outcomes)."""
    data = state.get("mission_kills")
    if not isinstance(data, dict):
        return 0
    return max(0, int(_num(data.get(mission_id), 0)))


def hunt_level(state, mission_id):
    """Level of a hunt mission: 1 at first, one more after each victory (1, 2, 3...).

    A save from before levels existed counts a cleared mission as won at least once.
    """
    data = state.get("mission_clears")
    won = max(0, int(_num(data.get(mission_id), 0))) if isinstance(data, dict) else 0
    if mission_id in (state.get("cleared") or []):
        won = max(won, 1)
    return 1 + won


def hunt_stage(mission, level):
    """Arcade stage a hunt mission plays at `level`: level 2 is the same wave as at stage +5 (x1.1 speed)."""
    return max(1, int(_num((mission or {}).get("content"), 1))) + 5 * (max(1, int(_num(level, 1))) - 1)


# ---------------------------------------------------------------- paint series
# Three optional missions of Act 2. The third one opens the paint shop for ONE change of colour of the
# Shield. The series can be flown again, as a whole only, to earn another change; each pass is harder.
PAINT_TINTS = ("red", "green", "violet")
PAINT_STEPS = 3
PAINT_COST = 500                 # a colour change is not free: credits spent when the Shield is painted


def paint_state(state):
    """The paint series of a save, cleaned: {"step": 0..2 missions won in this pass, "runs": passes
    finished, "token": a colour change is waiting}."""
    data = state.get("paint")
    if not isinstance(data, dict):
        data = {}
    return {
        "step": max(0, min(PAINT_STEPS - 1, int(_num(data.get("step"), 0)))),
        "runs": max(0, int(_num(data.get("runs"), 0))),
        "token": bool(data.get("token")),
    }


def is_paint(mission):
    return bool(mission and mission.get("paint"))


def paint_level(state):
    """The pass of the paint series: 1 at first, one more after each full pass (1, 2, 3...)."""
    return 1 + paint_state(state)["runs"]


def invader_level(state, mission):
    """Level of the Space Invaders grid of a paint mission: 1, 2, 3 in the first pass, 4, 5, 6 in the
    next one, and so on (three levels per pass)."""
    return PAINT_STEPS * paint_state(state)["runs"] + max(1, int(_num((mission or {}).get("paint"), 1)))


def mission_level(state, mission):
    """The level shown for a mission (hunts and the paint series), or None for the others."""
    if is_hunt(mission):
        return hunt_level(state, mission["id"])
    if is_paint(mission):
        return invader_level(state, mission)
    return None


def mission_done(state, mission):
    """Has the mission been won (for a paint mission: in the pass under way)?"""
    if is_paint(mission):
        return paint_state(state)["step"] >= int(mission["paint"])
    if (mission or {}).get("reactor"):
        return story_items.reactor_status(state, mission["reactor"]) is not None     # done = the reactor was caught
    if (mission or {}).get("drop"):
        return story_items.item_got(state, mission["drop"])          # done = its item was caught in this Act
    return bool(mission) and mission.get("id") in (state.get("cleared") or [])


# The colours of each hull: the Shield's three, and those of the Phenix (painted in Act 3 when it is the hull kept)
HULL_TINTS = {"shield": PAINT_TINTS, "phoenix": ("argent", "blue", "gold")}


def paint_target(state):
    """The hull the paint shop works on: the Shield (Act 2), or the hull kept in Act 3. None when there is none."""
    hull = kept_hull(state) or "shield"
    return next((sl for sl in state.get("slots") or [] if sl.get("id") == hull and sl.get("owned")), None)


def paint_tints(state):
    """The colours the paint shop offers (those of the hull it works on)."""
    sl = paint_target(state) or {}
    return HULL_TINTS.get(sl.get("id"), PAINT_TINTS)


def worn_tint(state):
    """The colour the hull of the paint shop wears."""
    sl = paint_target(state) or {}
    tints = HULL_TINTS.get(sl.get("id"), PAINT_TINTS)
    return sl.get("tint") if sl.get("tint") in tints else tints[0]


def paint_affordable(state):
    return int(_num(state.get("credits"), 0)) >= PAINT_COST


def paint_change(state, tint):
    """Spend the waiting colour change (and PAINT_COST credits) on the hull of the paint shop (the Shield, or the hull
    kept in Act 3). False when there is no change waiting, not enough credits, the colour is not one of that hull, or
    it is the colour it already wears (nothing is spent then)."""
    hull = paint_target(state)
    if hull is None or tint not in paint_tints(state) or not paint_state(state)["token"]:
        return False
    if worn_tint(state) == tint or not paint_affordable(state):
        return False
    state["credits"] = int(_num(state.get("credits"), 0)) - PAINT_COST
    hull["tint"] = tint
    state["paint"] = dict(paint_state(state), token=False)
    return True


def record_mission_kills(state, mission_id, kills):
    """Add the enemies destroyed during one run to the total of a hunt mission."""
    if not is_hunt(mission_by_id(mission_id)) or not isinstance(kills, dict):
        return
    known = {e["id"] for e in BESTIARY}
    added = sum(max(0, int(_num(n, 0))) for kind, n in kills.items() if kind in known)
    if added <= 0:
        return
    data = state.get("mission_kills")
    if not isinstance(data, dict):
        data = state["mission_kills"] = {}
    data[mission_id] = mission_total_kills(state, mission_id) + added


# ---------------------------------------------------------------- save data
def story_path(slot=1):
    return os.path.join(user_data_dir(), "story_%d.json" % int(slot))


def default_state():
    return {
        "version": SAVE_VERSION,
        "act": 1,
        "name": "",
        "mode": "normal",
        "fallen": False,
        "saved_at": "",
        "credits": 0,
        "flags": {"bestiary_s1": True},
        "cleared": [],
        "slots": [
            {
                "id": "shield", "owned": True, "tint": "red",
                "lives": 1, "lives_base": 1, "speed": SPEED_START, "dome": False,
                "dome_dur": DOME_DUR_START, "dome_cd": DOME_CD_START,
                "wall": "instant",
            },
            {
                "id": "phoenix", "owned": False, "tint": "argent",
                "lives": 1, "lives_base": 1, "speed": 60, "phenix": False,
                "phenix_cap": 60, "wall": "instant",
            },
        ],
        "selected_slot": 0,
        "log": [],
        "bestiary": {},          # enemies destroyed so far, by kind
        "mission_kills": {},     # enemies destroyed in all the runs of a hunt mission, by mission id
        "mission_clears": {},    # how many times a hunt mission was won (its level is one more)
        "paint": {"step": 0, "runs": 0, "token": False},   # the Act 2 paint series (see paint_state)
        "items": story_items.clean(None),   # the loot items of the current Act (see story_items.py)
        "vn": story_vn.clean(None),         # the answers of the visual novel (hidden points, see story_vn.py)
    }


def _num(value, default):
    """A number from a save file; a damaged value falls back to `default`."""
    try:
        if isinstance(value, bool):
            return default
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _clean_hull(slot, defaults):
    """Validate a migrated hull before menus or gameplay consume its fields."""
    out = dict(defaults)
    if slot.get("id") in HULLS:
        out["id"] = slot["id"]
    for key in ("owned", "dome", "phenix", "destroyed"):
        if isinstance(slot.get(key), bool):
            out[key] = slot[key]
    limits = {"lives": (1, 5), "lives_base": (1, NOVICE_LIVES), "speed": (SPEED_START, 100),
              "phenix_cap": (PHENIX_CAP_START, PHENIX_CAP_MAX),
              "dome_dur": (DOME_DUR_START, DOME_DUR_MAX), "dome_cd": (DOME_CD_MIN, DOME_CD_START)}
    for key, (low, high) in limits.items():
        if key in defaults or key in slot:
            value = max(low, min(high, _num(slot.get(key), defaults.get(key, low))))
            out[key] = value if key in ("dome_dur", "dome_cd") else int(value)
    out["tint"] = _hull_tint(out["id"], slot.get("tint", defaults.get("tint")))
    if slot.get("wall") in ("instant", "slow", "immune"):
        out["wall"] = slot["wall"]
    return out


def _to_act1_hangar(sl):
    """Version 3 -> 4 for one saved hull: the speed ladder moved down one step
    (60/80/100 became 40/60/80), lives stop at 2, the dome is not part of Act 1 and
    the "slow" wall (harmless) becomes the arcade rule."""
    speed = int(_num(sl.get("speed"), 60))
    if "speed" in sl:
        sl["speed"] = {60: 40, 80: 60, 100: 80}.get(speed, max(SPEED_START, min(80, speed)))
    if "lives" in sl:
        sl["lives"] = max(1, min(2, int(_num(sl.get("lives"), 1))))
    if sl.get("id") == "shield":
        sl["dome"] = False
        sl["dome_dur"] = DOME_DUR_START
        sl["dome_cd"] = DOME_CD_START
        if sl.get("wall") == "immune":
            sl["wall"] = "slow"


# The Asteroids prelude of each act and the first mission of the main series it opens (Dome I, Phenix I, la Riposte).
BELT_PRELUDES = (("ast_1", "dome_1"), ("ast_2", "phenix_1"), ("ast_3", "final_1"))


def _open_started_series(state):
    """A save made before the preludes existed: a series already started (its first mission won) does not wait for the
    belt, the prelude counts as won."""
    cleared = state.setdefault("cleared", [])
    flags = state.setdefault("flags", {})
    for prelude, first in BELT_PRELUDES:
        if first in cleared:
            for name in (mission_by_id(prelude) or {}).get("unlock") or []:
                flags[name] = True
            if prelude not in cleared:
                cleared.append(prelude)


def migrate_state(data):
    """Migrate older saves and validate fields for the current save version.

    Unknown or damaged fields fall back to the defaults. Returns None when
    `data` is not a dict at all.
    """
    if not isinstance(data, dict):
        return None
    base = default_state()
    old_version = int(_num(data.get("version"), 2))
    base["credits"] = max(0, int(_num(data.get("credits"), 0)))
    base["selected_slot"] = int(_num(data.get("selected_slot"), 0))
    # chapter (v2) became act (v3)
    base["act"] = max(1, min(3, int(_num(data.get("act", data.get("chapter")), 1))))
    if isinstance(data.get("name"), str):
        base["name"] = data["name"]
    if data.get("mode") in MODES:
        base["mode"] = data["mode"]
    if isinstance(data.get("fallen"), bool):
        base["fallen"] = data["fallen"]
    if isinstance(data.get("saved_at"), str):
        base["saved_at"] = data["saved_at"]
    flags = dict(base["flags"])
    if isinstance(data.get("flags"), dict):
        flags.update({k: v for k, v in data["flags"].items() if isinstance(k, str) and isinstance(v, bool)})
    base["flags"] = flags
    if isinstance(data.get("cleared"), list):
        base["cleared"] = [mid for mid in data["cleared"] if isinstance(mid, str)]
    if isinstance(data.get("log"), list):
        base["log"] = [entry for entry in data["log"] if isinstance(entry, str)
                       or (isinstance(entry, dict) and isinstance(entry.get("key"), str))]
    if isinstance(data.get("bestiary"), dict):
        record_kills(base, {k: v for k, v in data["bestiary"].items()})
    if isinstance(data.get("mission_clears"), dict):
        for mid, n in data["mission_clears"].items():
            if isinstance(mid, str) and is_hunt(mission_by_id(mid)):
                base["mission_clears"][mid] = max(0, int(_num(n, 0)))
    if isinstance(data.get("paint"), dict):
        base["paint"] = paint_state(data)
    if isinstance(data.get("items"), dict):
        base["items"] = story_items.clean(data["items"])
    if isinstance(data.get("vn"), dict):
        base["vn"] = story_vn.clean(data["vn"])
    if base["flags"].get(LEGACY_VERTICAL_FLAG):
        # a save made when the first BONUS mission gave the flight outright: the Shield keeps its reactor, installed
        base["items"] = story_items.clean(base["items"])
        base["items"]["got"].setdefault(story_items.REACTORS["shield"], story_items.INSTALLED)
    if isinstance(data.get("mission_kills"), dict):
        for mid, n in data["mission_kills"].items():
            if isinstance(mid, str) and is_hunt(mission_by_id(mid)):
                base["mission_kills"][mid] = max(0, int(_num(n, 0)))
    if isinstance(data.get("slots"), list) and data["slots"]:
        merged = []
        for i, sl in enumerate(data["slots"][:2]):
            proto = dict(base["slots"][i] if i < len(base["slots"]) else {})
            if isinstance(sl, dict):
                sl = dict(sl)
                if sl.get("id") not in HULLS:
                    sl["id"] = proto["id"]
                if old_version < 3:
                    # v2 stored the dome times in frames at 60 Hz
                    for key in ("dome_dur", "dome_cd"):
                        if key in sl:
                            sl[key] = _num(sl[key], 0.0) / 60.0
                if old_version < 4:
                    _to_act1_hangar(sl)
                proto = _clean_hull(sl, proto)
            merged.append(proto)
        base["slots"] = merged
    if not 0 <= base["selected_slot"] < len(base["slots"]):
        base["selected_slot"] = 0
    if data.get("act3_ship") in HULLS:
        base["act3_ship"] = data["act3_ship"]
    if old_version < 4:
        flags = base["flags"]
        if flags.pop("ch1_speed_80", False):
            flags["ch1_speed"] = True
        if flags.get("bestiary_s3"):
            flags["ch1_wall"] = True
        flags.pop("dome_online", None)
    _open_started_series(base)
    base["version"] = SAVE_VERSION
    return base


def read_state(path):
    """Read one slot file without touching it. Returns (state, status).

    status is "missing" (no file), "ok", or "damaged" (not readable; state is None).
    """
    if not os.path.isfile(path):
        return None, "missing"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        state = migrate_state(data)
    except Exception:
        return None, "damaged"
    if state is None:
        return None, "damaged"
    return state, "ok"


def load_state(path):
    """Read one slot. Returns a state, or None when missing or unreadable.

    An unreadable file is set aside (backup_unreadable) so it is never lost.
    """
    state, status = read_state(path)
    if status == "damaged":
        backup_unreadable(path)
    return state


def save_state(path, state):
    state["version"] = SAVE_VERSION
    state["saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    atomic_write_json(path, state)


# -------------------------------------------------------------- save slots
def format_date(saved_at):
    """'2026-10-08T11:21:05' -> '08/10/2026' ('' when unknown)."""
    try:
        y, m, d = str(saved_at)[:10].split("-")
        return "%02d/%02d/%04d" % (int(d), int(m), int(y))
    except (ValueError, TypeError):
        return ""


def slot_summary(slot):
    """What the slot list shows for slot 1..SLOT_COUNT."""
    state, status = read_state(story_path(slot))
    info = {"slot": slot, "status": status, "name": "", "mode": "normal",
            "act": 1, "date": "", "fallen": False}
    if state is not None:
        info.update(name=state.get("name") or "", mode=state.get("mode", "normal"),
                    act=int(_num(state.get("act"), 1)), date=format_date(state.get("saved_at")),
                    fallen=bool(state.get("fallen")))
    return info


def all_summaries():
    return [slot_summary(i) for i in range(1, SLOT_COUNT + 1)]


def clean_char(ch):
    """One typed character -> an allowed upper-case character, or ''."""
    if not ch:
        return ""
    ch = unicodedata.normalize("NFKD", ch)
    ch = "".join(c for c in ch if not unicodedata.combining(c)).upper()
    return ch if len(ch) == 1 and ch in NAME_CHARS else ""


def clean_name(raw):
    """A pilot name as stored: allowed characters only, single spaces, at most NAME_MAX."""
    chars = "".join(clean_char(c) for c in str(raw or ""))
    return " ".join(chars.split())[:NAME_MAX].strip()


def create_slot(slot, name, mode):
    """Start a new adventure in `slot` and save it. Returns the new state."""
    state = default_state()
    state["name"] = clean_name(name)
    state["mode"] = mode if mode in MODES else DEFAULT_MODE
    if state["mode"] == "novice":
        for sl in state["slots"]:
            sl["lives"] = sl["lives_base"] = NOVICE_LIVES      # three lives to begin with, a fourth to buy
    save_state(story_path(slot), state)
    return state


def delete_slot(slot):
    """Remove the save file of `slot`. True when a file was removed."""
    try:
        os.remove(story_path(slot))
        return True
    except OSError:
        return False


# Name entry: an on-screen keyboard, so the pad can do everything the keyboard does.
KEY_ROWS = [
    list("ABCDEFGHIJ"),
    list("KLMNOPQRST"),
    list("UVWXYZ0123"),
    ["4", "5", "6", "7", "8", "9", "-", "SPACE", "DEL", "OK"],
]


class NameEntry:
    """Pilot name being typed: text, plus a cursor on the on-screen keyboard."""

    def __init__(self, text=""):
        self.text = clean_name(text)
        self.row = 0
        self.col = 0

    @property
    def token(self):
        return KEY_ROWS[self.row][self.col]

    @property
    def name(self):
        return clean_name(self.text)

    def move(self, dx, dy):
        self.row = (self.row + dy) % len(KEY_ROWS)
        self.col = (self.col + dx) % len(KEY_ROWS[self.row])

    def type_char(self, ch):
        """A character typed on the real keyboard. True when it was accepted."""
        c = clean_char(ch)
        if not c or len(self.text) >= NAME_MAX:
            return False
        if c == " " and (not self.text or self.text.endswith(" ")):
            return False
        self.text += c
        return True

    def backspace(self):
        self.text = self.text[:-1]

    def press(self):
        """Validate the key under the cursor. Returns "ok" when the name is final,
        "empty" when OK was pressed with no name, else None."""
        tok = self.token
        if tok == "OK":
            return "ok" if self.name else "empty"
        if tok == "DEL":
            self.backspace()
        elif tok == "SPACE":
            self.type_char(" ")
        else:
            self.type_char(tok)
        return None


# ------------------------------------------------------------------ queries
def flag(state, name):
    return bool((state.get("flags") or {}).get(name))


# ------------------------------------------------------------------- intro
# The story told before the first mission: (picture in assets/story, text key).
# The first three slides are the same for everybody. The last one depends on the mode:
# in Veteran mode Professor Kamarasov died before finishing the quantum anchor.
INTRO_SLIDES = [
    ("huygens", "story_intro_1"),
    ("huygens_destroyed", "story_intro_2"),
    ("phobos", "story_intro_3"),
]
INTRO_LAST = {
    "normal": ("kamarasov", "story_intro_4"),
    "veteran": ("kamarasov_veteran", "story_intro_4v"),
}
INTRO_FLAG = "intro_seen"


# The Adventure intro is read aloud (French only): `assets/story/voice/<text key>.ogg`, and `marks.json` says when each line of
# the text is said (made by tools/make_intro_voice.py). The intro scrolls the text with it.
_VOICE_TABLE = {}


def _voice_table():
    if not _VOICE_TABLE:
        try:
            with open(asset_path("story", "voice", "marks.json"), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        _VOICE_TABLE["table"] = data if isinstance(data, dict) else {}
    return _VOICE_TABLE["table"]


def intro_voice(text_key, lang):
    """The recorded voice of a slide: {"path", "length", "marks": [(line index, start, end), ...]} (seconds, the lines are
    those of `intro_lines`), or None when there is no voice for this text or language, or the data is not usable."""
    if lang != "fr":
        return None
    entry = _voice_table().get(text_key)
    try:
        path = asset_path("story", "voice", str(entry["file"]))
        length = float(entry["length"])
        marks = [(int(m["line"]), float(m["start"]), float(m["end"])) for m in entry["marks"]]
    except (TypeError, KeyError, ValueError):
        return None
    if not os.path.isfile(path) or length <= 0.0 or not marks:
        return None
    last = (-1, -1.0)
    for line, start, end in marks:
        if line <= last[0] or start < last[1] or end <= start or end > length + 0.5:
            return None                                    # not in order: better no voice than a wrong scroll
        last = (line, end)
    return {"path": path, "length": length, "marks": marks}


def intro_slides(mode):
    """The slides to show for `mode`: a list of (picture name, text key)."""
    return INTRO_SLIDES + [INTRO_LAST.get(mode, INTRO_LAST["normal"])]


def intro_lines(translate, key, name):
    """Text of one slide as a list of lines ("" = a pause). {name} becomes the pilot's name."""
    text = str(translate(key)).replace("{name}", clean_name(name) or "?")
    return text.split("\n")


def intro_seen(state):
    return flag(state, INTRO_FLAG)


def mark_intro_seen(state):
    state.setdefault("flags", {})[INTRO_FLAG] = True


# A mission can come with a scene told the first time it is launched (same screen as the intro, with its own
# picture and text). It can be watched again from the journal. Keyed by mission id: the slides are
# [(picture in assets/story, text key)] and `title` is the journal line (after "watch again").
SCENES = {
    "ch1_sortie": {"title": "story_scene_sortie_t", "slides": [("oiseaux_bleus", "story_scene_sortie")]},
    "best_s2": {"title": "story_scene_best2_t", "slides": [("oiseaux_kaki", "story_scene_best2")]},
    "best_s3": {"title": "story_scene_best3_t", "slides": [("gargouilles", "story_scene_best3")]},
    "best_s4": {"title": "story_scene_best4_t", "slides": [("gargouilles_sombres", "story_scene_best4")]},
    "dome_1": {"title": "story_scene_dome_1_t", "slides": [("epave_shield", "story_scene_dome_1")]},
    "best_boss": {"title": "story_scene_bestboss_t", "slides": [("soucoupe_commandement", "story_scene_bestboss")]},
    "paint_1": {"title": "story_scene_paint_1_t", "slides": [("atelier_wallems", "story_scene_paint_1")]},
    # the prelude of each act: the road through the asteroid belt (the picture will come later: until then the slide is
    # a dark sky behind the text)
    "ast_1": {"title": "story_scene_ast1_t", "slides": [("ceinture_asteroides", "story_scene_ast1")]},
    "ast_2": {"title": "story_scene_ast2_t", "slides": [("ceinture_asteroides", "story_scene_ast2")]},
    # Act 3 (the pictures will come later: until then the slide is a dark sky behind the text)
    "up_shield_1": {"title": "story_scene_ups_t", "slides": [("remise_en_etat", "story_scene_ups")]},
    "up_phenix_1": {"title": "story_scene_upp_t", "slides": [("remise_en_etat", "story_scene_upp")]},
    "bonus_wreck_phenix": {"title": "story_scene_wreckp_t", "slides": [("epave_phenix", "story_scene_wreckp")]},
    "bonus_wreck_shield": {"title": "story_scene_wrecks_t", "slides": [("epave_nx01", "story_scene_wrecks")]},
    "ast_3": {"title": "story_scene_ast3_t", "slides": [("ceinture_asteroides", "story_scene_ast3")]},
    "final_1": {"title": "story_scene_fin_t", "slides": [("riposte", "story_scene_fin")]},
}

# The VIP rescue (Act 2 BONUS): its victory tells who was on board, and the concert of Lyra Voss in the Phobos bar opens.
VIP_SCENE = "vip_lyra"
LYRA_FLAG = "lyra_concert"

# The scenes of the story that belong to no mission: told after a mission (the attack on Phobos at the end of Act 2,
# the loss of the other hull once the choice is made, the end of the Adventure). `veteran`: the slides told instead in
# Veteran mode (no quantum anchor there, Kamarasov is dead). Keys are scene ids; the journal lists them once seen.
ACT3_ATTACK = "act3_attack"
EPILOGUE = "epilogue"
STORY_SCENES = {
    VIP_SCENE: {"title": "story_scene_vip_t", "slides": [("lyra_voss", "story_scene_vip")]},
    ACT3_ATTACK: {"title": "story_scene_attack_t",
                  "slides": [("phobos_attaque", "story_scene_attack_1"), ("ancrage_unique", "story_scene_attack_2")],
                  "veteran": [("phobos_attaque", "story_scene_attack_1"), ("ancrage_unique", "story_scene_attack_2v")]},
    "act3_kept_shield": {"title": "story_scene_lostp_t", "slides": [("perte_phenix", "story_scene_lostp")]},
    "act3_kept_phoenix": {"title": "story_scene_losts_t", "slides": [("perte_shield", "story_scene_losts")]},
    EPILOGUE: {"title": "story_scene_epilogue_t",
               "slides": [("epilogue_1", "story_scene_epilogue_1"), ("epilogue_2", "story_scene_epilogue_2")],
               "veteran": [("epilogue_1", "story_scene_epilogue_1"), ("epilogue_2", "story_scene_epilogue_2v")]},
}
# The order of the journal (the order of the story): the mission scenes of Acts 1 and 2, the attack, the loss, the
# Act 3 scenes, the end; the Phobos bar (Add-On) last.
SCENE_ORDER = (["ch1_sortie", "best_s2", "best_s3", "best_s4", "ast_1", "dome_1", "best_boss", "ast_2", "paint_1",
                VIP_SCENE, ACT3_ATTACK, "act3_kept_shield", "act3_kept_phoenix", "up_shield_1", "up_phenix_1",
                "bonus_wreck_phenix", "bonus_wreck_shield", "ast_3", "final_1", EPILOGUE])


# The films: videos watched full screen with their sound (assets/video/<video>.mp4, silent, and <video>.ogg, its
# sound; the jukebox intro is made the same way). A film comes right after a scene or another film (`after`) the first
# time, then the journal keeps a line to watch it again. Keys are film ids, in the order of the journal.
# Lyra Voss's private concert, after the VIP rescue: three songs in a row.
FILMS = {
    "lyra_1": {"title": "story_film_lyra1_t", "video": "lyra_1_eternal_dawn", "after": VIP_SCENE},
    "lyra_2": {"title": "story_film_lyra2_t", "video": "lyra_2_what_we_lost", "after": "lyra_1"},
    "lyra_3": {"title": "story_film_lyra3_t", "video": "lyra_3_no_mercy_left", "after": "lyra_2"},
    # the visual novel begins right after the concert: the film of the bar (no title over it), then the scene vn_1
    # (story_vn.VN_SCENES). Without its files the scene comes straight away.
    "vn_1": {"title": "story_film_vn1_t", "video": "vn_1_bar", "after": "lyra_3", "quiet": True, "vn": "vn_1"},
}


def film_files(film_id):
    """(picture, sound) paths of a film, or None when one of them is missing."""
    film = FILMS.get(film_id)
    if not film:
        return None
    video = asset_path("video", film["video"] + ".mp4")
    sound = asset_path("video", film["video"] + ".ogg")
    if not (os.path.isfile(video) and os.path.isfile(sound)):
        return None
    return video, sound


def film_after(scene_id):
    """The film told right after this scene (or this film), or None."""
    return next((fid for fid, film in FILMS.items() if film.get("after") == scene_id), None)


def film_chain(start):
    """The films that follow a scene (or a film) one after the other: [film id, ...]."""
    out = []
    fid = film_after(start)
    while fid and fid not in out:
        out.append(fid)
        fid = film_after(fid)
    return out


def film_flag(film_id):
    return "film_" + str(film_id)


def story_wins(state):
    """How many story missions (the series and the asteroid belts: no hunt, bonus or paint) are won. A mission replayed
    does not count twice."""
    cleared = set((state or {}).get("cleared") or [])
    return sum(1 for m in MISSIONS if m["id"] in cleared and mission_group(m) == GROUP_STORY)


def vn_due(state):
    """The visual novel scene to tell now, or None. The scenes come one after the other: only the first one not
    answered can be due. One with a film follows the film before it (the concert), one without comes once enough
    story missions are won since the answer to the scene it follows."""
    sid = story_vn.next_scene(state)
    if sid is None:
        return None
    scene = story_vn.scene(sid)
    if scene.get("film"):
        prev = (FILMS.get(scene["film"]) or {}).get("after")
        return sid if (not prev or film_seen(state, prev)) else None
    base = story_vn.mark(state, scene.get("after"))
    if base is None:
        return None
    return sid if story_wins(state) - base >= int(scene.get("wins") or 1) else None


def film_seen(state, film_id):
    return flag(state, film_flag(film_id))


def mark_film_seen(state, film_id):
    state.setdefault("flags", {})[film_flag(film_id)] = True


# The scene of the Phobos station bar belongs to no mission: it is told the first time the Add-On is available (the
# MAME games found, see addon.addon_ready), then it stays in the journal like the others. At its end the player goes
# straight to the Add-On menu (`door`), and the Elise theme (`music`) is played softly under the text. Keys are scene ids.
BAR_SCENE = "bar_phobos"
ADDON_SCENES = {
    BAR_SCENE: {"title": "story_scene_bar_t", "slides": [("bar_phobos", "story_scene_bar")],
                "door": "addon", "music": "nostalgie_elise"},
}
BAR_MUSIC_LEVEL = 0.34         # share of the normal music volume while the scene is read over it


# A slide picture can be a video clip instead of a still: `assets/story/<name>.mp4` (made by tools/encode_clip.py,
# no sound, 24 fps, a loop without a seam) plays behind the text. The still `<name>.jpg` stays as the poster, shown
# while the clip starts and whenever it cannot play (no ffmpeg, damaged file).
def clip_path(name):
    """Full path of the clip of a slide picture, or None when the picture is a plain still."""
    path = asset_path("story", str(name) + ".mp4")
    return path if os.path.isfile(path) else None


def scene_of(mission_id):
    return SCENES.get(mission_id) or STORY_SCENES.get(mission_id) or ADDON_SCENES.get(mission_id)


def scene_slides(scene_id, mode="normal"):
    """The slides of a scene for a save of `mode`: [(picture, text key)] (the Veteran ones when it has them)."""
    scene = scene_of(scene_id) or {}
    if mode == "veteran" and scene.get("veteran"):
        return list(scene["veteran"])
    return list(scene.get("slides") or [])


def loss_scene(hull):
    """The scene told once `hull` is chosen: the loss of the other one."""
    return "act3_kept_" + hull


def bar_due(state, addon_ready):
    """True when the Phobos bar scene has to be told now: the Add-On is available and this save has not seen it."""
    return bool(addon_ready) and not scene_seen(state, BAR_SCENE)


def scene_flag(mission_id):
    return "scene_" + str(mission_id)


def scene_seen(state, mission_id):
    return flag(state, scene_flag(mission_id))


def mark_scene_seen(state, mission_id):
    state.setdefault("flags", {})[scene_flag(mission_id)] = True


def scenes_seen(state):
    """Ids of the scenes already watched, in the order of the story (SCENE_ORDER), then the Add-On ones."""
    order = SCENE_ORDER + [m for m in SCENES if m not in SCENE_ORDER] + list(ADDON_SCENES)
    return [mid for mid in order if scene_seen(state, mid)]


PHENIX_CAP_START = 60
PHENIX_CAP_MAX = 100


def phenix_cap(slot):
    """Share (%) of the arcade Phenix form the pilot gets: 60 at first, 80 after the workshop, 100 in Act 3."""
    return max(PHENIX_CAP_START, min(PHENIX_CAP_MAX, int(_num((slot or {}).get("phenix_cap"), PHENIX_CAP_START))))


def selected_slot(state):
    slots = state.get("slots") or []
    i = int(state.get("selected_slot", 0))
    if 0 <= i < len(slots):
        return slots[i]
    return None


def _hull_tint(sid, tint):
    """Colour a hull flies with: the Shield wears red / green / violet, the Phenix argent."""
    if sid == "shield":
        return tint if tint in PAINT_TINTS else "red"
    return tint if tint in ("argent", "blue", "gold") else "argent"


def loadout(state, force_ship=None):
    """Hull the mission actually launches: the selected one, unless the mission imposes a hull
    (`force_ship`) the pilot owns. A hull not owned yet falls back to the first one owned."""
    slot = selected_slot(state) or {}
    if force_ship:
        forced = next((sl for sl in state.get("slots") or [] if sl.get("id") == force_ship and sl.get("owned")), None)
        if forced is not None:
            slot = forced
    if not slot.get("owned"):
        slots = state.get("slots") or []
        slot = next((s for s in slots if s.get("owned")), slot)
    sid = slot.get("id") if slot.get("id") in ("shield", "phoenix") else "shield"
    fallback_speed = SPEED_START if sid == "shield" else 60
    return {
        "ship_id": sid,
        "tint": _hull_tint(sid, slot.get("tint")),
        "lives": max(1, int(_num(slot.get("lives"), 1) or 1)),
        "speed_pct": max(SPEED_START, min(100, int(_num(slot.get("speed"), fallback_speed) or fallback_speed))),
        "dome": bool(slot.get("dome")),
        "dome_dur": _num(slot.get("dome_dur"), DOME_DUR_START) or DOME_DUR_START,
        "dome_cd": _num(slot.get("dome_cd"), DOME_CD_START) or DOME_CD_START,
        "wall": slot.get("wall") or "instant",
        "phenix_pct": phenix_cap(slot),
        "vertical": story_items.reactor_on(state, sid),         # the reactor of the hull flown, installed
    }


def jump_to_act2(state):
    """The ACT2 cheat: the save of a pilot who has just finished Act 1 (every Act 1 mission won)."""
    flags = state.setdefault("flags", {})
    cleared = state.setdefault("cleared", [])
    for mission in MISSIONS:
        if mission_in_act(mission, 1) and mission.get("playable") is not False:
            for name in mission.get("unlock") or []:
                flags[name] = True
            if mission["id"] not in cleared:
                cleared.append(mission["id"])
    flags["act2"] = True
    state["act"] = 2


def grant_phenix(state):
    """The NIX2 cheat: Act 2 is on, the belt and the five Phenix missions count as won and the Phenix is in the hangar."""
    if int(_num(state.get("act"), 1)) < 2:
        jump_to_act2(state)
    flags = state.setdefault("flags", {})
    cleared = state.setdefault("cleared", [])
    for mission in MISSIONS:
        if not (str(mission.get("id", "")).startswith("phenix_") or mission.get("id") == "ast_2"):
            continue
        for name in mission.get("unlock") or []:
            flags[name] = True
        if mission["id"] not in cleared:
            cleared.append(mission["id"])
        if mission.get("grant_hull"):
            for sl in state.get("slots") or []:
                if sl.get("id") == mission["grant_hull"]:
                    sl["owned"] = True


def act3_pending(state):
    """Act 2 is won and the hull that keeps the anchor is still to be chosen."""
    return flag(state, ACT3_PENDING) and int(_num((state or {}).get("act"), 1)) < 3


def choose_act3_ship(state, hull):
    """The attack on Phobos: `hull` keeps the quantum anchor and flies Act 3; the other one is destroyed (its slot is
    kept, marked `destroyed`, so the hangar can show the loss). False when there is no choice to make."""
    if hull not in HULLS or not act3_pending(state):
        return False
    for sl in state.get("slots") or []:
        if sl.get("id") == hull:
            sl["owned"] = True
        else:
            sl["owned"] = False
            sl["destroyed"] = True
    slots = state.get("slots") or []
    state["selected_slot"] = next((i for i, sl in enumerate(slots) if sl.get("id") == hull), 0)
    state["act3_ship"] = hull
    state["act"] = 3
    flags = state.setdefault("flags", {})
    flags.pop(ACT3_PENDING, None)
    flags["act3"] = True
    lost = "phoenix" if hull == "shield" else "shield"
    state.setdefault("log", []).append({"key": "story_log_lost_" + lost})
    return True


def jump_to_act3(state):
    """The 3333 cheat: Acts 1 and 2 won, the Phenix in the hangar, the attack on Phobos about to be told."""
    grant_phenix(state)
    flags = state.setdefault("flags", {})
    cleared = state.setdefault("cleared", [])
    for mission in MISSIONS:
        if mission_in_act(mission, 2) and mission.get("once") and mission["id"] not in cleared:
            cleared.append(mission["id"])
    flags[ACT3_PENDING] = True


def mission_waves(mission):
    """Arcade stage numbers a mission flies one after the other (empty: one wave of `content`)."""
    waves = (mission or {}).get("waves")
    if not isinstance(waves, (list, tuple)):
        return []
    return [max(1, int(_num(w, 1))) for w in waves]


def mission_in_act(mission, act):
    """Is this mission on the map of act `act`? Missions without `acts` (the hunts) are on every map."""
    acts = (mission or {}).get("acts")
    return not acts or int(_num(act, 1)) in acts


# The map groups its missions. A hunt is a Bestiary mission (replayable); an "extra" is a BONUS or the optional
# paint series; the rest is the story (the Asteroids prelude of each act among them). Act 1 lists the hunts first (they bring the speed, the life and the walls the
# Dome series needs), the later acts list the story first.
GROUP_STORY, GROUP_HUNT, GROUP_EXTRA = "story", "hunt", "extra"
GROUP_ORDER = {1: (GROUP_HUNT, GROUP_STORY, GROUP_EXTRA), 2: (GROUP_STORY, GROUP_HUNT, GROUP_EXTRA),
               3: (GROUP_STORY, GROUP_HUNT, GROUP_EXTRA)}


def mission_group(mission):
    """"hunt", "extra" or "story": the section of the map a mission belongs to."""
    m = mission or {}
    if m.get("hunt"):
        return GROUP_HUNT
    if (m.get("reactor") or m.get("drop") or m.get("needs_reactor") or m.get("reward")
            or m.get("paint") or m.get("carry")):
        return GROUP_EXTRA
    return GROUP_STORY


def visible_missions(state, cheat=False):
    """The missions the map lists, grouped (see GROUP_ORDER): those of the current act. The UNLK cheat lists every
    mission, in the order of the table."""
    if cheat:
        return list(MISSIONS)
    act = int(_num(state.get("act"), 1))
    shown = [m for m in MISSIONS if _listed(state, m, act)]
    order = GROUP_ORDER.get(min(max(act, 1), 3), GROUP_ORDER[3])
    shown.sort(key=lambda m: order.index(mission_group(m)))            # (stable: the table order inside a group)
    return shown


def unlock_source(state, flag_name, act=None):
    """The mission whose victory raises the story flag `flag_name` (the one the map and the workshop name as "after
    ..."), or None. When two hulls have their own version of it, the one the pilot can fly."""
    if not flag_name:
        return None
    act = int(_num(state.get("act"), 1)) if act is None else act
    found = [m for m in MISSIONS if flag_name in (m.get("unlock") or []) and hull_fits(state, m)]
    found.sort(key=lambda m: 0 if mission_in_act(m, act) else 1)
    return found[0] if found else None


def unlock_hint(state, mission):
    """The mission to win before this one opens (what the map says on a locked row), or None."""
    if not mission or mission_open(state, mission):
        return None
    if is_paint(mission):
        prev = int(mission["paint"]) - 1
        return next((m for m in MISSIONS if m.get("paint") == prev), None) if prev >= 1 else None
    return unlock_source(state, mission.get("need"))


FIRST_SORTIE = "ch1_sortie"
FIRST_HELP_SECONDS = 5.0            # how long the controls reminder stays on screen in the very first sortie


def first_sortie(state, mission_id):
    """True for the first sortie of a pilot who has not won a mission yet: the controls reminder is shown there."""
    return mission_id == FIRST_SORTIE and not (state or {}).get("cleared")


def next_mission(state, missions):
    """The mission the map suggests: the first one of the list that can be flown and is not won yet. None when there is
    none."""
    for m in missions:
        if not mission_playable(state, m):
            continue
        if not mission_done(state, m):
            return m
    return None


def _listed(state, mission, act):
    """Is this mission on the map of act `act`? A secret mission waits until it is open. A mission that `carry`s over
    (the BONUS ones) is on the map of every act, but once its reactor is caught it only stays on the map of the act
    it belongs to (`home`): the later acts list it only while it is still to do."""
    if not mission_in_act(mission, act):
        return False
    if not hull_fits(state, mission):
        return False
    if mission.get("secret") and not mission_open(state, mission):
        return False
    if mission.get("carry") and act > int(_num(mission.get("home"), 1)) and mission_done(state, mission):
        return False
    return True


def kept_hull(state):
    """The hull chosen to keep the quantum anchor at the end of Act 2 ("shield" / "phoenix"), or None before."""
    hull = (state or {}).get("act3_ship")
    return hull if hull in HULLS else None


def hull_lost(state, hull):
    """Was this hull destroyed in the attack on Phobos?"""
    sl = next((s for s in (state or {}).get("slots") or [] if s.get("id") == hull), None)
    return bool(sl and sl.get("destroyed"))


def hull_fits(state, mission):
    """A mission made for one hull (`hull`: the Act 3 versions) is there only when it is the one kept; a mission that
    imposes a hull (`ship`: the BONUS reactors) goes away when that hull is lost."""
    want = (mission or {}).get("hull")
    if want and kept_hull(state) != want:
        return False
    ship = (mission or {}).get("ship")
    if ship and hull_lost(state, ship):
        return False
    return True


def reactor_hulls(state):
    """The hulls of the hangar that fly with their two-dimensional reactor installed (owned, not destroyed)."""
    out = []
    for sl in (state or {}).get("slots") or []:
        hull = sl.get("id")
        if hull in HULLS and sl.get("owned") and not sl.get("destroyed") and story_items.reactor_on(state, hull):
            out.append(hull)
    return out


def reactor_hull(state):
    """The hull a mission that `needs_reactor` flies: the selected one if it has its reactor, else the other one
    that has it; None when no hull has one."""
    hulls = reactor_hulls(state)
    if not hulls:
        return None
    sel = (selected_slot(state) or {}).get("id")
    return sel if sel in hulls else hulls[0]


def mission_open(state, mission):
    if not mission:
        return False
    need = mission.get("need")
    if need and not flag(state, need):
        return False
    if mission.get("needs_reactor") and not reactor_hulls(state):
        return False                       # the VIP rescue: a hull with its two-dimensional reactor installed
    if is_paint(mission) and paint_state(state)["step"] < int(mission["paint"]) - 1:
        return False                       # the paint series is flown in order
    return True


def mission_playable(state, mission, cheat=False):
    """Can this mission be launched? `cheat` (the UNLK code) skips every unlock rule."""
    if not mission:
        return False
    if mission.get("playable") is False or int(mission.get("content") or 0) <= 0:
        return False
    if cheat:
        return True
    if not mission_open(state, mission) or not hull_fits(state, mission):
        return False
    if mission.get("drop") and mission_done(state, mission):
        return False                       # the item it drops is caught: a drop mission is offered until then
    if mission.get("once") and mission.get("id") in (state.get("cleared") or []):
        return False                       # a story mission is flown once; hunts stay replayable
    if mission.get("reactor") and mission_done(state, mission):
        return False                       # the reactor is caught: a BONUS mission is offered until then
    if is_paint(mission) and paint_state(state)["step"] != int(mission["paint"]) - 1:
        return False                       # only the next mission of the pass; a won one waits for the next pass
    return True


# ---------------------------------------------------------------- workshop
_NO_MIN = float("-inf")


def _step_to(slot, field, default, minimum, target):
    """Set `field` to `target` if it is currently in [minimum, target)."""
    cur = int(_num(slot.get(field), default))
    if cur < minimum or cur >= target:
        return False
    slot[field] = target
    return True


def _up_speed_60(slot):
    return _step_to(slot, "speed", SPEED_START, _NO_MIN, 60)


def _up_speed_80(slot):
    return _step_to(slot, "speed", SPEED_START, 60, 80)


def _up_speed_100(slot):
    return _step_to(slot, "speed", SPEED_START, 80, 100)


def lives_base(slot):
    """Lives the hull started with: 1 (3 in Novice mode). The workshop adds one, then one more in Act 3."""
    return max(1, int(_num((slot or {}).get("lives_base"), 1)))


def _up_lives_2(slot):
    base = lives_base(slot)
    return _step_to(slot, "lives", base, _NO_MIN, base + 1)


def _up_lives_3(slot):
    base = lives_base(slot)
    return _step_to(slot, "lives", base, base + 1, base + 2)


def _up_dome_dur(slot):
    if not slot.get("dome"):
        slot["dome"] = True
        slot["dome_dur"] = DOME_DUR_START
        slot["dome_cd"] = _num(slot.get("dome_cd"), DOME_CD_START) or DOME_CD_START
        return True
    dur = _num(slot.get("dome_dur"), DOME_DUR_START) or DOME_DUR_START
    if dur >= DOME_DUR_MAX - _EPS:
        return False
    slot["dome_dur"] = min(DOME_DUR_MAX, dur + DOME_DUR_STEP)
    return True


def _up_dome_on(slot):
    """The first dome upgrade: the Shield gets its dome (1 s, the shortest one)."""
    if slot.get("dome") or slot.get("id") == "phoenix":
        return False                          # the dome is the Shield's
    slot["dome"] = True
    slot["dome_dur"] = DOME_DUR_START
    slot["dome_cd"] = _num(slot.get("dome_cd"), DOME_CD_START) or DOME_CD_START
    return True


def _up_dome_lat(slot):
    if not slot.get("dome"):
        return False
    cd = _num(slot.get("dome_cd"), DOME_CD_START) or DOME_CD_START
    if cd <= DOME_CD_MIN + _EPS:
        return False
    slot["dome_cd"] = max(DOME_CD_MIN, cd - DOME_CD_STEP)
    return True


def _up_wall_slow(slot):
    """Walls: touching the edge kills at once -> the arcade rule (slowdown, then death)."""
    if slot.get("wall") != "instant":
        return False
    slot["wall"] = "slow"
    return True


def _up_wall_immune(slot):
    if slot.get("wall") != "slow":
        return False
    slot["wall"] = "immune"
    return True


def _up_cap_80(slot):
    """Phenix only: the Phenix form lasts 80 % of the arcade one (60 % at first)."""
    if slot.get("id") != "phoenix" or phenix_cap(slot) >= 80:
        return False
    slot["phenix_cap"] = 80
    return True


def _st_cap_80(slot):
    return "owned" if phenix_cap(slot) >= 80 else None


def _up_cap_100(slot):
    """Phenix only, Act 3: the Phenix form lasts as long as in the arcade."""
    if slot.get("id") != "phoenix" or phenix_cap(slot) < 80 or phenix_cap(slot) >= 100:
        return False
    slot["phenix_cap"] = 100
    return True


def _st_cap_100(slot):
    if phenix_cap(slot) >= 100:
        return "owned"
    return "need_prev" if phenix_cap(slot) < 80 else None


def _speed(slot):
    return int(_num(slot.get("speed"), SPEED_START))


def _lives(slot):
    return int(_num(slot.get("lives"), 1))


def _st_speed_60(slot):
    return "owned" if _speed(slot) >= 60 else None


def _st_speed_80(slot):
    if _speed(slot) >= 80:
        return "owned"
    if _speed(slot) < 60:
        return "need_prev"
    return None


def _st_speed_100(slot):
    if _speed(slot) >= 100:
        return "owned"
    if _speed(slot) < 80:
        return "need_prev"
    return None


def _st_lives_2(slot):
    return "owned" if _lives(slot) >= lives_base(slot) + 1 else None


def _st_lives_3(slot):
    if _lives(slot) >= lives_base(slot) + 2:
        return "owned"
    if _lives(slot) < lives_base(slot) + 1:
        return "need_prev"
    return None


def _st_dome_on(slot):
    return "owned" if slot.get("dome") else None


def _st_dome_dur(slot):
    if slot.get("dome") and (_num(slot.get("dome_dur"), 0.0) or 0.0) >= DOME_DUR_MAX - _EPS:
        return "owned"
    return None


def _st_dome_lat(slot):
    if not slot.get("dome"):
        return "need_dome"
    cd = _num(slot.get("dome_cd"), DOME_CD_START) or DOME_CD_START
    if cd <= DOME_CD_MIN + _EPS:
        return "owned"
    return None


def _st_wall_slow(slot):
    return "owned" if slot.get("wall") in ("slow", "immune") else None


def _st_wall_immune(slot):
    if slot.get("wall") == "immune":
        return "owned"
    if slot.get("wall") != "slow":
        return "need_prev"
    return None


# The dome lasts longer in two steps (1 s -> 1.5 s -> 2 s), the second one costs more than the first
DOME_DUR_PRICES = (2000, 3000)

# id, i18n label, cost, flag required, apply(slot) -> bool, status(slot) -> str|None, act
# `act` is the act whose workshop sells it. Only Act 1 is built so far: the dome comes with
# its own series of quests (nothing sets "dome_online" yet), the rest is for Acts 2 and 3.
UPGRADES = [
    ("speed_60", "story_shop_speed60", 300, "ch1_speed", _up_speed_60, _st_speed_60, 1),
    ("speed_80", "story_shop_speed80", 800, "ch1_speed", _up_speed_80, _st_speed_80, 1),
    ("lives_2", "story_shop_lives2", 2000, "ch1_life_2", _up_lives_2, _st_lives_2, 1),
    ("wall_slow", "story_shop_wall_slow", 1000, "ch1_wall", _up_wall_slow, _st_wall_slow, 1),
    ("dome_on", "story_shop_dome_on", 800, "dome_online", _up_dome_on, _st_dome_on, 1),
    ("phenix_cap_80", "story_shop_phenix80", 3000, "phenix_owned", _up_cap_80, _st_cap_80, 2),
    ("speed_100", "story_shop_speed100", 4000, "ch3_speed", _up_speed_100, _st_speed_100, 3),
    ("lives_3", "story_shop_lives3", 5000, "ch3_lives", _up_lives_3, _st_lives_3, 3),
    ("dome_dur", "story_shop_dome", DOME_DUR_PRICES[0], "ch3_dome", _up_dome_dur, _st_dome_dur, 3),
    ("dome_lat", "story_shop_latency", 800, "dome_online", _up_dome_lat, _st_dome_lat, 2),
    ("wall_immune", "story_shop_wall_immune", 4000, "ch3_wall", _up_wall_immune, _st_wall_immune, 3),
    ("phenix_cap_100", "story_shop_phenix100", 5000, "ch3_gauge", _up_cap_100, _st_cap_100, 3),
]

# The prices above are the Shield's. The Phenix, whose workshop opens in Act 2 when the credits are already higher, pays more
# for the steps it shares with the Shield; the Phenix-only rows (the gauge) have their own price in the table.
PHENIX_PRICES = {"speed_80": 2000, "wall_slow": 3000, "lives_2": 4000}


def upgrade_cost(slot, sid):
    """Credits the workshop asks for the row `sid` of the hull `slot` (the table price, or the price of that hull / step)."""
    up = _upgrade(sid)
    if up is None:
        return 0
    if sid == "dome_dur":
        dur = _num((slot or {}).get("dome_dur"), DOME_DUR_START) or DOME_DUR_START
        step = int((dur - DOME_DUR_START) / DOME_DUR_STEP + 0.5) if (slot or {}).get("dome") else 0
        return DOME_DUR_PRICES[max(0, min(step, len(DOME_DUR_PRICES) - 1))]
    if (slot or {}).get("id") == "phoenix" and sid in PHENIX_PRICES:
        return PHENIX_PRICES[sid]
    return up[2]


# What the workshop shows in Act 1: id, i18n label, cost, flag required before it is buyable
SHOP = [(u[0], u[1], u[2], u[3]) for u in UPGRADES if u[6] == 1]


# What the workshop sells for the Phenix (Act 2): the same hull upgrades, no dome, plus its own gauge.
PAINT_ROW = ("paint", "story_shop_paint", PAINT_COST, None)
PHENIX_SHOP_IDS = ("speed_80", "lives_2", "wall_slow", "phenix_cap_80")
# Act 3: what brings the hull kept to the arcade ship (each line opens with its repair mission). The Shield of the
# arcade is immune to the walls and its dome lasts 2 s; the Phenix of the arcade keeps the slowdown rule of the walls
# and its whole Phenix form.
ACT3_SHOP_IDS = {"shield": ("speed_100", "lives_3", "wall_immune", "dome_dur"),
                 "phoenix": ("speed_100", "lives_3", "phenix_cap_100")}


# The workshop sells "Vies 2" (and "Vies 3" in Act 3): the number is the lives you end up with, so a Novice (who starts with 3)
# reads "Vies 4" (then "Vies 5")
NOVICE_LABELS = {"story_shop_lives2": "story_shop_lives4", "story_shop_lives3": "story_shop_lives5"}


def shop_for(state):
    """Workshop rows of the selected hull: (id, label, cost, flag required)."""
    slot = selected_slot(state) or {}
    hull = "phoenix" if slot.get("id") == "phoenix" else "shield"
    act = int(_num(state.get("act"), 1))
    ids = PHENIX_SHOP_IDS if hull == "phoenix" else [u[0] for u in SHOP]
    if act >= 3:
        ids = list(ids) + list(ACT3_SHOP_IDS[hull])
    rows = [(u[0], u[1], upgrade_cost(slot, u[0]), u[3]) for sid in ids for u in UPGRADES if u[0] == sid]
    target = paint_target(state)
    if act >= 2 and target is not None and target.get("id") == slot.get("id"):
        rows.append(PAINT_ROW)                 # the paint shop: PAINT_COST credits, and one change per finished series
    if state.get("mode") == "novice":
        rows = [(sid, NOVICE_LABELS.get(label, label), cost, need) for sid, label, cost, need in rows]
    # the loot items caught (a reactor only for the hull flown)
    rows = rows + [item_row(i) for i in story_items.shop(state, slot.get("id"))]
    # what is already at MAX goes last: the rows still to buy stay under the cursor, the finished ones are a footnote
    todo = [r for r in rows if upgrade_note(state, r[0]) != "story_owned"]
    return todo + [r for r in rows if upgrade_note(state, r[0]) == "story_owned"]


def shop_after(state, sid):
    """The mission to win before the workshop row `sid` can be bought (it is what its story flag waits for), or None
    when the row is open or does not wait for a mission."""
    up = _upgrade(sid)
    if up is None or not up[3] or flag(state, up[3]):
        return None
    return unlock_source(state, up[3])


ITEM_PREFIX = "item:"


def item_row(item):
    """Workshop row of a loot item: ("item:<id>", name key, price, no flag)."""
    return (ITEM_PREFIX + item, "item_%s_name" % item, story_items.PRICES[item], None)


def item_of(sid):
    """The loot item a workshop row id stands for, or None."""
    if isinstance(sid, str) and sid.startswith(ITEM_PREFIX) and sid[len(ITEM_PREFIX):] in story_items.ITEM_IDS:
        return sid[len(ITEM_PREFIX):]
    return None


def act_caps(state):
    """Highest speed and lives the workshop of the current act allows."""
    caps = dict(ACT_CAPS.get(int(_num(state.get("act"), 1)), ACT_CAPS[1]))
    if state.get("mode") == "novice":
        caps["lives"] += NOVICE_LIVES - 1                  # the workshop reaches one more life than the cap, like in Normal
    return caps

_STATUS_KEYS = {
    "owned": "story_owned",
    "need_prev": "story_need_prev",
    "need_dome": "story_need_dome",
}


def _upgrade(sid):
    return next((u for u in UPGRADES if u[0] == sid), None)


def upgrade_note(state, sid):
    """i18n key shown on a workshop row instead of its price, or None.

    "story_locked" when the story flag is missing, "story_owned" when already
    bought, "story_need_prev" / "story_need_dome" when a step is missing.
    """
    item = item_of(sid)
    if item is not None:
        return "story_item_installed" if story_items.status(state, item) == story_items.INSTALLED else None
    up = _upgrade(sid)
    if up is None:
        return None
    if up[3] and not flag(state, up[3]):
        return "story_locked"
    slot = selected_slot(state) or {}
    return _STATUS_KEYS.get(up[5](slot))


def buy(state, sid):
    """Buy one upgrade for the selected hull. True when it was bought."""
    item = item_of(sid)
    if item is not None:
        hull = (selected_slot(state) or {}).get("id")
        if item in story_items.REACTOR_IDS and story_items.REACTORS.get(hull) != item:
            return False                              # a reactor fits its own hull only
        return story_items.buy(state, item)           # a loot item: for the next mission (a reactor: for good)
    up = _upgrade(sid)
    if up is None:
        return False
    if up[3] and not flag(state, up[3]):
        return False
    slot = selected_slot(state)
    if slot is None or not slot.get("owned"):
        return False
    cost = upgrade_cost(slot, sid)                     # before the purchase: the step it buys decides the price
    if int(state.get("credits", 0)) < cost:
        return False
    if not up[4](slot):
        return False
    state["credits"] = int(state.get("credits", 0)) - cost
    return True


# ----------------------------------------------------------------- results
def failure_penalty(credits, mode="normal"):
    """Points lost after a failed mission in Normal mode (5 % of the credits held) or Novice mode (2 %)."""
    credits = max(0, int(_num(credits, 0)))
    rate = NOVICE_PENALTY_RATE if mode == "novice" else PENALTY_RATE
    return int(credits * rate + 0.5)


def record_result(state, mission_id, score, cleared, kills=None, loot=None, used=None):
    """Apply the end of a mission.

    Cleared: the score is banked as hangar credits, unlock flags and journal line.
    Failed, Normal mode: nothing is gained and 5 % of the credits held are lost.
    Failed, Veteran mode: the pilot falls, the save becomes a memorial.
    `kills` ({kind: n}, the enemies destroyed) always goes into the Bestiary, win or lose.
    `loot` (the item caught during the mission) goes on sale in the hangar, win or lose; `used` (the items that were
    installed for the mission) are used up, win or lose (see story_items.py). The exception is the reactor of a BONUS
    mission: it must be caught AND the mission finished, a ship lost with it in the hold brings nothing back
    (`res["reactor_lost"]`) and the mission is offered again. A BONUS mission finished WITHOUT its item and without a
    death is neither won nor lost: no score paid, no penalty (`res["no_item"]` = the item missed), offered again.

    Returns {"score", "cleared", "first", "lost", "fallen"}. The journal stores a
    text KEY, not the translated text, so it follows the player's language.
    """
    score = max(0, int(score or 0))
    res = {"score": score, "cleared": bool(cleared), "first": False, "lost": 0, "fallen": False, "act": 0,
           "loot": None, "used": [], "opened": [], "reactor_lost": None, "no_item": None}
    record_kills(state, kills)            # the enemies met count whatever the outcome
    record_mission_kills(state, mission_id, kills)
    res["used"] = story_items.consume(state, used)           # before the Act can change: they belong to this one
    if loot in story_items.REACTOR_IDS and not cleared:
        res["reactor_lost"] = loot if story_items.status(state, loot) is None else None
        loot = None                                           # caught but the mission was lost: it is not acquired
    if loot and story_items.find(state, loot):
        res["loot"] = loot
        if loot in story_items.REACTOR_IDS:
            state.setdefault("log", []).append({"key": "story_log_" + loot})      # story_log_reactor_shield / _phenix
    if not cleared:
        if state.get("mode") == "veteran":
            state["fallen"] = True
            res["fallen"] = True
        else:
            credits = max(0, int(state.get("credits", 0)))
            res["lost"] = failure_penalty(credits, state.get("mode"))
            state["credits"] = credits - res["lost"]
        return res
    mission = next((m for m in MISSIONS if m["id"] == mission_id), None)
    if mission and (mission.get("reactor") or mission.get("drop")) and not mission_done(state, mission):
        # a BONUS mission won without its item (the reactor): neither a win nor a defeat. Nothing is paid, nothing is
        # lost, the mission stays on the map and the item falls again next time. (The enemies met are in the Bestiary.)
        res["cleared"] = False
        res["score"] = 0
        res["no_item"] = story_items.REACTORS.get(mission.get("reactor")) or mission.get("drop")
        return res
    state["credits"] = int(state.get("credits", 0)) + score
    if is_paint(mission):
        paint = paint_state(state)
        if paint["step"] == int(mission["paint"]) - 1:        # in order only (the cheat can fly any)
            paint["step"] += 1
            if paint["step"] >= PAINT_STEPS:                  # the pass is done: one colour change, a harder series
                paint.update(step=0, runs=paint["runs"] + 1, token=True)
                res["paint"] = True
            state["paint"] = paint
    if is_hunt(mission):
        state["mission_clears"] = dict(state.get("mission_clears") or {})
        # the level before this win is also the number of wins after it
        state["mission_clears"][mission_id] = hunt_level(state, mission_id)
    if mission:
        flags = state.setdefault("flags", {})
        hidden = [m["id"] for m in MISSIONS if m.get("secret") and not mission_open(state, m)]
        for name in mission.get("unlock") or []:
            flags[name] = True
        res["opened"] = [m_id for m_id in hidden if mission_open(state, mission_by_id(m_id))]    # a secret mission shows up
        if mission.get("grant_hull"):
            for sl in state.get("slots") or []:
                if sl.get("id") == mission["grant_hull"] and not sl.get("owned"):
                    sl["owned"] = True
                    res["hull"] = mission["grant_hull"]
        act = int(_num(mission.get("act"), 0))
        if act > int(_num(state.get("act"), 1)):
            state["act"] = act                       # the end of an act starts the next one
            res["act"] = act
        if mission.get("act3") and int(_num(state.get("act"), 1)) < 3:
            flags[ACT3_PENDING] = True               # the attack on Phobos and the choice of the hull come next
            res["act3"] = True
        if mission.get("epilogue"):
            res["epilogue"] = True                   # the end of the Adventure: its last scene
        if mission.get("win_scene"):
            res["win_scene"] = mission["win_scene"]  # a scene told after the first victory (the VIP rescue)
        cleared_ids = state.setdefault("cleared", [])
        res["first"] = mission_id not in cleared_ids
        if res["first"] and int(_num(mission.get("reward"), 0)) > 0:
            res["reward"] = int(mission["reward"])   # the parts salvaged (a BONUS mission): paid once
            state["credits"] = int(state.get("credits", 0)) + res["reward"]
        if res["first"]:
            cleared_ids.append(mission_id)
            state.setdefault("log", []).append({"key": mission.get("log") or "story_log_clear"})
    return res


def journal_entries(state, cheat_vn=False):
    """The journal as a list: the story intro first (always there), then what happened.

    Right under the first-clear line of a hunt mission comes a line with the total of
    enemies destroyed in all the runs of that mission (only once there is something to count).
    `cheat_vn` (the code VNOV): every scene of the visual novel is listed, answered or not.
    """
    out = [{"intro": True}]                                  # lines that replay a story scene, then the films
    for mid in scenes_seen(state):
        out.append({"scene": mid})
        out.extend({"film": fid} for fid in film_chain(mid) if film_seen(state, fid))
    shown = {e.get("film") for e in out}
    out.extend({"film": fid} for fid in FILMS if fid not in shown and film_seen(state, fid))
    if cheat_vn:                                                                 # every film and scene of the visual novel
        shown = {e.get("film") for e in out}
        out.extend({"film": story_vn.scene(sid)["film"]} for sid in story_vn.VN_ORDER
                   if story_vn.scene(sid).get("film") and story_vn.scene(sid)["film"] not in shown)
    out.extend({"vn": sid} for sid in story_vn.VN_ORDER                          # (a scene with a film is listed by it)
               if not story_vn.scene(sid).get("film") and (cheat_vn or story_vn.answered(state, sid)))
    hunts = {m["log"]: m["id"] for m in MISSIONS if (is_hunt(m) or is_paint(m)) and m.get("log")}
    for entry in state.get("log") or []:
        out.append(entry)
        key = entry.get("key") if isinstance(entry, dict) else None
        mission_id = hunts.get(key)
        if mission_id:
            out.append({"level": mission_level(state, mission_by_id(mission_id)), "mission": mission_id})
        if mission_id and mission_total_kills(state, mission_id) > 0:
            out.append({"kills": mission_total_kills(state, mission_id), "mission": mission_id})
    return out


def log_text(entry, translate):
    """Text of one journal line (new entries are {"key": ...}, old ones plain text)."""
    if isinstance(entry, dict):
        if "scene" in entry:
            scene = scene_of(entry.get("scene")) or {}
            return translate("story_log_scene").format(title=translate(scene.get("title") or "story_log_scene"))
        if "vn" in entry:
            scene = story_vn.scene(entry.get("vn")) or {}
            return translate("story_log_scene").format(title=translate(scene.get("journal") or "story_log_scene"))
        if "film" in entry:
            film = FILMS.get(entry.get("film")) or {}
            return translate("story_log_scene").format(title=translate(film.get("title") or "story_log_scene"))
        if "level" in entry:
            return translate("story_log_level").format(n=max(1, int(_num(entry.get("level"), 1))))
        if "kills" in entry:
            n = max(0, int(_num(entry.get("kills"), 0)))
            return translate("story_log_kill_1" if n == 1 else "story_log_kills").format(n=n)
        return translate(str(entry.get("key") or "story_log_clear"))
    return str(entry)
