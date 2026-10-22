"""The soft halo behind the enemy shots (enemy.EnemyBullet, boss.BossBullet): it lights the background, nothing else."""
import pygame
import pytest

import bullet_halo
from boss import BossBullet
from enemy import EnemyBullet

BG = (10, 10, 20)


def _canvas():
    s = pygame.Surface((200, 200))
    s.fill(BG)
    return s


def _lum(c):
    return c[0] + c[1] + c[2]


@pytest.mark.parametrize("make", [lambda: EnemyBullet(100, 100), lambda: BossBullet(100, 100)], ids=["enemy", "boss"])
def test_a_shot_glows_on_the_background_around_it(make):
    s = _canvas()
    b = make()
    b.draw(s)
    # a few pixels left of the shot (outside its 6-7 px body) are lighter than the background, and pinkish
    near = s.get_at((100 - 9, 106))[:3]
    assert _lum(near) > _lum(BG) + 15
    assert near[0] > near[1] and near[2] > near[1]
    # farther than the radius: untouched
    assert s.get_at((100 - bullet_halo.HALO_RADIUS - 6, 106))[:3] == BG
    assert s.get_at((100, 100 + 14 + bullet_halo.HALO_RADIUS + 6))[:3] == BG


@pytest.mark.parametrize("make", [lambda: EnemyBullet(100, 100), lambda: BossBullet(100, 100)], ids=["enemy", "boss"])
def test_the_glow_fades_with_the_distance(make):
    s = _canvas()
    make().draw(s)
    lums = [_lum(s.get_at((100 - d, 106))[:3]) for d in (6, 9, 13, 17)]
    assert lums == sorted(lums, reverse=True) and lums[0] > lums[-1]


def test_a_dead_shot_draws_nothing():
    for b in (EnemyBullet(100, 100), BossBullet(100, 100)):
        b.alive = False
        s = _canvas()
        b.draw(s)
        assert s.get_at((100 - 9, 106))[:3] == BG and s.get_at((100, 106))[:3] == BG


def test_the_shot_itself_is_still_drawn_over_the_glow():
    s = _canvas()
    EnemyBullet(100, 100).draw(s)
    assert s.get_at((100, 105))[:3] == (255, 180, 255)          # bright core
    assert s.get_at((98, 105))[:3] == (255, 80, 200)            # pink body


def test_the_hitbox_does_not_change():
    b = EnemyBullet(100, 100)
    assert b.get_hitbox().size == (8, 12)
    assert BossBullet(100, 100).get_hitbox().size == (7, 14)


def test_the_glow_never_goes_darker_and_is_built_only_once():
    s = pygame.Surface((200, 200))
    s.fill((200, 200, 200))
    EnemyBullet(100, 100).draw(s)
    for x in range(80, 120):
        for y in range(80, 130):
            assert min(s.get_at((x, y))[:3]) >= 200 or s.get_at((x, y))[:3] in ((255, 80, 200), (255, 180, 255))
    assert bullet_halo.halo_surface() is bullet_halo.halo_surface()


def test_the_halo_is_centred_on_the_shot_even_near_the_screen_edge():
    s = _canvas()
    EnemyBullet(2, 3).draw(s)                                   # half of the glow is off screen: no crash
    assert _lum(s.get_at((8, 9))[:3]) > _lum(BG)
