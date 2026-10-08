"""
Per-frame play logic of Game.update() once a run is active: ship updates,
stage transitions, the saucer boss, bullet/collision resolution and the
end-of-frame effects.

Extracted from game.py (Game.update). Functions take the Game object as `game`
and behave exactly as before; Game.update() calls them in the same order and
keeps every early `return` of the original.
"""
import random

import pygame

from settings import (BASE_HEIGHT, BASE_WIDTH, SCREEN_SHAKE_DECAY, stage_speed_mult)
from enemy import BigBird, Enemy
from explosion import TeslaCoilFx


def tick_ships(game):
    """Update every ship (input, edge kills, Tesla effect) and the electric hum."""
    keys = pygame.key.get_pressed()

    if game.stage_transition is None:
        ai_move = ai_shoot = None
        if game.attract_mode:
            ai_move, ai_shoot = game._attract_ai()
        for ship in game._ships():
            ship.rumble_level = int(getattr(game, "rumble_level", 3))
            ship.autofire = True if game.attract_mode else bool(getattr(game, "autofire", True))
            if getattr(game, "play_mode", "solo") != "coop":
                mode = game.input_mode
                joy = game.joystick
                ship.input_scheme = "solo"
            else:
                scheme = getattr(ship, "input_scheme", "solo")
                joy = getattr(ship, "_joy", None)
                mode = "gamepad" if scheme == "pad" else "keyboard"
            if game.attract_mode and ship is game.player:
                edge_killed = ship.update(
                    game.dt, keys, mode, joy,
                    allow_shoot=(game.input_grace <= 0),
                    ai_move=ai_move, ai_shoot=ai_shoot,
                )
            else:
                edge_killed = ship.update(
                    game.dt, keys, mode, joy,
                    allow_shoot=(game.input_grace <= 0),
                )
            cd = float(getattr(ship, "shield_ripple_cd", 0.0) or 0.0)
            if cd > 0:
                ship.shield_ripple_cd = max(0.0, cd - game.dt)
            if edge_killed:
                game._note_scalable("razor")
                kind = "gameover" if ship.dying else "edge"
                game.explosions.append(game._boom(ship.x, ship.y, kind=kind))
                game.shake_amount = 22.0 if ship.dying else 14.0
                game.sounds.play("explosion_big" if ship.dying else "explosion", x=ship.x)
                side = getattr(ship, "last_edge_side", 0) or getattr(ship, "edge_side", -1)
                game.tesla_fx = TeslaCoilFx(side, ship.y)
                game.sounds.play_electric(True, x=ship.x)
                if getattr(ship, "just_lost_life", False):
                    game.stage_life_lost = True
                if getattr(ship, "edge_contact", False) and getattr(ship, "edge_flash", 0) > 0:
                    game.stage_touched_edge = True
                if getattr(ship, "flag_gauge_max", False):
                    ship.flag_gauge_max = False
                    if not getattr(ship, "phenix_auto_refill", False):
                        game._note_scalable("gauge_max")
                if getattr(game, "play_mode", "") == "coop" and getattr(ship, "just_lost_life", False):
                    game._on_coop_life_lost(ship)
    tesla_on = game.tesla_fx is not None and not game.tesla_fx.is_finished()
    flash_on = any(p.edge_flash > 0.08 and not p.dying for p in game._ships())
    game.sounds.play_electric(tesla_on or flash_on, x=game._sfx_electric_x())


def tick_fly_up(game):
    """Stage transition: ships fly off the top, then the next stage is set up."""
    for ship in game._ships():
        if ship.alive or ship.dying:
            ship.y -= 420 * game.dt
            ship.engine_intensity = 1.0
    game._tick_stars(follow=True)
    if all((not s.alive) or s.y < -80 for s in game._ships()):
        if getattr(game, "adventure", None):
            game._end_adventure(True)
            return
        game.stage += 1
        game._note_scalable("stage2", game.stage, absolute=True)
        if game.stage > 1 and (game.stage - 1) % 5 == 0:
            game._note_scalable("loop")
        if game.stage >= 21:
            game._note_scalable("boldly_go", game.stage, absolute=True)
        game._setup_stage(game.stage)
        for ship in game._ships():
            ship.y = BASE_HEIGHT + 60
            hw = float(getattr(ship, "width", 60) or 60) * 0.5
            ship.x = max(hw + 4.0, min(float(BASE_WIDTH) - hw - 4.0, float(ship.x)))
        game.stage_transition = "arrive"
        game.transition_timer = 0.0
    # still draw explosions etc lightly
    for exp in game.explosions[:]:
        exp.update(game.dt)
        if exp.is_finished():
            game.explosions.remove(exp)


def tick_arrive(game):
    """Stage transition: ships enter from the bottom."""
    # Ship enters from bottom
    target_y = BASE_HEIGHT - 95
    for ship in game._ships():
        if ship.alive:
            ship.y -= 380 * game.dt
            ship.engine_intensity = 1.0
    game._tick_stars(follow=True)
    game.formation.update(game.dt, game.player.x)
    game._drain_detach_pops()
    if all((not s.alive) or s.y <= target_y for s in game._ships()):
        for ship in game._ships():
            if ship.alive:
                ship.y = target_y
                feet = ship.y + float(getattr(ship, "height", 90) or 90) * 0.48
                game.explosions.append(game._boom(ship.x - 18, feet, kind="dust"))
                game.explosions.append(game._boom(ship.x + 18, feet, kind="dust"))
        game.stage_transition = None
        game.input_grace = 0.4
    for exp in game.explosions[:]:
        exp.update(game.dt)
        if exp.is_finished():
            game.explosions.remove(exp)


def tick_boss_saucer(game):
    """Saucer boss: cries, angry queue and bird spawning."""
    game.boss_saucer.update(game.dt, game.player.x)
    game._boss_cry_quiet = getattr(game, "_boss_cry_quiet", 0.0) + game.dt
    # Idle yell only after a long silence (ready / angry / yell all reset the clock)
    if game._boss_cry_quiet > 8.0 and random.random() < 0.045 * game.dt:
        game._play_boss_cry("boss_yell", volume=0.88, x=game.boss_saucer.boss.x)
    q = getattr(game, "_boss_angry_queue", None)
    if q:
        nxt = []
        for wait in q:
            wait -= game.dt
            if wait <= 0:
                game._play_boss_cry("boss_angry", volume=0.9, x=game.boss_saucer.boss.x)
            else:
                nxt.append(wait)
        game._boss_angry_queue = nxt
    # Spawn birds more often — stage1 2x more likely than stage2, max 10
    game.boss_bird_timer -= game.dt
    if game.boss_bird_timer <= 0:
        rate = float(getattr(game.boss_saucer, "bird_rate", 1.0) or 1.0)
        game.boss_bird_timer = random.uniform(0.9, 1.8) / max(0.15, rate)
        alive_birds = len(game.formation.get_alive_enemies())
        if alive_birds < 6:
            x = random.uniform(60, BASE_WIDTH - 60)
            st = 1 if random.random() < 0.67 else 2
            bird = Enemy(x, -30, formation_index=alive_birds + random.randint(0, 6), stage=st)
            bird.speed_mult = stage_speed_mult(game.stage) * game.difficulty_speed_mult()
            bird.state = "formation"
            bird.start_dive(x)  # dive in their spawn lane, not a shared player X
            game.formation.enemies.append(bird)


def begin_stage_clear(game):
    """Non-boss stage cleared: start the fly-up transition."""
    game._clear_enemy_fire()
    game._on_stage_cleared()
    if not getattr(game, "adventure", None):
        game._play_level_vo(int(getattr(game, "stage", 1) or 1) + 1)
    game.stage_transition = "fly_up"
    for ship in game._ships():
        ship.destroy_bullet()


def boss_cataclysm(game):
    """Boss killed: cataclysm explosion, kill the birds, start the outro."""
    # Cataclysm: explode many cells + boss area
    import random as _r
    living = [c for c in game.boss_saucer.cells if c.alive]
    for c in living:
        c.alive = False
        if _r.random() < 0.35:
            game.explosions.append(game._boom(c.x, c.y, kind="enemy"))
    for d in game.boss_saucer.decorations:
        if d.alive:
            d.alive = False
            game.explosions.append(game._boom(d.x, d.y, kind="enemy"))
    bx = game.boss_saucer.boss.x
    by = game.boss_saucer.boss.y
    for _ in range(8):
        game.explosions.append(game._boom(
            bx + _r.uniform(-120, 120),
            by + _r.uniform(-40, 80),
            kind="gameover" if _ < 3 else "collision"
        ))
    game.shake_amount = 30.0
    game.sounds.play("explosion_big", x=bx)
    for e in game.formation.get_alive_enemies():
        e.kill()
    game.boss_saucer = None
    game.bosses_defeated += 1
    game._note_scalable("boss_down")
    if game.difficulty == "veteran":
        game._note_scalable("veteran_clear")
    game._note_scalable("ten_flags")
    game._clear_enemy_fire()
    game.stage_transition = "boss_outro"
    game.transition_timer = 0.0


def tick_boss_outro(game):
    """Boss outro spectacle, then fly up to the next stage."""
    game.transition_timer += game.dt
    game._tick_stars(follow=True)
    for exp in game.explosions[:]:
        exp.update(game.dt)
        if exp.is_finished():
            game.explosions.remove(exp)
    # After spectacle, ship flies to next stage
    if game.transition_timer > 1.8:
        game._clear_enemy_fire()
        game._on_stage_cleared()
        game._play_level_vo(int(getattr(game, "stage", 1) or 1) + 1)
        game.stage_transition = "fly_up"
        for ship in game._ships():
            ship.destroy_bullet()


def player_bullets_vs_enemies(game):
    """Player bullets against the boss, big birds and regular birds."""
    for ship in game._ships():
      for shot_i, bullet_rect in ship.get_bullet_rects():
        hit_something = False
        # Boss saucer armor / core
        if game.boss_saucer is not None and game.boss_saucer.alive:
            result = game.boss_saucer.hit_bullet(bullet_rect)
            if result is not None:
                kind, target = result
                if kind == "cell":
                    ship.destroy_bullet("neutral", index=shot_i)
                    if getattr(target, "is_purple", False):
                        game.explosions.append(game._boom(target.x, target.y, kind="electric"))
                        game.shake_amount = 4.5
                        game.sounds.play("shield_zap", volume=0.75, x=target.x)
                    else:
                        game.explosions.append(game._boom(target.x, target.y, kind="enemy"))
                        game.shake_amount = 3.5
                        game.sounds.play("enemy_explosion", volume=0.4, x=target.x)
                    game._add_score(ship, 1)
                    game._note_scalable("wrecker")
                elif kind == "deco":
                    ship.destroy_bullet("neutral", index=shot_i)
                    game.explosions.append(game._boom(target.x, target.y, kind="flame"))
                    game.shake_amount = 5.0
                    game.sounds.play("enemy_explosion", volume=0.45, x=target.x)
                    game._add_score(ship, 50)
                    game._note_scalable("cutter")
                    delay = 0.72 + random.uniform(0.18, 0.65)
                    game._boss_angry_queue.append(delay)
                    if getattr(game.boss_saucer, "flag_ports_pair", False):
                        game.boss_saucer.flag_ports_pair = False
                        game._note_scalable("port_pair")
                elif kind == "boss":
                    game._hitstop(0.045)
                    ship.destroy_bullet("valid", index=shot_i)
                    target.kill()
                    game._add_score(ship, game._boss_points())
                    game.explosions.append(game._boom(target.x, target.y, kind="gameover"))
                    game.shake_amount = 20.0
                    game.sounds.play("explosion_big", x=ship.x)
                hit_something = True
        if hit_something:
            break  # indices shifted; next frame continues

        for enemy in game.formation.get_hittable_enemies():
            if isinstance(enemy, BigBird):
                if bullet_rect.colliderect(enemy.get_left_wing_hitbox()):
                    if enemy.hit_wing("left"):
                        ship.destroy_bullet("neutral", index=shot_i)
                        game.explosions.append(game._boom(enemy.x - 35, enemy.y, kind="enemy"))
                        game.shake_amount = 3.0
                        game.sounds.play("enemy_explosion", volume=0.5, x=enemy.x)
                    else:
                        ship.destroy_bullet("neutral", index=shot_i)
                    hit_something = True
                    break
                if bullet_rect.colliderect(enemy.get_right_wing_hitbox()):
                    if enemy.hit_wing("right"):
                        ship.destroy_bullet("neutral", index=shot_i)
                        game.explosions.append(game._boom(enemy.x + 35, enemy.y, kind="enemy"))
                        game.shake_amount = 3.0
                        game.sounds.play("enemy_explosion", volume=0.5, x=enemy.x)
                    else:
                        ship.destroy_bullet("neutral", index=shot_i)
                    hit_something = True
                    break
                if bullet_rect.colliderect(enemy.get_body_hitbox()):
                    enemy.kill()
                    game._hitstop()
                    ship.destroy_bullet("valid", index=shot_i)
                    game._add_score(ship, game._enemy_kill_points(enemy))
                    game._note_bird_kill()
                    if getattr(enemy, "diving", False):
                        game._note_scalable("butcher")
                    game._note_scalable("clean_shot", int(getattr(ship, "combo_streak", 0) or 0), absolute=True)
                    game.explosions.append(game._boom(enemy.x, enemy.y, kind="enemy", delay_frames=1))
                    game.shake_amount = 7.0
                    game.sounds.play("enemy_explosion", x=enemy.x)
                    hit_something = True
                    break
                # Catch-all: silhouette overlap that slipped between wing/body boxes
                if bullet_rect.colliderect(enemy.get_hitbox()):
                    enemy.kill()
                    game._hitstop()
                    ship.destroy_bullet("valid", index=shot_i)
                    game._add_score(ship, game._enemy_kill_points(enemy))
                    game._note_bird_kill()
                    if getattr(enemy, "diving", False):
                        game._note_scalable("butcher")
                    game._note_scalable("clean_shot", int(getattr(ship, "combo_streak", 0) or 0), absolute=True)
                    game.explosions.append(game._boom(enemy.x, enemy.y, kind="enemy", delay_frames=1))
                    game.shake_amount = 7.0
                    game.sounds.play("enemy_explosion", x=enemy.x)
                    hit_something = True
                    break
            else:
                if bullet_rect.colliderect(enemy.get_hitbox()):
                    enemy.kill()
                    game._hitstop()
                    ship.destroy_bullet("valid", index=shot_i)
                    game._add_score(ship, game._enemy_kill_points(enemy))
                    game._note_bird_kill()
                    if getattr(enemy, "diving", False):
                        game._note_scalable("butcher")
                    game._note_scalable("clean_shot", int(getattr(ship, "combo_streak", 0) or 0), absolute=True)
                    game.explosions.append(game._boom(enemy.x, enemy.y, kind="enemy", delay_frames=1))
                    game.shake_amount = 5.5
                    game.sounds.play("enemy_explosion", x=enemy.x)
                    hit_something = True
                    break
        if hit_something:
            break


def boss_floor_check(game):
    """Unbroken saucer touching the bottom of the screen kills the ship(s)."""
    if (game.boss_saucer is not None and game.boss_saucer.alive
            and game.stage_transition is None
            and game.boss_saucer.touches_floor(BASE_HEIGHT)):
        for ship in game._ships():
            if not ship.alive or ship.dying:
                continue
            if getattr(ship, "infinite_lives", False):
                continue
            if game.play_mode == "coop":
                ship.hit()
                game._on_coop_life_lost(ship)
            else:
                ship.lives = 0
                ship.dying = True
                ship.death_timer = 0.0
                ship.invulnerable = 0.0
                ship.rumble(1.0, 1.0, 640)
            ship.phenix_gauge = float(getattr(ship, "phenix_min_gauge", 0))
            ship.combo_streak = 0
            ship.phenix_timer = 0.0
            game.explosions.append(game._boom(ship.x, ship.y, kind="gameover"))
        game.shake_amount = 24.0
        game.sounds.play("explosion_big", x=BASE_WIDTH // 2)


def enemy_attacks_vs_players(game):
    """Boss hull / bullets, enemy bullets and divers against the ship(s)."""
    for ship in game._ships():
        if not ship.alive or ship.dying:
            continue
        player_hitbox = ship.get_hitbox()
        if game.boss_saucer is not None and game.boss_saucer.alive:
            hull = game.boss_saucer.get_hull_hitbox()
            if hull.width > 0 and player_hitbox.colliderect(hull):
                if ship.infinite_lives:
                    ship.hit()
                    game.explosions.append(game._boom(ship.x, ship.y, kind="bullet"))
                    game.shake_amount = 14.0
                    game.sounds.play("explosion", x=ship.x)
                    ship.y = min(BASE_HEIGHT - 80, ship.y + 40)
                else:
                    if game.play_mode == "coop":
                        ship.hit()
                        game._on_coop_life_lost(ship)
                    else:
                        ship.lives = 0
                        ship.dying = True
                        ship.death_timer = 0.0
                        ship.invulnerable = 0.0
                        ship.rumble(1.0, 1.0, 640)
                    ship.phenix_gauge = float(getattr(ship, "phenix_min_gauge", 0))
                    ship.combo_streak = 0
                    ship.phenix_timer = 0.0
                    game.explosions.append(game._boom(ship.x, ship.y, kind="gameover"))
                    game.shake_amount = 24.0
                    game.sounds.play("explosion_big", x=ship.x)
            for b in game.boss_saucer.bullets[:]:
                if b.alive and b.get_hitbox().colliderect(player_hitbox):
                    b.alive = False
                    if ship.is_phenix and getattr(ship, "uses_shield", False):
                        bh = b.get_hitbox()
                        game._shield_absorb(ship, bh.centerx, bh.centery)
                        game._add_score(ship, 5)
                    elif (not ship.is_phenix) and ship.invulnerable <= 0 and ship.alive and not ship.dying:
                        ship.hit()
                        if game.play_mode == "coop":
                            game._on_coop_life_lost(ship)
                        kind = "gameover" if ship.dying else "bullet"
                        game.explosions.append(game._boom(ship.x, ship.y, kind=kind))
                        game.shake_amount = 22.0 if ship.dying else 12.0
                        game.sounds.play("explosion_big" if ship.dying else "explosion", x=ship.x)
                    break
        for bullet in game.formation.bullets[:]:
            if bullet.alive and bullet.get_hitbox().colliderect(player_hitbox):
                bullet.alive = False
                if ship.is_phenix and getattr(ship, "uses_shield", False):
                    bh = bullet.get_hitbox()
                    game._shield_absorb(ship, bh.centerx, bh.centery)
                    game._add_score(ship, 5)
                elif (not ship.is_phenix) and ship.invulnerable <= 0 and ship.alive and not ship.dying:
                    ship.hit()
                    if game.play_mode == "coop":
                        game._on_coop_life_lost(ship)
                    kind = "gameover" if ship.dying else "bullet"
                    game.explosions.append(game._boom(ship.x, ship.y, kind=kind))
                    game.shake_amount = 22.0 if ship.dying else 12.0
                    game.sounds.play("explosion_big" if ship.dying else "explosion", x=ship.x)
                break
        for enemy in game.formation.get_hittable_enemies():
            if enemy.diving and enemy.get_hitbox().colliderect(player_hitbox):
                try:
                    enemy.kill(flash=False)
                except TypeError:
                    enemy.kill()
                    enemy.hit_flash_frames = 0
                    enemy.alive = False
                    enemy.dying = False
                game.explosions.append(game._boom(enemy.x, enemy.y, kind="collision"))
                game.sounds.play("enemy_explosion", x=enemy.x)
                if ship.is_phenix:
                    game.shake_amount = max(game.shake_amount, 8.0)
                    if getattr(ship, "uses_shield", False):
                        game._add_score(ship, game._enemy_kill_points(enemy))
                        game._note_bird_kill()
                        if getattr(enemy, "diving", False):
                            game._note_scalable("butcher")
                else:
                    ship.hit()
                    if game.play_mode == "coop":
                        game._on_coop_life_lost(ship)
                    pkind = "gameover" if ship.dying else "collision"
                    game.explosions.append(game._boom(ship.x, ship.y, kind=pkind))
                    game.shake_amount = 26.0 if ship.dying else 18.0
                    game.sounds.play("explosion_big", x=ship.x)
                break


def tick_effects_and_hotseat(game):
    """End of frame: life-lost flags, explosions, Tesla, shake, hot-seat hand-off."""
    if any(getattr(s, "just_lost_life", False) for s in game._ships()):
        game.stage_life_lost = True
    for s in game._ships():
        if getattr(s, "flag_gauge_max", False):
            s.flag_gauge_max = False
            if not getattr(s, "phenix_auto_refill", False):
                game._note_scalable("gauge_max")

    for exp in game.explosions[:]:
        exp.update(game.dt)
        if exp.is_finished():
            game.explosions.remove(exp)
    if game.tesla_fx is not None:
        game.tesla_fx.update(game.dt)
        if game.tesla_fx.is_finished():
            game.tesla_fx = None
            game.sounds.play_electric(False)

    # Soft performance cap: keep newest explosions only
    if len(game.explosions) > 24:
        game.explosions = game.explosions[-24:]

    if game.shake_amount > 0:
        game.shake_amount = max(0.0, game.shake_amount - SCREEN_SHAKE_DECAY * game.dt)

    # Life lost mid-frame (enemy bullet / dive) — hold, then hand off
    if (game.hotseat and not game.attract_mode and not game.game_over
            and not game.hotseat_wait and game.hotseat_hold <= 0
            and game.stage_transition is None
            and getattr(game.player, "just_lost_life", False)
            and game.player.alive and not game.player.dying):
        game._hotseat_arm_hold("switch", game.HOTSEAT_HOLD_LIFE)
