# Suite de V2 : ECHOCITY natif

## Statut explicite

Noyau C++ en développement, testé isolément. **Il n’est pas encore connecté au
traitement ysfx/JACK ni proposé comme transformateur insérable dans le Web.**
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
```

Ces programmes exécutent le vrai noyau C++ et contrôlent l’absence d’allocation
dans les chemins testés. Ils couvrent frontières de blocs, ordre, collisions,
réutilisation, surcharge atomique, durée connue/inconnue, watchdog, tempo,
captured routing, annulation par origine/module et reprises de fins refusées.
Les callbacks de sortie et l’horloge de bloc sont des bancs de test : **ce ne
sont pas des preuves de MIDI réel via ysfx/JACK ni d’écoute sur les synthés.**

## Intégration suivante avant un module jouable

- Raccorder les jetons sources au vrai chemin direct/phrase et à ses Note Off,
  Note On zéro, sustain, STOP/PANIC, suppression et chargement de patch.
- Raccorder une continuation réelle par identité stable aux étapes de la chaîne,
  y compris MONO/ARP ; mesurer le coût et qualifier les réattaques qui se croisent.
- Intégrer configuration versionnée, IDs indépendants, descripteurs, commandes,
  sauvegarde/restauration, contrôleurs/MOVEMENTS et édition Web transactionnelle.
- Tester le MIDI réellement émis et la restauration d’anciens patches avant une
  installation musicale. L’écoute et Firefox sur le Pi restent à qualifier.
- Étendre ensuite Feedback/Freeze, parcours, taps et Reverse conformément au
  checkpoint #28 ; aucun de ces modes n’est annoncé livré par ce noyau.
