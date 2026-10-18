# RELEASE, SUPERCHARGE et MOVEMENTS cycliques

Ces fonctions concernent le moteur natif Zynthian et l’éditeur Web. Elles n’ajoutent pas de nouvelles fonctionnalités REAPER.

## Choisir le moment d’avancer

Dans CONDUCTOR, **AVANCER AU** sépare le geste de passage du réglage existant « immédiat / fin de phrase » :

- **PRESS** conserve l’avancement à l’appui. Les blocs RELEASE ou SUPERCHARGE RELEASE du STEP courant se déclenchent au relâchement sans avancer une seconde fois.
- **RELEASE · tap ou charge** prépare le prochain STEP pendant l’appui et y entre au relâchement. Avant le premier lancement, le STEP préparé est 01. Un tap court peut donc lancer 01, puis un maintien suivi d’un release chargé peut lancer 02. Les couches PRESS du STEP entrant jouent lors de son admission. Les couches HOLD/LONG HOLD du futur STEP ne sont pas jouées pendant sa préparation.
- Si « fin de phrase / cycle » est sélectionné sur le STEP sortant, le passage est mis en attente. Le niveau de charge et le type de release sont conservés jusqu’à cette frontière ; les appuis supplémentaires n’empilent pas une file de STEPS.

RELEASE reste utilisable après un appui long si aucun SUPERCHARGE n’est configuré. Dès qu’un STEP possède une configuration SUPERCHARGE ou un bloc SUPERCHARGE RELEASE, le seuil distingue release court et chargé ; le chargé remplace le court. STOP, PANIC et le remplacement du patch annulent les préparations. Un doublon de release ne redéclenche rien.

RELEASE et SUPERCHARGE RELEASE peuvent révéler une PHRASE avec son CC/fade configuré. Ils utilisent LATCH ; GATE n’est pas compatible avec un déclenchement effectué alors que le bouton est déjà relâché.

## Affecter la charge

**SUPERCHARGE · TEMPS DU PATCH**, dans l’en-tête du Conductor, règle le seuil et la durée de pleine charge communs à tous les Conductor de ce patch. Le bouton **SUPERCHARGE STEP n** contient les affectations multiples et deux sélecteurs **HÉRITER / OVERRIDE** : chaque temps hérite par défaut de la valeur du patch, ou peut être remplacé pour ce STEP indépendamment de l’autre. Les anciennes valeurs locales explicites restent des overrides. Les blocs et affectations sont placés dans le STEP où ils doivent être joués : STEP courant sans avancement au release, STEP suivant avec avancement au release.

**ADD CHARGE BINDING** cible explicitement un bloc : vélocité, TIME DECAY ou VELOCITY DECAY de sa PHRASE ; durée ou amplitude de son MOVEMENT. Ces valeurs restent locales à son démarrage, sans modifier la source. Un bloc déjà parti à l’appui ne reçoit pas rétroactivement une nouvelle durée au release ; utiliser un TRIG de release ou l’entrée dans le prochain STEP pour ce cas.

**ADD PARAMETER CHARGE** cible un paramètre disponible d’un instrument/transformateur, y compris VOL/PAN Zynthian pour les instruments liés. Ces affectations règlent le paramètre au release chargé via le chemin de contrôle natif existant.

Chaque affectation possède deux bornes et un facteur. La fraction de charge est `clamp(temps_appui / durée_pleine_charge, 0, 1)`. La progression de l’affectation est `clamp(fraction × facteur, 0, 1)` ; les bornes peuvent être inversées pour renverser l’effet. Le facteur est limité à 0–16. Il permet notamment d’atteindre plus vite la borne finale. Les valeurs sont validées puis limitées au range réel. Le registre assure les conversions des paramètres, y compris logarithmes, crans et choix discrets. Les cibles manquantes et les plages invalides sont refusées, sans application silencieuse à une autre destination.

La durée locale d’un MOVEMENT est bornée à .001–86400 secondes. Son amplitude est 0–1 autour de sa valeur REPOS : zéro donne REPOS, un conserve toute la courbe. Les valeurs de sortie restent normalisées entre 0 et 1, donc entre 0 et 127 pour un CC. Les cibles générales passent par le système d’arbitrage des paramètres ; une nouvelle prise de contrôle respecte ses règles habituelles.

Le bouton **TEST CHARGE** utilise les vrais événements d’appui/relâchement, avec les mêmes seuils natifs que la source NOTE/CC physique. La carte montre la progression et le STEP préparé lorsqu’une charge est configurée. Les timings et la jauge ne sont pas calculés par un chronomètre du navigateur.

## Courbes et lecture des MOVEMENTS

- **ALT + glisser** bombe un segment ; **BEND** sous POINTS / PRECISION permet son édition numérique. Affichage, aperçu et moteur utilisent la même courbure. Les anciens points `[x,y]` restent valides ; `[x,y,bend]` conserve une courbure comprise entre -.98 et +.98. HOLD garde ses paliers sans supprimer les courbures enregistrées.
- **SELECT IN + OUT**, ou les cases individuelles, sélectionne les points. **ALIGN SELECTED** les place à la hauteur moyenne de la sélection. Déplacer un point sélectionné, ou modifier sa valeur Y, déplace verticalement le groupe en respectant les limites. IN et OUT gardent leurs positions temporelles 0 et 1. CLEAR SELECTION libère ce déplacement groupé.
- **PLAY MODE** : ONCE, LOOP ou PING-PONG. La durée de PING-PONG couvre un aller-retour complet. LOOP revient directement au début ; pour éviter un saut, dessiner une jonction compatible entre les deux extrémités. Aucun glide de jonction supplémentaire n’est implicite.
- **MAINTIEN** est indépendant : LIBRE ou PENDANT L’APPUI. Au relâchement, un MOVEMENT maintenu, même cyclique, rejoint REPOS pendant RELEASE. STOP/PANIC restent immédiats. Un nouveau MOVEMENT sur la même cible prend la main selon sa politique DIRECT/SOFT_RESTART ; l’ancienne boucle ne reprend pas la cible.

## Vérification reproductible

Avec le runtime et le binaire natif déjà construits, sans installer de paquets sur le Zynthian :

```sh
bash scripts/movement-test.sh
PYTHONPATH=tests python3 -m unittest \
 test_supercharge_native.Supercharge.test_release_current_and_advance \
 test_supercharge_native.Supercharge.test_charge_duration_factor_and_short_exclusion \
 test_supercharge_native.Supercharge.test_registered_parameter_bounds_and_quantization \
 test_supercharge_native.Supercharge.test_midi_charge_and_panic_cancellation \
 test_supercharge_native.Supercharge.test_release_after_long_press_without_charge \
 test_supercharge_native.Supercharge.test_charge_waits_for_exact_master_boundary \
 test_supercharge_native.Supercharge.test_patch_charge_defaults_and_step_overrides \
 test_supercharge_native.Supercharge.test_bent_cycles_persist_and_stop
```

`HEADLESS_BINARY` et `HEADLESS_SOURCE` peuvent désigner un candidat apparié. Les tests utilisent un moteur natif privé et le vrai serveur HTTP, sans JACK ni données du musicien. Ils ne certifient pas le matériel physique de la pédale. Le cas de frontière exacte protège aussi le passage de STEP lorsque la fin du maître tombe entre deux callbacks.
