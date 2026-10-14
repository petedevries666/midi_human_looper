# Qualification temps réel MOVEMENT — PR #62

Base exacte : `b4113da7ba8316be682ebb1959a7339ce971ca0c`. Branche de diagnostic
`diag/movement-realtime`, empilée sur #62. Aucune règle musicale, capacité moteur,
interface, persistance, installation ou configuration JACK n'est modifiée.
Aucun déploiement, merge ou début de phase G.

## Résultat musical

**L'usage live normal n'est pas encore qualifié.** Les mesures représentatives
sans navigateur ont une faible consommation CPU habituelle, mais des XRUN et
certains dépassements ponctuels existent aussi en charge légère. Un seul run
STRESS sans XRUN ne démontre pas que NORMAL est stable. Les répétitions sont
conservées ; elles ne sont pas remplacées par le meilleur résultat.

Les tests utilisent le vrai moteur EEL/ysfx et ses ports JACK, pas une simulation
MIDI. Le backend JACK **dummy, non temps réel**, est une simulation de périphérique,
à 48 kHz, dans un Cloud partagé x86-64. Cela ne qualifie ni ARM64, ni le pilote
Zynthian, ni Helix, ni une sortie DIN/USB physique.

## Conditions exactes du pic 26,85 ms à 512 frames

Fichier : `evidence/movement-realtime/matrix/512/callback.csv.gz`, ligne dont
`sample=490496`, `entry_ns=332040049483610`.

- Pas de navigateur, pas de serveur HTTP, pas d'édition Web.
- Scénario `independent`, 1,489 s après son début. Trois MOVEMENTS actifs observés.
- Taux demandé **100 Hz**, trois CC indépendants CH1/CC10, CC11, CC12.
  Courbes linéaires 0→127 sur 60 s ; déduplication entière active.
- Les trois admissions utilisent l'API native PREVIEW (`op=46`) en début de phase.
  Ce n'est donc pas un profil concert entièrement piloté par MIDI.
- **Zéro commande consommée dans ce callback**. Pas de SAVE/LOAD/édition à cet
  instant ; le script ne transmet aucun CC de pédale dans cette phase.
- La PHRASE précédente a été arrêtée par PANIC avant cette phase. Le nombre réel
  de PHRASES actives n'était **pas enregistré** dans cette première version de
  trace : ne pas présenter l'intention « zéro PHRASE » comme un comptage observé.
- Les débits exacts notes/CC dans cet intervalle n'étaient pas enregistrés non plus.
  100 Hz est la cadence d'évaluation/émission possible, pas le débit effectivement
  envoyé après déduplication. Ne pas inventer les débits manquants.

Mesure complète : **26,849 ms elapsed / 2,437 ms CPU**. Le segment d'entrée/récupération
prend 24,476 ms elapsed pour 0,068 ms CPU. L'appel `ysfx_process_float` prend
2,350 ms CPU. Les deux enveloppes MOVEMENT cumulées prennent 0,00686 ms CPU
(l'enveloppe post-EEL contient aussi des opérations de contrôle). Environ 24,412 ms
sont hors CPU, principalement dans le premier segment. Cela distingue ce pic d'un
calcul MOVEMENT de 26 ms ; cela **n'identifie pas à lui seul** la cause système exacte
(préemption, attente interne, activité du noyau/hyperviseur).

Le host ne lance pas `@gfx`. EEL exécute son traitement musical `@block`, mais les
branches individuelles de ce code ne sont pas profilées : un nettoyage différé ne
peut pas être exclu simplement parce que le compteur de commandes vaut zéro.

## Profils concert réellement mesurés

Les données sont préparées et LOADées **avant** la fenêtre de mesure. Les messages
PANIC préparatoires sont drainés, puis un temps de stabilisation est laissé.
Pendant les 12 secondes mesurées : **aucun HTTP, navigateur, SAVE/LOAD, PREVIEW,
édit ni requête de lecture de l'état**. Les commandes sont des Note On/Off et CC
injectés dans le vrai port JACK. L'état est lu avant/après ; PANIC de nettoyage
intervient après la fenêtre. Le transport JACK n'est pas lancé : ces PHRASES/MOVEMENTS
emploient l'horloge native en samples, comme l'exécution free-time autonome.

- **LIGHT** : un STEP PHRASE + MOVEMENT ; PRESS à 0/4/8 s, RELEASE environ 25 ms
  après chacun. PHRASE ONCE de 2 s, 2 attaques/s pendant sa lecture ; MOVEMENT
  rampe de 4 s, 25 Hz, GLIDE parallèle 0,2 s. Au plus une instance PHRASE et un
  MOVEMENT. La PHRASE finit naturellement avant le PRESS suivant.
- **NORMAL** : trois PHRASES ONCE distinctes de 20 s (2 attaques/s chacune),
  deux MOVEMENTS triangulaires de 20 s à 25 Hz. Premier STEP : trois PHRASES +
  deux MOVEMENTS. STEPS suivants : remplacement des MOVEMENTS uniquement, les
  trois PHRASES continuent. Trois PRESS à 0/4/8 s, aucun HOLD. Une pédale **simulée
  à l'entrée JACK** transmet CH1/CC20 pendant environ une seconde, au plus 25 valeurs.
  Elle annule effectivement le MOVEMENT sur cette cible ; le STEP suivant peut le
  relancer. Il n'y a donc pas toujours deux MOVEMENTS actifs.
- **STRESS** : douze sources PHRASE / douze instances ONCE, quatre notes par
  attaque à 8 attaques de chordes/s/source ; huit MOVEMENTS à 100 Hz, 81 points
  triangulaires sur 20 s. Rafales supplémentaires de 16 Note On puis Off, quatre
  fois par seconde, sur CH2. Même pédale et trois PRESS. Le dernier PRESS essaie
  de réadmettre les PHRASES quand les douze instances sont occupées : refus propre
  attendu, sans recyclage global. Les Note Off partagées sont gouvernées par
  l'ownership, donc leur débit n'est pas déduit du nombre d'attaques.

Voir [table complète des profils](evidence/movement-realtime/live-tables.md),
[les répétitions](evidence/movement-realtime/repeats.md), et les traces/captures
`live/<buffer>-<profil>/{callback.csv.gz,midi.json,summary.json}`.
Les débits sont comptés sur les écritures MIDI **acceptées par JACK**, pas estimés
à partir des points de courbe. `Note On+Off/s` compte les messages ; `Note On/s`
compte les attaques non nulles. Les comptes PHRASE/MOVEMENT sont autoritatifs.

## Attribution, limites et défauts reproduits

La mesure historique `maxCallbackUs` commence **après** la lecture MIDI, mesure
elapsed et inclut les commandes/configuration. Ce n'est ni le callback complet,
ni du CPU pur. Les anciens pics 30,013 / 104,684 / 265,959 ms n'ont pas ces traces
complémentaires : leur origine exacte reste inconnue. Les nouvelles mesures ne
permettent pas une attribution rétroactive certaine.

La matrice initiale inclut explicitement des commandes de configuration, PREVIEW,
les rafales, la télémétrie et PANIC. Elle n'est pas assimilée au profil concert.
Voir [buffers et charges](evidence/movement-realtime/tables.md). À 128 frames,
80,670 ms CPU sont mesurées pendant l'intervalle PANIC, dont 79,126 ms dans
`ysfx_process_float`. À 512, un autre callback consomme 18,192 ms CPU, dont
6,782 ms dans les commandes et 11,327 ms dans l'enveloppe performance/cleanup.
Le bridge PANIC appelle `sw_stop_phrases`, `reset_note_runtime`, l'annulation
Snapshot, puis pose `panic_pending` ; `@block` et `cleanupChain` possèdent des
chemins de nettoyage. **La trace de région ne permet pas d'attribuer tout ce coût
à une fonction EEL particulière.** Aucun chemin n'est optimisé sans cette preuve.

Un premier NORMAL à 512 montre aussi 23,082 ms CPU, sans commande ni entrée MIDI,
dont 21,188 ms dans l'enveloppe performance/cleanup avant DSP. Ce pic n'est pas
expliqué par une édition Web. Sa fonction interne précise reste inconnue.
Le temps CPU représente la comptabilité du noyau, pas un compteur d'instructions
matérielles exécutées. La dernière série ajoute `getrusage(RUSAGE_THREAD)` : temps user/system, défauts
mémoire et changements de contexte. Aucun défaut de page majeur n'y est enregistré ;
les pics les plus lents ne comportent pas nécessairement de défaut mineur.
Cela ne démontre ni une cause unique Cloud, ni une saturation intrinsèque MOVEMENT.

Comparaison indépendante : le binaire **original #62 sans traceur** a été recompilé
et exécuté sur NORMAL/STRESS, 512/256, avec le même injecteur/observateur acyclique.
`pr62-live` conserve les captures, compteurs et empreinte binaire. NORMAL montre
10/6 notifications XRUN à 512/256. Son maximum historique 21,023/5,705 ms est
**cumulatif, préparation comprise**, et ne localise pas le pic dans la fenêtre live.
Les deltas de compteurs couvrent aussi la lecture de l'état après la fenêtre.
La comparaison confirme la préexistence des symptômes ; elle ne remplace pas le
profilage CPU complet du binaire instrumenté.

Des problèmes de mesure ont été identifiés, sans suppression des échecs :

1. La première préparation de matrice exigeait à tort `status=ok` d'une capture
   `op=4`, qui renvoie directement le format PATCH. Correction du script seulement ;
   l'échec et ses traces avant toute phase musicale sont conservés.
2. Le recorder initial de 16 384 événements saturait sous STRESS (exit 6). Un
   recorder de diagnostic de 65 536 événements couvre les ~18 000 messages/run.
   Cela n'augmente **aucune capacité du moteur**. L'ancien probe conserve son défaut
   de 16 384 pour les suites existantes. La qualification sépare également
   injecteur et observateur JACK, évitant leur boucle de dépendance, et pré-touche
   les pages d'observation avant activation.

3. La suite globale finale a d'abord échoué sur `engine disconnected` dans la
   fixture CONDUCTOR navigateur. Son log et exit 1 restent conservés. Les stderr
   JACK/moteur/Web étaient des pipes non drainés : ils sont désormais des fichiers
   hors callback, conservés en diagnostic. Le même test passe avec #62 original
   et le binaire instrumenté. La cause de la déconnexion initiale reste inconnue ;
   ces reruns ne démontrent pas rétrospectivement que le pipe en était responsable.

Des runs STRESS ont échoué sur l'ordre des événements **au port observé**, y compris
une version acyclique. Ils sont conservés (`live-cyclic`, `live-acyclic-v2`) avec
exit 1. Leur origine n'est pas résolue. La dernière série garde l'assertion et
compte aussi les écritures directement dans le callback MBMF : aucun ordre
inversé écrit n'y est détecté et les captures passent. Cela ne prouve pas que
les échecs précédents étaient seulement des artefacts, ni que le problème est clos.

## Instrumentation et reproduction

`--rt-trace FILE.csv` est opt-in. Dix régions wall/thread CPU ; compteurs MIDI
réellement écrits, instances/sources PHRASE, MOVEMENTS, refus, overflow, XRUN,
frame JACK et ressources du thread. Ring SPSC préalloué de 4096 records, aucune
allocation/écriture fichier/attente/verrou dans le callback. Un consommateur
séparé écrit le CSV. Saturation : seules les traces sont refusées et comptées
(`# dropped=N`), jamais des événements MIDI. Les fichiers de qualification ont
un footer ; les tests vérifient la conservation du nombre de records même en
saturation. Le coût du traceur est mesuré par `tests/realtime_trace.cpp` ; les
mesures comprennent son coût. La publication et le dernier appel diagnostic
`getrusage` ne font pas partie du chronométrage total.

Les enveloppes controller/transport, post-EEL/MOVEMENT et émission/observation
regroupent plusieurs opérations ; les comparer comme telles. Le temps réseau,
JSON et filesystem du worker n'est pas mesuré comme CPU callback. Les opérations
qui lui sont demandées apparaissent dans `commands`; une analyse de fonctions
internes nécessiterait une instrumentation ciblée supplémentaire.

Dans ce Cloud, réutiliser l'environnement existant :

```sh
source /tmp/mbmf-b-env.sh
scripts/headless-build.sh
scripts/movement-realtime-test.sh --output /tmp/mbmf-matrix --seconds 3
python3 scripts/analyze-realtime.py /tmp/mbmf-matrix
# exit 2 = gate temps réel non qualifié ; ne pas transformer en PASS.
MOVEMENT_RT_TEST=tests/movement_live_profiles.py scripts/movement-realtime-test.sh \
  --output /tmp/mbmf-live --seconds 12
MOVEMENT_RT_TRACE=/tmp/mbmf-functional.csv "$TEST_PYTHON" scripts/combined-test.py \
  --native --jack --browser chromium --timeout 240
```

Hors de ce Cloud, employer les dépendances et variables documentées dans AGENTS.md
et `scripts/headless-setup.sh`. Ces scripts de qualification démarrent uniquement
un serveur **dummy privé desktop** ; ne pas les lancer sur le Zynthian en service.
Le script de mesure sépare les assertions fonctionnelles du gate RT : un exit 0
fonctionnel n'est **pas** une qualification deadline/XRUN. `qualification.exit=2`
pour la matrice initiale. Aucun seuil ni test musical existant n'est affaibli.

## Qualification physique courte, après revue humaine

Aucune installation automatique. Utiliser uniquement un SHA approuvé et les
backups/rollback existants ; conserver le runtime physique actuel tant que cet
accord n'existe pas. Ne changer ni JACK, ni services OS, ni LUMAZ.

1. Le flag est actuellement un argument CLI natif ; l’adaptateur Oram ne l’expose
   pas encore et n’est pas modifié dans cette PR. La qualification native instrumentée
   exige un lancement manuel préparé/revu, à la place de l’instance MBMF de test,
   pas une seconde instance concurrente. Dans ce lancement, conserver les arguments/ports
   habituels et ajouter `--rt-trace /tmp/mbmf-v4.csv`. Une seule instance MBMF,
   synthé de test, volume modéré ; sauvegarde du projet avant test. Le flag ne
   modifie ni projet ni routing. Vérifier la révision affichée.
2. Préparer LIGHT/NORMAL en studio, SAVE, puis fermer le navigateur. Utiliser
   Helix pour les trois PRESS et une seconde de pédale sur le CC choisi. Écouter
   notes et paramètres, relever les CC côté synthé/monitor MIDI.
3. Mesurer 15 minutes à 512 frames, puis 256 seulement si le premier est propre
   et dans une session de qualification prévue. Relever rate/buffer, CPU/RAM,
   notifications XRUN, gaps, deadlines et compteurs. Une panne ne justifie jamais
   de désactiver les guards. Ne pas changer le buffer d'un concert en cours.
4. Vérifier remplacement, prise de contrôle physique, STOP ALL PHRASES (MOVEMENT
   continue), PANIC (tout s'arrête), déconnexion navigateur/Helix et arrêt/reprise
   de transport. Confirmer aucune note bloquée ni reprise d'un propriétaire périmé.
5. Arrêter proprement la session diagnostique pour obtenir le footer, récupérer
   le CSV hors callback et revenir au lancement normal sans trace. Aucun PUSH/PULL
   ou conversion destructive pour ce test. Ne pas envoyer le STRESS virtuel sur
   une liaison DIN : ses débits dépassent les capacités usuelles de cette liaison.

**Verdicts : GO pour revue technique de #62 en draft ; GO uniquement pour un essai
de diagnostic contrôlé V4 après revue du SHA ; NO-GO pour qualification concert,
pour affirmer la stabilité live et pour démarrer G.** Restent bloquants : pics CPU
non attribués à la fonction, XRUN sans édition et erreurs d'ordre intermittentes
observées sous STRESS. Les tests fonctionnels verts ne ferment pas ces sujets.
