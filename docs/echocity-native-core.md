# Suite de V2 : ECHOCITY natif

## Statut explicite

Le host natif et le Web proposent maintenant un ECHOCITY terminal par instrument,
après les transformations POLY/MONO et la génération ARP. L’intégration reste à
qualifier sur ports JACK isolés avant installation sur le moteur musical.
Le JSFX REAPER figé reste inchangé.

Le menu des transformateurs propose « ECHOCITY — FIN DE CHAÎNE ». Ses réglages : intervalle en ms ou en temps,
décalage initial, nombre de répétitions, mélange, décroissance de vélocité,
durée des notes et sa décroissance, transposition par répétition et ping-pong
vers un autre canal. APPLIQUER valide le lot ; le bypass conserve le son direct.
La version 2 de l’extension de patch `echocity` conserve ces réglages sans
déplacer les anciennes cellules mémoire. Charger un ancien patch les retire.
Une version inconnue est refusée, sans conversion silencieuse.

DRY et WET règlent indépendamment la vélocité du direct et celle des répétitions,
de 0 à 1. Un nouvel effet démarre avec DRY=1 et WET=0,5. Modifier WET ne change
jamais DRY. La décroissance affecte seulement les répétitions successives.
La version 1 reste lisible : l’ancien mélange est converti en DRY=1−WET pour
conserver le niveau des anciens patches, puis sauvegardé en version 2 avec deux
niveaux indépendants. Le runtime conserve le direct complet en cas de refus de
la génération d’échos, comme auparavant.

La première activation exige de relâcher les notes. Le protocole reste ensuite
actif jusqu’à la fin de la session, même si le dernier effet est retiré.
Les notes directes et les échos partagent un registre de sorties : une répétition
sur une hauteur tenue réserve ensemble NoteOff et NoteOn pour être audible.
MIDI 1 ne permet pas de relâcher indépendamment deux voix de même canal/hauteur.
Les CC existants gardent leurs messages et leur ordre ; les repères privés du
journal ne quittent jamais le host. CC120/123 actualisent le registre uniquement
après réservation de leur message de sortie. Un défaut déclenche le balayage
PANIC avant réutilisation des propriétaires.

Limites : un effet par instrument, en fin de chaîne uniquement ; pas de Feedback,
Freeze ou Reverse, ni d’assignation de ses paramètres à un contrôleur/MOVEMENT.
La provenance ARP/MONO est agrégée : STOP des phrases retire les échos issus des
phrases, tandis que la porte native reste responsable de sa note directe partagée.
Le runtime réserve au plus 256 voix différées et 2048 sources ; un lot impossible
est refusé en entier et laisse la vélocité directe complète.

Qualification reproductible : `scripts/echocity-native-test.sh`, puis
`python3 tests/test_echocity_playable.py`. Le second utilise un moteur privé sans
JACK par défaut ; `ECHOCITY_JACK=1` ajoute le banc réellement connecté à ses seuls
ports de test `mbmf_d`, avec `.build/echocity-jack-probe` compilé depuis
`tests/conductor_jack.cpp` (`MBMF_TEST_ACYCLIC`, `MBMF_TEST_CAPTURE_ALL_CC`,
`MBMF_TEST_FORBID_PRIVATE_CONTROL`). Aucun port matériel n’est connecté.

## Audit et choix

La PR #28 (`feat/echocity-scheduled-events`) apporte une fondation EEL de 256 voix
et 512 événements, avec continuation terminale POLY uniquement. Elle ne contient
pas ECHOCITY et n’est pas intégrée à la branche native courante. Son checkpoint
décrit les continuations, la durée des notes sources et la propriété des sorties
comme prérequis. Depuis le gel REAPER, cette suite développe ces contrats dans
le moteur natif, sans importer les développements GUI ou migrations JSFX/Lua.

Le dispatcher actuel traite des étapes groupées et capture ARP séparément. Un
simple délai posé à la sortie MIDI perdrait l’identité des instruments et
contournerait les étapes aval. Cette PR ne présente pas cette solution comme
une chaîne arbitraire. La continuation est représentée par une identité stable ;
son raccordement aux étapes réelles reste une étape distincte.

## Noyau implémenté

`native_note_scheduler.hpp` fournit une file commune bornée à 512 événements,
256 voix différées et 256 notes sources. Une génération réserve toutes ses
attaques et toutes ses fins de notes avant admission. Les lots refusés ne sont
pas partiellement joués. L’ordre est échantillon absolu puis ordre d’admission ;
une fin au bord droit attend le bloc suivant. Une paire de durée nulle attaque
avant de relâcher.

Les sources répétées possèdent des jetons distincts et un ordre FIFO explicite.
Les domaines Source/Voice et les générations empêchent un ancien relâchement
d’agir sur une nouvelle note réutilisant le même emplacement. Instrument,
module, instance de phrase et provenance direct/phrase sont conservés. La
suppression ou le bypass peut annuler le propriétaire ciblé sans arrêter un autre.

Le registre des sorties capture hauteur, canal et branche à l’attaque. Le
relâchement utilise cette capture après une modification des paramètres aval.
Plusieurs propriétaires d’une même note partagent sa dernière fin physique.
L’admission d’un éventail de 16 sorties est atomique. Un échec de relâchement
conserve ses références et demande la récupération de l’hôte ; il ne prétend pas
qu’un PANIC a réussi. Le reset sans émission est réservé à un PANIC réellement
délivré par l’intégration.

`echocity_core.hpp` calcule des répétitions bornées : intervalle en ms ou beats,
premier décalage, nombre de répétitions 1–32, mix MIDI sec/échos par vélocité,
décroissance, gate et décroissance de gate, pas de hauteur et alternance de canal.
Les paramètres de chaque génération sont capturés. Le tempo est capturé à son
admission : modifier le tempo ne recalcule pas les événements déjà planifiés.
Sans tempo valide, une génération synchronisée est refusée. Un refus conserve
la vélocité sèche d’origine. Les limites MIDI et l’horizon de 60 secondes sont
explicites ; aucun bouclage infini n’est déduit d’une vélocité constante.

Les valeurs zéro de vélocité suppriment la génération ; elles ne deviennent pas
de fausses attaques MIDI. La sortie des hauteurs MIDI arrête la progression
plutôt que d’effectuer un wrap implicite.

## Durée en direct : limite à conserver visible

Une note tenue n’a pas encore de durée connue. Ses échos réservent un watchdog,
puis leur gate capturé est scellé au relâchement source. Si un gate raccourci
aurait déjà dû se terminer, il est relâché maintenant, jamais antidaté. Le
compteur `lateGateReleases` rend ce cas observable. Une note dont la durée est
connue avant l’attaque différée bénéficie du gate exact. La stratégie musicale
pour gates courts sur notes longues doit être qualifiée avant l’interface.

## Contrat temps réel

Pas de heap, mutex, fichiers, réseau ou dépendance au navigateur dans les
chemins d’admission/rendu/annulation. Tables et file fixes. Les callbacks ne
doivent pas réentrer dans l’ordonnanceur. Une attaque refusée ne doit avoir
commis aucune sortie ; une fin partielle conserve les références restantes pour
la prochaine tentative. L’intégration doit convertir l’alarme de récupération en
arrêt sûr et mesurer le coût sur son callback réel.

La propriété partagée coalesce les attaques de même canal/hauteur. Le contrat
de réattaque musicale pour des échos se superposant au son sec tenu reste à
trancher/tester avec les synthés. Ne pas annoncer une réattaque qui n’est pas
encore définie par la chaîne réelle.

## Validation reproductible

```sh
bash scripts/echocity-core-test.sh
SANITIZE=1 bash scripts/echocity-core-test.sh
YSFX_SOURCE=/chemin/vers/ysfx bash scripts/echocity-native-test.sh
SANITIZE=1 YSFX_SOURCE=/chemin/vers/ysfx bash scripts/echocity-native-test.sh
```

Ces programmes exécutent le vrai noyau C++ et contrôlent l’absence d’allocation
dans les chemins testés. Ils couvrent frontières de blocs, ordre, collisions,
réutilisation, surcharge atomique, durée connue/inconnue, watchdog, tempo,
captured routing, annulation par origine/module et reprises de fins refusées.
Les callbacks de sortie et l’horloge de bloc sont des bancs de test : **ce ne
sont pas des preuves de MIDI réel via ysfx/JACK ni d’écoute sur les synthés.**

Le second script ajoute une preuve différente : entrée MIDI et lecture de phrases
dans le vrai ysfx épinglé, puis observation de leurs sources et calcul d’échos
par le C++. Le MIDI sec émis par ysfx est inspecté ; les échos produits par le
C++ restent dans un récepteur de test. Aucun serveur JACK ni synthé supplémentaire
n’est lancé. Les cadences 44,1 kHz / 512 et 48 kHz / 128 sont exercées.

## Raccordement des sources natives

`native_echo_sources.py`, appelé uniquement par le générateur natif, ajoute un
journal borné à 1 024 événements. Il est désactivé par défaut. Le fichier JSFX
REAPER et les dimensions/adresses de la mémoire sérialisée restent inchangés.
Sa page de travail commence à 29 000 000, après les autres pages natives et
dans les 33 554 432 cellules de la VM. Il ne doit pas être sérialisé.

Les événements POLY/MONO sont capturés après leur transformation et avant la
coalescence physique des notes, avec instrument stable, origine, identité de
phrase, canal, hauteur, vélocité et position dans le bloc. Les relâchements de
phrases passent aussi par les destinations capturées dans leur registre existant.
La fin normale d’une phrase scelle les gates sans couper la traîne ; un arrêt
explicite, une suppression d’instrument ou un reset annulent le périmètre visé.
Les suppressions hors DSP restent en attente pour le prochain bloc. Un PANIC
dans le bloc conserve sa position au lieu d’être antidaté au début du bloc.

`echocity_source_journal.hpp` valide un bloc entier avant tout callback, puis
trie par position et ordre de génération. Un débordement ou une ligne corrompue
refuse le bloc et demande la récupération : aucune fin perdue n’est ignorée.
`echocity_source_bridge.hpp` associe les sources répétées en FIFO et applique
ces cycles de vie au vrai ordonnanceur. Le lecteur doit pré-lier les cellules
au démarrage avant activation, et acquitter les curseurs seulement après succès.
L’admission et les callbacks de sortie doivent propager leurs propres refus à
la récupération du host ; la validation du journal ne réserve pas tout le MIDI
physique d’un bloc. Les tests du journal et du pont vérifient l’absence d’allocation.
Les sorties, y compris celles d’une annulation ponctuelle, doivent être placées
avec leur `Event.sample` absolu relativement au début du bloc du host.
Un défaut de sortie existant du VM (`instance_output_fault`) doit également
invalider le traitement musical du bloc : observer une attaque logique avant
émission physique ne prouve pas que son admission MIDI a réussi.

Ce raccordement observe les frontières POLY/MONO et les attaques/fins réellement
générées par l’ARP. Il ne fournit pas de continuation à n’importe quel endroit
de la chaîne : l’effet musical proposé ici est terminal.

## Suite après le premier module terminal

- Qualifier le MIDI réellement émis et la restauration d’anciens patches avant
  installation musicale. L’écoute et Firefox sur le Pi restent à qualifier.
- Raccorder une continuation réelle par identité stable aux étapes de la chaîne
  pour permettre d’autres positions et plusieurs effets.
- Ajouter les descripteurs d’assignation aux contrôleurs/MOVEMENTS.
- Étendre ensuite Feedback/Freeze, parcours, taps et Reverse conformément au
  checkpoint #28 ; aucun de ces modes n’est annoncé livré par ce noyau.

## Routage WET multicanal

Le carrier v4 ajoute CYCLE (canaux cochés dans l'ordre), RANDOM (tirage par
répétition, avec option sans répétition consécutive dans une série) et PATTERN
(liste de 1 à 16 canaux, doublons autorisés, répétée si nécessaire). Les modes
de lecture FORWARD, REVERSE ALL, ALTERNATE et RANDOM CHAOS restent indépendants.
Le routage du DRY ne change pas. Un seul canal sélectionné reste utilisable en
RANDOM, même si l'option sans répétition est cochée.

Chaque répétition conserve son canal jusqu'au Note Off, même après modification
des réglages. Toutes les notes d'un fragment partagent la destination choisie
pour cette répétition ; FORWARD partage ce choix sur une fenêtre INTERVALLE sans
retarder les attaques. Les canaux choisis doivent être routés dans Zynthian.
Les anciens carriers v1/v2/v3 gardent exactement FIXE / PING-PONG.

## Extension MIDI par fragments

LECTURE propose FORWARD (comportement HARRIS existant), REVERSE ALL,
ALTERNATE et RANDOM CHAOS. Ces modes réordonnent les attaques MIDI ; ils
ne retournent pas la forme d'onde du synthé.

Pour les trois nouveaux modes, INTERVALLE sert aussi de durée de fragment,
en ms ou en temps. Le fragment démarre à sa première attaque et se clôt
après cette durée, même sans nouvelle note entrante. Les silences ne créent
pas de fragments vides. DRY reste immédiat ; les échos attendent la clôture,
puis suivent PREMIER ÉCHO, RÉPÉTITIONS et l'intervalle existant.

- REVERSE ALL : ordre des attaques inversé dans chaque fragment.
- ALTERNATE : premier écho en avant, deuxième en arrière, puis alternance dans chaque série.
- RANDOM CHAOS : choix avant/arrière à 50 % pour chaque répétition, commun à toutes ses notes.
- Hauteurs et durées des notes sont conservées avant PAS DE HAUTEUR/GATE.
  Une note encore tenue conserve sa durée via son propriétaire source et son
  watchdog existant ; elle n'est pas coupée arbitrairement à la fin du fragment.
- Configuration capturée par fragment ; une modification vaut pour les fragments
  suivants. Bypass/suppression annule le WET en attente et préserve le direct.
  STOP ciblé respecte la provenance ; RESET/PANIC réinitialise le parcours.
- Limites fixes : huit buffers de 64 attaques, ordonnanceur partagé de 256 voix.
  Un fragment sans capacité de sortie est refusé en entier et libère ses sources.
  Une saturation du buffer retire le fragment complet, sans Note Off oublié.
  Le direct déjà joué garde son niveau ; il ne peut être corrigé rétroactivement.
- Les échos restent bornés par l'horizon de 60 secondes. Des combinaisons trop
  longues de fragment, premier écho et répétitions refusent le WET explicitement.
- Les patches FORWARD continuent à être sauvegardés en extension v2. Les nouveaux
  modes utilisent v3 ; v1/v2 se relisent en FORWARD. Un ancien moteur ne doit pas
  charger silencieusement un patch v3. Revenir à FORWARD permet de sauvegarder v2.

Qualification : banc C++ sans JACK avec interdiction des allocations temps réel,
ordre MIDI/durées/annulations/capacité ; carrier Python/C++ et sauvegarde native ;
édition réelle des quatre choix et rappel dans le test navigateur Conductor.
Inspiration : https://freakshowindustries.com/backmask (adaptation MIDI, pas un clone audio).
