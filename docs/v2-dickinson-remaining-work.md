# V.2 DICKINSON — livraison et évolutions restantes

Le nom validé est **V.2 DICKINSON**, comme Bruce Dickinson. Le produit natif
porte sa propre version, indépendante du JSFX REAPER figé.

Base musicale : PR #89 puis PR #90 (CLIMB exploratoire). Pas de fusion dans main.
Le STEP MAX des CLIMB reste fixé à 2 dans cette livraison. Les variantes UP et
UP/DOWN, ainsi que DOWN et DOWN/UP, partagent encore leur parcours dans #90.
Ne pas présenter ces limites comme des fonctionnalités terminées.

## Premier incrément commencé

- [x] Tester #90 : 25 426 contrôles du vrai MIDI généré par ysfx/EEL réussis.
- [x] Test privé natif : patch 127, ARP mode 12 et réservation Program Change.
- [x] Donner au Web et à son API le nom V.2 DICKINSON.
- [x] Fiabiliser le catalogue : requête partagée, validation, nouvelle tentative
  avec temporisation bornée et protection contre un éditeur sans descripteur.
- [x] Conserver les choix MIDI RECALL non appliqués lors de LIER et du polling ;
  montrer explicitement « MODIFICATIONS EN ATTENTE · APPLIQUER ».
- [x] Tests des handlers JavaScript de production avec réponses HTTP contrôlées.
- [x] Qualification visuelle authentifiée de cet incrément sur le Pi : nom de
  version, identités des transformateurs et 13 choix ARP, dont le mode 11 actif.
- [ ] Qualification prolongée audio/MIDI ; les tests courts ne la remplacent pas.

La dispense humaine antérieure de captures aux cinq tailles reste limitée à la
validation directe sur l’interface réelle. Aucun test responsive complet n’est
revendiqué ici. Les tests JS ne sont pas des captures ni une preuve de rendu.

## Ordre de reprise

### P0 — fiabilité et conservation

- [ ] Ignorer un Program Change visant le patch réellement déjà actif : aucun
  STOP, rechargement MBMF ni rappel du snapshot ; conserver les modifications
  non sauvegardées. Garder RAPPELER PATCH comme rechargement volontaire.
  Vérifier l’état chargé dans la session courante, pas seulement le numéro
  sélectionné/persisté. Tester PC répétés pendant/après chargement, redémarrage,
  échec de rappel et conservation de la dernière demande utile en attente.
- [ ] Compléter la validation du chargement : réseau lent, descripteurs en échec,
  token absent/incorrect, reconnexion et redémarrage du moteur, Firefox/mobile.
  Attendu : aucun MODULE/undefined éditable et aucune requête en boucle folle.
- [ ] Tester rig + patches : redémarrage, IDs de processeurs, snapshots associés,
  changement/renommage, interruption et rollback. Aucun écrasement implicite.
- [ ] Qualifier les notes maintenues, sustain, STOP/PANIC, entrée Helix, ajout et
  suppression de chaînes, reconnexion des ports, routage par canal et refus sûrs.
- [ ] Mesurer charge, mémoire, XRUN, délais et réception MIDI en durée ; garder
  distincts les échecs moteur, synthé et ordonnancement. Ne pas modifier JACK pour
  faire passer un test sans décision explicite.

### P1 — ARP et contrat complet CONDUCTOR

- [ ] Ajouter STEP MAX 1–4 : descripteur, sélection native, UI, sauvegarde et
  migration avec défaut neutre 2, limites et vrai MIDI. (#90)
- [ ] Différencier/consolider les quatre CLIMB après validation musicale, sans
  changer silencieusement les identités de modes des patches existants.
- [ ] Livrer les parcours Conductor BACKWARD/PING-PONG/RANDOM/SHUFFLE : le
  compilateur actuel exécute SEQUENTIAL/INSTANT seulement. Ne pas confondre avec
  les parcours historiques du Smart Switch simple. (#55/#78)
- [ ] JOIN NOW et JOIN AT LOOP START, PHRASE et MOVEMENT, sans time stretch ni
  fausses notes antérieures ; référence maître et dépassement de durée conformes.
- [ ] Politiques JOIN EXISTING / RESTART / NEW INSTANCE : la compilation actuelle
  ne livre que NEW_INSTANCE comme override de bloc ; tester toutes les entrées.
- [ ] Blocs de couche STOP, PAUSE, RESUME, RESET CURSOR/BAG et STOP_RESET : le
  modèle les conserve mais cela ne constitue pas un chemin d’exécution complet.
  PAUSE libère les notes possédées ; RESUME ne réattaque pas les notes anciennes.
- [ ] FECK : annuler sons, MOVEMENTS et transitions en attente, garder le STEP,
  rejouer ce STEP au prochain PRESS puis reprendre le parcours normal.
- [ ] Revoir la matrice du cahier maître A01–L11 et R1–R7 : REVEAL/GATE/fades,
  groupes, frontières exactes, STOP, saturation, références manquantes et persistance.
- [ ] Vérifier les extensions MOVEMENT non closes de #31/#32 : beats/bars,
  quantification, politique de changement de tempo, bibliothèque/copier-lier,
  multi-cibles et ownership. ONCE/LOOP/PING-PONG et GATED sont déjà développés.

### P2 — modules et contrôles demandés mais non livrés

- [ ] VELOCITY CURVES + AMOUNT : vraie courbe de réponse et mélange 0–100 %,
  distincts du multiplicateur VELOCITY actuel. (#12/#18)
- [ ] HUMANIZER phrases et instruments : intégrer la fondation #25 au scheduling,
  à l’ownership, aux descripteurs, à l’UI et à la persistance. (#11/#18)
- [ ] ECHOCITY : passer du scheduler #28 au module musical ; puis Freeze/Reverse
  selon le cahier propre. Ne pas annoncer la fondation comme un effet jouable.
  Suite native commencée : noyau C++, journal/pont des sources directes et
  phrases POLY/MONO, tests avec le vrai ysfx. Sortie musicale partagée, étapes
  aval/ARP, configuration et Web encore à faire.
  Voir [le chantier ECHOCITY](echocity-native-core.md).
- [ ] Velocity Decay Pitch Bias/Pivot : helper encore inactif ; migration native,
  paramètres, contrôleurs, snapshots et lecture réelle à développer.
- [ ] Transformateurs propres aux PHRASES : absents de l’exécution actuelle.
- [ ] Vélocité ×0.0 : minimum actuel ×0.2 ; gérer correctement silence et Note Off,
  conversions et migration. (#51)
- [ ] BYPASS global MIDI THRU transparent et journal MIDI Web réel. (#70)
- [ ] Import MIDI : étendre/refuser explicitement CC, bend, pressure et programme,
  et qualifier les limites ; l’import actuel est notes-only. (#33)

### P3 — administration et release cohérente

- [ ] Fermer #54 : vrai pairing persistant révocable, autorisation ADMIN séparée,
  menu natif au bon endroit et navigation de l’encodeur testée sur le V4. La
  passerelle locale n’est pas à elle seule la preuve de ces exigences.
- [ ] Qualifier CHECK/UPDATE/ROLLBACK et cache (#52), sources de release éligibles,
  interruption, restauration et absence d’activation pendant une activité musicale.
- [ ] Consolider les branches/PR et réviser les documents de capacités périmés ;
  une PR Draft, un modèle JSON ou un ancien test vert ne constituent pas une
  release intégrée qualifiée. (#75/#76)

## Discipline et prochain travail

La validation directe de l’interface V.2 DICKINSON est terminée : version,
identités des modules et choix ARP vérifiés. Les preuves opérationnelles et
captures restent privées ; aucun patch musical n’est publié.

Chaque case exige : code natif réel si nécessaire, MIDI observé pour une règle
musicale, UI utilisable, SAVE/LOAD/migration et résultat attribué au bon commit.
Conserver les patches et snapshots du musicien, les fichiers locaux non suivis,
le JSFX figé et LUMAZ. Pas de merge automatique.

Après la livraison et la vérification visuelle : reproduire le chargement lent
sur le navigateur réel, puis commencer STEP MAX 1–4 sur un incrément séparé.
Ne pas reprendre un audit général à chaque interruption ; reprendre la première
case non clôturée, en mettant ce fichier à jour avec les preuves.
