"""A test rig for the Guardians alone (the training encounter is gone from the game): the real GuardianSquad of the
Adventure, its five Guardians already in their places (patrolling at y = 130, no entry), the lasers in `bullets` moved
like the formation's shots, and some still birds (enemy.Enemy, one per colour given) the lasers can burn."""

import guardian as gd
from enemy import Enemy
from settings import BASE_WIDTH


class Rig:
    def __init__(self, birds=()):
        self.sq = gd.GuardianSquad(gd.PER_WAVE)
        self.sq.guardians = []
        for i in range(gd.PER_WAVE):
            g = gd.Guardian(BASE_WIDTH * (i + 1) / (gd.PER_WAVE + 1), 130, i)
            g.entry = 0.0
            self.sq.guardians.append(g)
        self.sq.next_charge = 0.0
        self.bullets = []
        self.birds = [Enemy(BASE_WIDTH * (i + 1) / (len(birds) + 1), 250 + (stage - 1) * 85, i, stage)
                      for i, stage in enumerate(birds)]

    guardians = property(lambda self: self.sq.guardians)
    enemies = property(lambda self: self.sq.guardians + self.birds)
    clock = property(lambda self: self.sq.clock)
    effects = property(lambda self: self.sq.effects)
    burned = property(lambda self: self.sq.burned)

    def update(self, dt, player_x, player_y=625):
        self.bullets = [b for b in self.bullets if b.alive]
        for bolt in self.bullets:
            bolt.update(dt)
        self.sq.tick(dt, player_x, player_y, self.bullets, self.birds)
        self.bullets[:] = [b for b in self.bullets if b.alive]

    def _burn_birds(self, previous_boxes):
        self.sq.bullets = self.bullets
        self.sq.burned += gd.burn_birds(self.sq, self.birds, previous_boxes)

    def draw(self, surface):
        self.sq.draw(surface)
        for bolt in self.bullets:
            bolt.draw(surface)

    def get_alive_enemies(self):
        return [b for b in self.enemies if b.alive and not b.dying]

    def get_hittable_enemies(self):
        return self.get_alive_enemies()

    def all_dead(self):
        return (not any(b.alive for b in self.enemies) and not self.effects and not any(b.alive for b in self.bullets)
                and not any(g.fx_active() for g in self.guardians))
