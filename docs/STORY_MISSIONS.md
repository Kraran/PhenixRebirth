# Phenix Rebirth — Cahier missions (prototype 2.0)

Source de vérité pour le mode Histoire.  
Arcade 1.4.3 ne lit pas ce fichier.

Convention :
- `id` stable (jamais renommer sans migration `story.json`)
- `prereq` = ids de missions **réussies**
- `flags` = booléens persistants
- `unlock_shop` = le joueur **peut acheter** cet palier (il paie encore avec les points)
- `grant` = one-shot immédiat (pas d’achat)
- `stages` / `roster` = ce que la run a le droit de faire spawn
- `brief` / `win` = texte illustré (i18n plus tard, FR ici)

Points de la run → `story.credits` (argent hangar).

---

## Flags globaux

| flag | défaut | devient true |
|---|---|---|
| `dome_online` | false | `ch1_finale` |
| `phenix_owned` | false | `ch2_finale` |
| `paint_shield_green` | false | `ch1_bonus_1` |
| `paint_shield_violet` | false | `ch1_bonus_2` |
| `paint_phenix_blue` | false | `ch2_bonus_1` |
| `paint_phenix_gold` | false | `ch2_bonus_2` |
| `bestiary_s1` … `bestiary_s5` | s1 true | missions bestiaire |
| `wall_tier` | `instant` | `slow` après Élec 1 · `immune` après Élec 2 |
| `chapter` | 1 | montée après finale de chapitre |

`wall_tier` ne s’applique qu’au **Shield dont le dôme est en ligne** ?  
Décision prototype : la résistance électrique est une propriété **du pad Shield**. Le Phenix a sa propre ligne au ch.3.

---

## Hangar (rappel)

| slot | coque | dispo |
|---|---|---|
| 0 | Shield | dès le tuto |
| 1 | Phenix | après `phenix_owned` |

Inventaire **par slot** : vies achetées, palier vitesse, (Shield) durée / latence dôme, teinte.

Départ slot 0 :
- vies 1 (palier acheté = 1)
- vitesse 60 %
- dôme offline
- `wall_tier = instant`
- teinte rouge (défaut Shield)

---

## Carte — forme

Arbre gauche → droite, 3 rails au ch.1 :

```
[ch1_sortie]──[best_s2]──[best_s3]──[best_s4]──[best_boss]
      │                                                      \
      ├──[speed_80]──[speed_100]                               [ch1_finale]
      ├──[life_2]──[life_3]                                   /
      └──[elec_1]──(dôme requis)──[elec_2]──[ch1_bonus_1]──[ch1_bonus_2]
```

Nœud : `locked` / `open` / `cleared`.  
Clic `open` → brief → run.  
`cleared` relançable (farm points) sauf mention `once`.

---

## Chapitre 1 — Le Shield

### ch1_sortie
- titre : Première sortie
- kind : story
- prereq : —
- stages : `[1]`
- roster : `[bird_s1]`
- modifiers : `dome=off`, `lives=save`, `speed=save`
- grant : `bestiary_s1`
- unlock_shop : `speed_60` (déjà actif), `lives_1` (déjà actif)
- unlock_nodes : `ch1_best_s2`, `ch1_speed_80`, `ch1_life_2`, `ch1_elec_1`
- brief : Dernier Shield EDF. Dôme grillé. Un tir. Une vie. Les Avioïdes sont déjà dans le puits.
- win : Tu ramènes le Shield. Le hangar enregistre la signature des éclaireurs.

### ch1_best_s2
- titre : Bestiaire — Éclaireurs sombres
- kind : bestiary
- prereq : `ch1_sortie`
- stages : `[1, 2]`
- roster : `[bird_s1, bird_s2]`
- grant : `bestiary_s2`
- unlock_nodes : `ch1_best_s3`
- brief : Nouvelle signature. Plus denses, double tir. Identifie, compte, rentre.
- win : Fiche « oiseau lvl 2 » ouverte.

### ch1_best_s3
- titre : Bestiaire — Gargouilles
- kind : bestiary
- prereq : `ch1_best_s2`
- stages : `[1, 2, 3]`
- roster : `[bird_s1, bird_s2, garg_s3]`
- grant : `bestiary_s3`
- unlock_nodes : `ch1_best_s4`
- brief : Plus des oiseaux. Viser le corps. Les ailes reviennent.
- win : Fiche gargouille lvl 3 ouverte.

### ch1_best_s4
- titre : Bestiaire — Harpies violettes
- kind : bestiary
- prereq : `ch1_best_s3`
- stages : `[1, 2, 3, 4]`
- roster : `[bird_s1, bird_s2, garg_s3, garg_s4]`
- grant : `bestiary_s4`
- unlock_nodes : `ch1_best_boss`
- brief : Même bête, autre couleur, plus vite. Complète la fiche.
- win : Fiche gargouille lvl 4 ouverte.

### ch1_best_boss
- titre : Bestiaire — Porte-essaim
- kind : bestiary
- prereq : `ch1_best_s4`
- stages : `[1, 2, 3, 4, 5]`
- roster : `all_known` (les 5 types)
- grant : `bestiary_s5`
- unlock_nodes : `ch1_finale` (si dôme encore off)
- brief : La soucoupe n’est pas un roi. C’est un dock. Perce-la. Reviens avec un schéma de générateur.
- win : Fiche boss ouverte. Le hangar peut parler réparation.

### ch1_speed_80
- titre : Banc d’essai — 80 %
- kind : trial
- prereq : `ch1_sortie`
- stages : `[1]`
- roster : `[bird_s1]`
- unlock_shop : `speed_80`
- brief : Le réacteur accepte une seconde pompe. Prouve que tu tiens la ligne.
- win : Atelier : vitesse 80 % achetable.

### ch1_speed_100
- titre : Banc d’essai — 100 %
- kind : trial
- prereq : `ch1_speed_80`
- stages : `[1, 2]`
- roster : `[bird_s1, bird_s2]` si `bestiary_s2` sinon `[bird_s1]`
- unlock_shop : `speed_100`
- brief : Régime de conception. Ne grille pas la pompe.
- win : Atelier : vitesse 100 % achetable.

### ch1_life_2
- titre : Second harnais
- kind : trial
- prereq : `ch1_sortie`
- stages : `[1]`
- roster : `[bird_s1]`
- unlock_shop : `lives_2`
- brief : Un siège de rechange. L’EDF n’en fabrique plus. Récupère-le.
- win : Atelier : 2 vies achetable.

### ch1_life_3
- titre : Trois souffles
- kind : trial
- prereq : `ch1_life_2`
- stages : `[1, 2]`
- roster : known birds only
- unlock_shop : `lives_3`
- brief : Plus que trois harnais dans tout le hangar. Gagne-les.
- win : Atelier : 3 vies achetable.

### ch1_elec_1
- titre : Électrique 1
- kind : hazard
- prereq : `ch1_sortie`
- stages : `[1]`
- roster : `[bird_s1]`
- modifiers : `walls=instant` pendant la mission (on subit encore le défaut) + orages visuels
- grant : `wall_tier = slow` **après victoire** (ralentissement + mort si contact long — règle Shield 1.4.3)
- unlock_nodes : `ch1_elec_2` si `dome_online`
- brief : Les bords du puits sont sous tension. Tiens la ligne sans les lécher.
- win : Le Shield apprend à encaisser une fraction de seconde. Toujours mortel si tu insistes.

### ch1_elec_2
- titre : Électrique 2
- kind : hazard
- prereq : `ch1_elec_1`, `ch1_finale`
- stages : `[1, 2]`
- roster : known
- modifiers : `walls=slow` pendant la mission
- grant : `wall_tier = immune`
- brief : Recalibre l’isolant. Les murs ne doivent plus être une sentence.
- win : Immunité murs sur ce pad Shield.

### ch1_finale
- titre : Générateur
- kind : finale
- prereq : `ch1_best_boss`
- stages : `[1, 2, 3, 4, 5]`
- roster : `all_known`
- modifiers : `dome=off` jusqu’à la victoire
- grant : `dome_online`, `chapter = 2` (hub ch.2 se révèle, carte ch.1 reste farmable)
- unlock_shop : `dome_duration_60`, `dome_latency_100` (paliers 80/100 et latency 50/0 = missions courtes ch.1b ou achat après essais — **TBD**, voir annexes)
- unlock_nodes : `ch1_elec_2`, `ch1_bonus_1` si bestiaire 5/5
- brief : Deux générateurs de soucoupe. Branche-les sur le dôme ou rentre à pied.
- win : Le dôme s’allume. B n’est plus mort. Chapitre 1 clos.
- once : false (farm ok) mais `grant` déjà true ne se rejoue pas

### ch1_bonus_1
- titre : Peinture verte
- kind : bonus
- prereq : `bestiary_s5`, `ch1_finale`
- stages : `[1, 2, 3, 4, 5]`
- roster : all
- grant : `paint_shield_green`
- unlock_nodes : `ch1_bonus_2`
- brief : Le hangar relâche une teinte de série. Mérite-la.
- win : Teinte verte débloquée sur le pad Shield.

### ch1_bonus_2
- titre : Peinture violette
- kind : bonus
- prereq : `ch1_bonus_1`
- stages : `[1, 2, 3, 4, 5]`
- roster : all
- grant : `paint_shield_violet`
- brief : Dernière bombe du stock EDF. Pas un cadeau.
- win : Teinte violette débloquée.

### Annexes ch.1 — paliers dôme (à préciser)

Pas encore de missions dédiées. Prototype atelier :

Après `dome_online`, achetable tout de suite :
- durée 60 % (1.2 s si base arcade 2.0 s)
- latence +100 % (CD 10 s si base 5 s)

Pour ouvrir 80/100 % et +50/0 % : soit 2 mini-trials `ch1_dome_dur`, `ch1_dome_cd` (copies de speed_80), soit achat libre. **À trancher.**

---

## Chapitre 2 — Le Phenix légendaire (squelette)

Carte nouvelle colonne, slot 1 verrouillé jusqu’à `ch2_finale`.

| id | prereq | grant / unlock |
|---|---|---|
| `ch2_signal` | `ch1_finale` | ouvre la piste proto |
| `ch2_best_*` | reprise bestiaire si besoin farm | — |
| `ch2_speed_80/100` | `ch2_signal` | shop vitesse **pad Phenix** |
| `ch2_life_2/3` | `ch2_signal` | shop vies **pad Phenix** |
| `ch2_finale` | `ch2_signal` + condition TBD (boss ?) | `phenix_owned`, mode Phenix **on** |
| `ch2_bonus_1` | bestiaire 5/5 + finale | `paint_phenix_blue` |
| `ch2_bonus_2` | bonus 1 | `paint_phenix_gold` |

Start pad Phenix après grant : vies 1, vitesse 60 %, jauge Phenix **on** (durée/cap à 60 % jusqu’au ch.3).

---

## Chapitre 3 — Final (squelette)

| id | prereq | grant / unlock |
|---|---|---|
| `ch3_cap_80` / `ch3_cap_100` | `ch2_finale` | shop `phenix_cap_80/100` |
| `ch3_elec_1` | `ch2_finale` | `phenix_wall_tier = slow` |
| `ch3_ending` | caps + TBD | crédits Histoire |

Reine vs relais : **non tranché**.

---

## Schéma `story.json` (cible code)

```json
{
  "version": 1,
  "chapter": 1,
  "credits": 0,
  "flags": {},
  "cleared": [],
  "bestiary": { "bird_s1": { "kills": 0, "known": true } },
  "slots": [
    { "id": "shield", "owned": true, "tint": "red",
      "lives": 1, "speed": 60, "dome": false,
      "dome_dur": 60, "dome_cd": 200, "wall": "instant" },
    { "id": "phoenix", "owned": false, "tint": "argent",
      "lives": 1, "speed": 60, "phenix": false, "phenix_cap": 60, "wall": "instant" }
  ],
  "selected_slot": 0
}
```

---

## Écran Bestiaire (données)

Chaque fiche :
- `id` roster
- `known` (silhouette si false)
- `kills`
- `pts` Normal (10 / 20 / 30 / 40 / 500)
- sprite déjà en aide arcade

Tués seulement si l’espèce est dans le `roster` de la mission (un oiseau lvl 2 tué avant unlock ne compte pas — il ne spawn pas).

---

## À trancher avant le code combat

1. Paliers dôme 80/100 % : missions ou shop libre après finale ?
2. `ch2_finale` : quelle mission concrète (raid proto + boss) ?
3. Ending ch.3 : Reine-essaim ou relais ?
4. Farm : missions cleared rapportent-elles encore 100 % des points ?
5. Élec 1 avant le dôme : le `wall_tier=slow` s’applique-t-il **sans** dôme ? (prototype : oui, sur la coque)
