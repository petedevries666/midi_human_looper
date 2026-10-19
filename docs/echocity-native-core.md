# Suite de V2 : ECHOCITY natif

## Statut explicite

Noyau C++ et raccordement des sources en développement. Le banc exécute le
vrai moteur EEL natif dans ysfx, observe son MIDI sec et transmet ses événements
sources à l’ordonnanceur C++. **Les échos restent reçus par le banc de test ;
ils ne sont pas encore insérés dans la sortie du host JACK ou dans le Web.**
La version musicale déjà installée reste utilisable. Aucun JSFX REAPER figé,
patch utilisateur, preset ou configuration JACK n’est modifié par ce travail.

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

Ce raccordement observe une frontière POLY/MONO existante : **il ne fournit pas
encore une continuation à n’importe quel endroit de la chaîne**. L’accord en
entrée d’un ARP n’est volontairement pas annoncé comme sa sortie arpégée. L’ARP,
le mélange MIDI sec/échos, les réattaques superposées et le partage des sorties
doivent encore être intégrés avant d’activer un module musical.

## Intégration suivante avant un module jouable

- Activer le journal/pont dans le host de performance avec configuration native,
  sortie MIDI partagée, récupération sur refus et chargement de patch.
- Raccorder une continuation réelle par identité stable aux étapes de la chaîne,
  y compris MONO/ARP ; mesurer le coût et qualifier les réattaques qui se croisent.
- Intégrer configuration versionnée, IDs indépendants, descripteurs, commandes,
  sauvegarde/restauration, contrôleurs/MOVEMENTS et édition Web transactionnelle.
- Tester le MIDI réellement émis et la restauration d’anciens patches avant une
  installation musicale. L’écoute et Firefox sur le Pi restent à qualifier.
- Étendre ensuite Feedback/Freeze, parcours, taps et Reverse conformément au
  checkpoint #28 ; aucun de ces modes n’est annoncé livré par ce noyau.
