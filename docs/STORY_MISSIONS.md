# Phenix Rebirth - Missions de l'Aventure (v1.7.2)

Liste des 70 missions de `src/story_state.py` (`MISSIONS`), écrite par `python docs/manual/make_story_missions.py` : ne pas la modifier à la main.

- `id` : identifiant stable (une sauvegarde le garde ; une mission retirée va dans `REMOVED_MISSIONS`)
- `need` : le drapeau qui ouvre la mission ; il est posé par la victoire d'une mission (`unlock`)
- *une seule fois* : jouée une fois jusqu'à la fin ouverte de l'acte IV (`ending_done`), puis toutes les missions sont rejouables
- Titres français et anglais : `src/i18n.py`. Le manuel du joueur (docs/manual) en reprend l'ordre.

## Acte 1 - le Shield

| id | Mission (FR) | Mission (EN) | Type | S'ouvre après | Notes |
|---|---|---|---|---|---|
| `ch1_sortie` | Bestiaire I : Première sortie | Bestiary I: First sortie | vagues | dès le départ | rejouable |
| `best_s2` | Bestiaire II : oiseaux kaki | Bestiary II: khaki birds | vagues | Bestiaire I : Première sortie (`ch1_sortie`) | rejouable |
| `best_s3` | Bestiaire III : gargouilles | Bestiary III: gargoyles | vagues | Bestiaire II : oiseaux kaki (`bestiary_s2`) | rejouable |
| `best_s4` | Bestiaire IV : gargouilles sombres | Bestiary IV: dark gargoyles | vagues | Bestiaire III : gargouilles (`bestiary_s3`) | rejouable |
| `bonus_2d` | BONUS : le réacteur à impulsion bidimensionnelle (Shield) | BONUS: the two-dimensional impulse reactor (Shield) | Galaga | Bestiaire IV : gargouilles sombres (`bestiary_s4`) | secrète jusqu'à son ouverture, reste sur la carte des actes suivants tant qu'elle n'est pas gagnée |
| `ast_1` | Ceinture d'astéroïdes I | Asteroid belt I | Asteroids | Bestiaire I : Première sortie (`ch1_sides`) | rejouable, 60 astéroïdes |
| `dome_1` | Dôme I : l'épave du Shield | Dome I: the Shield wreck | vagues | Ceinture d'astéroïdes I (`ast_s1`) | une seule fois |
| `dome_2` | Dôme II : les Kakis | Dome II: the Khakis | vagues | Dôme I : l'épave du Shield (`dome_s1`) | une seule fois |
| `dome_3` | Dôme III : les Gargouilles | Dome III: the Gargoyles | vagues | Dôme II : les Kakis (`dome_s2`) | une seule fois |
| `dome_4` | Dôme IV : les Gargouilles sombres | Dome IV: the Dark Gargoyles | vagues | Dôme III : les Gargouilles (`dome_s3`) | une seule fois |
| `dome_5` | Dôme V : la nuée | Dome V: the swarm | nuée | Dôme IV : les Gargouilles sombres (`dome_s4`) | une seule fois |
| `phobos_1` | Défense de Phobos I : la horde | Defence of Phobos I: the horde | nuée | Dôme V : la nuée (`dome_s5`) | une seule fois |
| `act2_gate` | Passage à l'acte 2 | Gateway to Act 2 | vagues | Défense de Phobos I : la horde (`phobos_s1`) | une seule fois |
| `ch2_tease` | Acte 2 | Act 2 | vagues | Passage à l'acte 2 (`act2`) | non jouable (annonce) |
| `sentinelle_1` | EDF - Sentinelles silencieuses I : Jupiter | EDF - Silent Sentinels I: Jupiter | Space War | Bestiaire I : Première sortie (`ch1_sides`) | une seule fois (rejouable après `sentinelles_done`), jupiter |
| `lander_deimos` | Atterrissage sur Déimos | Landing on Deimos | Lunar Lander | Dôme II : les Kakis (`dome_s2`) | facultative, une seule fois, carburant 90 |
| `raid_deimos` | Raid sur les bases avioïdes I : Déimos | Raid on the Avioid bases I: Deimos | Scramble | Dôme II : les Kakis (`dome_s2`) | facultative, une seule fois, raid niveau 1 |
| `lander_rock` | Atterrissage sur un astéroïde | Landing on an asteroid | Lunar Lander | Dôme IV : les Gargouilles sombres (`dome_s4`) | facultative, une seule fois, carburant 80 |
| `raid_rock` | Raid sur les bases avioïdes II : astéroïde | Raid on the Avioid bases II: asteroid | Scramble | Dôme IV : les Gargouilles sombres (`dome_s4`) | facultative, une seule fois, raid niveau 2 |

## Acte 2 - le Phenix

| id | Mission (FR) | Mission (EN) | Type | S'ouvre après | Notes |
|---|---|---|---|---|---|
| `bonus_2d_phenix` | BONUS : le réacteur à impulsion bidimensionnelle (Phenix) | BONUS: the two-dimensional impulse reactor (Phenix) | Galaga | Phenix V : le réveil (`phenix_owned`) | secrète jusqu'à son ouverture, reste sur la carte des actes suivants tant qu'elle n'est pas gagnée |
| `bonus_vip` | BONUS : sauvetage VIP | BONUS: VIP rescue | escorte | un réacteur 2D installé sur un vaisseau | secrète jusqu'à son ouverture, une seule fois, reste sur la carte des actes suivants tant qu'elle n'est pas gagnée |
| `best_boss` | Bestiaire V : le commandant avioïde | Bestiary V: the Avioid commander | vagues | Passage à l'acte 2 (`act2`) | rejouable |
| `best_guardians` | Bestiaire VI : les Gardiens | Bestiary VI: the Guardians | vagues | Phenix III : le relais (`phenix_s3`) | rejouable |
| `ast_2` | Ceinture d'astéroïdes II | Asteroid belt II | Asteroids | Passage à l'acte 2 (`act2`) | rejouable, 80 astéroïdes |
| `guardians_1` | Gardiens I : le premier feu | Guardians I: the first fire | vagues | Ceinture d'astéroïdes II (`ast_s2`) | une seule fois |
| `phenix_1` | Phenix I : le signal | Phenix I: the signal | vagues | Gardiens I : le premier feu (`guardians_s1`) | une seule fois |
| `phenix_2` | Phenix II : le brouillage | Phenix II: the jamming | nuée | Phenix I : le signal (`phenix_s1`) | une seule fois |
| `phobos_2` | Défense de Phobos II : le siège | Defence of Phobos II: the siege | nuée | Phenix II : le brouillage (`phenix_s2`) | une seule fois |
| `phenix_3` | Phenix III : le relais | Phenix III: the relay | vagues | Défense de Phobos II : le siège (`phobos_s2`) | une seule fois |
| `phenix_4` | Phenix IV : l'approche | Phenix IV: the approach | vagues | Phenix III : le relais (`phenix_s3`) | une seule fois |
| `phenix_5` | Phenix V : le réveil | Phenix V: the awakening | vagues | Phenix IV : l'approche (`phenix_s4`) | une seule fois |
| `paint_1` | Peinture I : l'échantillon | Paint I: the sample | Space Invaders | Passage à l'acte 2 (`act2`) | rejouable |
| `paint_2` | Peinture II : le mélange | Paint II: the mix | Space Invaders | Passage à l'acte 2 (`act2`) | rejouable |
| `paint_3` | Peinture III : la cuve | Paint III: the vat | Space Invaders | Passage à l'acte 2 (`act2`) | rejouable |
| `guardians_2` | Gardiens II : le mur de lasers | Guardians II: the wall of lasers | vagues | Phenix V : le réveil (`phenix_owned`) | une seule fois |
| `act3_gate` | Passage à l'acte 3 : le grand raid | Gateway to Act 3: the great raid | vagues | Gardiens II : le mur de lasers (`guardians_s2`) | une seule fois |
| `sentinelle_2` | EDF - Sentinelles silencieuses II : Saturne | EDF - Silent Sentinels II: Saturn | Space War | EDF - Sentinelles silencieuses I : Jupiter (`sentinelle_1`) | une seule fois (rejouable après `sentinelles_done`), saturn |
| `sentinelle_3` | EDF - Sentinelles silencieuses III : Uranus | EDF - Silent Sentinels III: Uranus | Space War | EDF - Sentinelles silencieuses II : Saturne (`sentinelle_2`) | une seule fois (rejouable après `sentinelles_done`), uranus |
| `lander_europa` | Atterrissage sur Europe | Landing on Europa | Lunar Lander | Phenix I : le signal (`phenix_s1`) | facultative, une seule fois, carburant 70 |
| `raid_europa` | Raid sur les bases avioïdes III : Europe | Raid on the Avioid bases III: Europa | Scramble | Phenix I : le signal (`phenix_s1`) | facultative, une seule fois, raid niveau 3 |
| `lander_titan` | Atterrissage sur Titan | Landing on Titan | Lunar Lander | Phenix III : le relais (`phenix_s3`) | facultative, une seule fois, carburant 70 |
| `raid_titan` | Raid sur les bases avioïdes IV : Titan | Raid on the Avioid bases IV: Titan | Scramble | Phenix III : le relais (`phenix_s3`) | facultative, une seule fois, raid niveau 4 |

## Acte 3 - la Riposte

| id | Mission (FR) | Mission (EN) | Type | S'ouvre après | Notes |
|---|---|---|---|---|---|
| `up_shield_1` | Remise en état I : les propulseurs | Repairs I: the thrusters | vagues | Passage à l'acte 3 : le grand raid (`act3`) | vaisseau gardé : shield, une seule fois |
| `up_shield_2` | Remise en état II : la coque | Repairs II: the hull | vagues | Remise en état I : les propulseurs (`ch3_speed`) | vaisseau gardé : shield, une seule fois |
| `up_shield_3` | Remise en état III : le blindage Tesla | Repairs III: the Tesla shielding | nuée | Remise en état II : la coque (`ch3_lives`) | vaisseau gardé : shield, une seule fois |
| `up_shield_4` | Remise en état IV : le dôme | Repairs IV: the dome | vagues | Remise en état III : le blindage Tesla (`ch3_wall`) | vaisseau gardé : shield, une seule fois |
| `up_phenix_1` | Remise en état I : les propulseurs | Repairs I: the thrusters | vagues | Passage à l'acte 3 : le grand raid (`act3`) | vaisseau gardé : phoenix, une seule fois |
| `up_phenix_2` | Remise en état II : la coque | Repairs II: the hull | vagues | Remise en état I : les propulseurs (`ch3_speed`) | vaisseau gardé : phoenix, une seule fois |
| `up_phenix_3` | Remise en état III : la jauge | Repairs III: the gauge | vagues | Remise en état II : la coque (`ch3_lives`) | vaisseau gardé : phoenix, une seule fois |
| `bonus_wreck_phenix` | BONUS : l'épave du Phenix | BONUS: the wreck of the Phenix | nuée | Passage à l'acte 3 : le grand raid (`act3`) | vaisseau gardé : shield, une seule fois |
| `bonus_wreck_shield` | BONUS : l'épave du NX01 | BONUS: the wreck of the NX01 | nuée | Passage à l'acte 3 : le grand raid (`act3`) | vaisseau gardé : phoenix, une seule fois |
| `bonus_singularity` | BONUS : le convoi de la Singularité | BONUS: the Singularity convoy | Galaga | Remise en état I : les propulseurs (`ch3_speed`) |  |
| `ast_3` | Ceinture d'astéroïdes III | Asteroid belt III | Asteroids | Remise en état III : la jauge ou Remise en état IV : le dôme (`ch3_ready`) | rejouable, 100 astéroïdes |
| `guardians_3` | Gardiens III : le Gardien Alpha | Guardians III: the Alpha Guardian | vagues | Ceinture d'astéroïdes III (`ast_s3`) | une seule fois |
| `phobos_3` | Défense de Phobos III : la marée | Defence of Phobos III: the tide | nuée | Gardiens III : le Gardien Alpha (`guardians_s3`) | une seule fois |
| `sentinelle_4` | EDF - Sentinelles silencieuses IV : Neptune | EDF - Silent Sentinels IV: Neptune | Space War | EDF - Sentinelles silencieuses III : Uranus (`sentinelle_3`) | une seule fois (rejouable après `sentinelles_done`), neptune |
| `final_1` | Riposte I : Jupiter | Counterstrike I: Jupiter | vagues | Défense de Phobos III : la marée (`phobos_s3`) | une seule fois |
| `final_2` | Riposte II : Saturne | Counterstrike II: Saturn | nuée | Riposte I : Jupiter (`final_s1`) | une seule fois |
| `final_3` | Riposte III : Uranus | Counterstrike III: Uranus | Galaga | Riposte II : Saturne (`final_s2`) | une seule fois |
| `final_4` | Riposte IV : Neptune | Counterstrike IV: Neptune | vagues | Riposte III : Uranus (`final_s3`) | une seule fois |
| `final_5` | Riposte V : Triton | Counterstrike V: Triton | vagues | Riposte IV : Neptune (`final_s4`) | une seule fois |
| `lander_triton` | Atterrissage sur Triton | Landing on Triton | Lunar Lander | Passage à l'acte 3 : le grand raid (`act3`) | facultative, une seule fois, carburant 60 |
| `raid_triton` | Raid sur les bases avioïdes V : Triton | Raid on the Avioid bases V: Triton | Scramble | Passage à l'acte 3 : le grand raid (`act3`) | facultative, une seule fois, raid niveau 5 |

## Acte IV - No Mercy Left (fin ouverte et BONUS DE FIN)

| id | Mission (FR) | Mission (EN) | Type | S'ouvre après | Notes |
|---|---|---|---|---|---|
| `act4_alcyone` | Alcyone - Le Grand Saut | Alcyone - The Great Leap | fin | Riposte V : Triton (`game_won`) | une seule fois |
| `bonus_scramble` | BONUS FINAL - Scramble | FINAL BONUS - Scramble | Scramble | Alcyone - Le Grand Saut (`ending_done`) | secrète jusqu'à son ouverture, facultative, BONUS FINAL, sans fin |
| `bonus_lander` | BONUS FINAL - Lunar Lander | FINAL BONUS - Lunar Lander | Lunar Lander | Alcyone - Le Grand Saut (`ending_done`) | secrète jusqu'à son ouverture, facultative, BONUS FINAL, sans fin, carburant 90 |
| `bonus_ast_endless` | BONUS FINAL - Asteroids | FINAL BONUS - Asteroids | Asteroids | Alcyone - Le Grand Saut (`ending_done`) | secrète jusqu'à son ouverture, facultative, BONUS FINAL, sans fin |
| `bonus_gd_endless` | BONUS FINAL - Gardiens | FINAL BONUS - Guardians | vagues | Alcyone - Le Grand Saut (`ending_done`) | secrète jusqu'à son ouverture, facultative, BONUS FINAL, sans fin |
| `bonus_spacewar` | BONUS FINAL - Space War | FINAL BONUS - Space War | Space War | Alcyone - Le Grand Saut (`ending_done`) | secrète jusqu'à son ouverture, facultative, BONUS FINAL, sans fin |
| `bonus_swarm` | BONUS FINAL - Nuée | FINAL BONUS - Swarm | nuée | Alcyone - Le Grand Saut (`ending_done`) | secrète jusqu'à son ouverture, facultative, BONUS FINAL, sans fin |

Une mission listée dans plusieurs actes (atterrissages, raids, Sentinelles, BONUS) n'apparaît ici que dans le premier.
