# MIDI BAD MOTHERFUCKER
# MASTER SPECIFICATION — MOVEMENT & PHRASE CONDUCTOR

**Projet :** MIDI BAD MOTHERFUCKER (MBMF)  
**Dépôt :** https://github.com/petedevries666/midi_human_looper  
**Socle d'audit :** PR #50, branche `fix/free-time-capture-origin`, commit observé `25fcb1e458ffdce7286ff4c60cd4546d586e19a4`  
**Cibles :** REAPER JSFX et moteur natif Zynthian/JACK avec interface Web  
**Nature :** contrat fonctionnel, UX, moteur musical, intégration et validation  
**Statut :** décisions produit validées ; aucune implémentation de ce cahier des charges n'est présumée livrée.

> **Instruction première pour Codex :** ce document est issu d'une conception détaillée avec l'utilisateur. Les règles arrêtées sont des exigences, pas des pistes d'inspiration. Ne rien improviser dans les parties non tranchées. Auditer l'existant, proposer le découpage des PR, implémenter par incréments testables et ne pas fusionner/déployer sans accord explicite.

---

## 0. Instructions non négociables

1. **Étendre MBMF, ne pas le réécrire.** Réutiliser Smart Switches, éditeur de courbes, Controller Engine, politiques d'ownership, routes MIDI, enregistrement, persistance, moteurs et tests existants.
2. **Ne rien inventer.** Une règle musicale absente de ce document reste ouverte, sans comportement arbitraire imposé par Codex.
3. **Pas de placebo.** Un contrôle visible doit fonctionner réellement. Des tests de UI sans MIDI effectif ne prouvent pas le moteur.
4. **Pas de second Controller Engine.** Les MOVEMENTS passent par la propriété, les priorités, le TAKEOVER et le BACK TO STATE du moteur existant.
5. **Ne pas perdre de musique.** Préserver événements des PHRASES, timing libre, canaux, patchs, banques, imports/exports et anciens schémas.
6. **Ne pas casser les fonctions existantes.** Instruments, Transformers, Controllers, Snapshot, REC/OVERDUB, PHRASES, Smart Switches actuels, tests et sauvegardes doivent survivre.
7. **Schémas versionnés et migrations explicites.** Aucun déplacement implicite d'offsets/records et aucune troncature de PHRASE pour obtenir une compatibilité factice.
8. **Conserver les capacités historiques non contraires au nouveau contrat**, notamment les gestes des Special Switches et les modes de parcours existants ; les options avancées ne doivent pas polluer la première couche.
9. **Ne pas modifier LUMAZ, le système Zynthian, JACK installé, firmware Helix ni une autre application.**
10. **Pas de merge vers main, pas de force-push, pas de mise à jour de mon matériel sans accord explicite.** Utiliser des PR traçables et réversibles.
11. **Cloud != qualification matériel.** Aucun test dummy-JACK à grand buffer ne prouve la stabilité réelle V4/ARM64/Helix/Firefox.
12. **Toujours dire précisément ce qui marche, ce qui ne marche pas, et dans quel hôte.**

## 1. Philosophie du produit

**Simple à découvrir. Simple à jouer. Puissant à approfondir.**

Le scénario fondateur :

~~~text
NEW SMART SWITCH
STEP 01  [+] -> PHRASE 01
STEP 02  [+] -> PHRASE 02
STEP 03  [+] -> PHRASE 03
STEP 04  [+] -> PHRASE 04

PRESS -> STEP 01 -> PRESS -> STEP 02 -> PRESS -> STEP 03 -> PRESS -> STEP 04 -> PRESS -> STEP 01...
~~~

L'utilisateur ne doit pas avoir besoin de comprendre JOIN, REVEAL, MUTE GROUP, END OF PHRASE, Controller Ownership ou courbes pour créer et jouer quatre accords.

**Première couche :** un Smart Switch, un STEP 01, un gros +, choisir une source, STEP suivant créé automatiquement, jouer immédiatement. **Profondeur progressive :** EDIT contextuel et options avancées uniquement si demandés. Il ne s'agit pas de plusieurs applications/modes : un seul logiciel avec complexité optionnelle.

Contraintes UX :
- Pas de PHRASE LIBRARY persistante dans CONDUCTOR.
- Pas de fenêtre obligatoire pour chaque ajout.
- Pas de bouton ADD STEP obligatoire entre deux ajouts.
- Pas de MIDI Learn obligatoire pour éditer ou tester.
- Pas de panneau permanent fourre-tout.
- Pas de contrôle illusoire.
- Ne pas dépendre de la souris uniquement : support tactile et clavier lorsque pertinent.
- Faible densité visuelle sans diluer inutilement les informations critiques.

## 2. Audit préalable obligatoire et état connu

Avant de coder : comparer ce contrat au contenu exact de la branche et aux dépendances PR. Fournir une matrice **existe / partiel / à créer / à adapter / absent dans REAPER** pour :
- Smart Switches dynamiques à IDs stables.
- Séquences et parcours actuels.
- Gestes PRESS/TAP/DOUBLE/HOLD et MIDI Learn.
- Controller Engine / ownership / Smart Takeover / return.
- Courbes multipoints, presets et assignations.
- Sliders TEST des Controllers.
- Instances et propriété des notes.
- REC / free-time / STOP / PANIC.
- Source MIDI import/export.
- Persistance, banques, migrations.
- Moteur partagé REAPER/natif.
- MOVEMENT autonome.
- Nouveau CONDUCTOR STEPS × LAYERS.

**Documents à lire dans le repo :**
- README.md
- docs/smart-switches.md
- docs/dynamic-smart-switches.md
- docs/controller-engine-policies.md
- docs/controller-engine-integration.md
- docs/issue-53-interactions.md
- docs/zynthian-v4-feedback-sprint.md
- docs/phrase-midi-interchange.md
- docs/capabilities.md
- sources réelles, tests et schémas sur la branche et ses bases.

**Vérifications factuelles préalables (ne pas présenter comme livrées au sens de ce contrat) :**
- La branche PR #50 contient déjà un Smart Switch à séquence de PHRASES, des modes de parcours et le TEST de gestes ; **ce n'est pas** encore le CONDUCTOR multicalque décrit ici.
- La documentation du Controller Engine décrit DIRECT/PICKUP/GLIDE/SLEW, priorités, BACK TO STATE, courbes et mappings natifs. La parité d'exécution REAPER n'est **pas entièrement acquise**.
- docs/issue-53-interactions.md décrit déjà un **slider TEST par Controller** (CC/unassigned 0–127, NOTE 0/127), passant par le vrai moteur. Auditer/conserver/tester, ne pas réécrire en parallèle.
- Plusieurs restrictions de note ownership/HOLD/import et la validation V4/Firefox/Helix physique sont encore signalées.

**Livrable de phase zéro :** état des lieux vérifié, fichiers à réutiliser, risques de migration/temps réel/ownership, plan de PR découpé, tests exigés. Ne pas commencer par un nouveau framework.

## 3. Modèle conceptuel obligatoire

**SOURCE PHRASE** : performance MIDI créée/enregistrée/importée dans le pool. Conservation du contenu, timing libre, notes, vélocités, canaux et événements supportés, PLAY MODE, paramètres existants. Un CONDUCTOR la **référence** : il ne copie pas la PHRASE ni ne possède son REC/OVERDUB.

**SOURCE MOVEMENT** : modulation temporelle réutilisable, courbe multipoints autonome sur CC/canal ou paramètre MBMF exposé. Créée/éditée séparément ; référencée par CONDUCTOR, pas inventée dans le STEP.

**SMART SWITCH** : commande nommée à identité stable, éventuellement MIDI-learned, avec gestes, options, séquence et état indépendant. Préserver la collection dynamique actuelle (ne pas la réduire à 4 switches).

**CONDUCTOR** : STEPS horizontaux, LAYERS verticaux à l'intérieur de chaque STEP, blocs de référence PHRASE/MOVEMENT/action ; options de switch, STEP et bloc.

**INSTANCE** : occurrence effective de lecture d'une SOURCE, distincte du bloc et de la SOURCE elle-même. Plusieurs instances peuvent coexister ; chacune doit avoir temps, état, destination et propriété de notes/contrôles suffisamment définis.

**SOURCE vs BLOC vs INSTANCE** : une modification de propriété locale au BLOC ne modifie pas la SOURCE. Un STOP peut concerner une INSTANCE ou toutes les instances d'une SOURCE suivant sa cible. Une source peut être référencée par plusieurs switches.

## 4. Interface CONDUCTOR validée

### 4.1. Ouverture et ajout

À l'ouverture de l'éditeur d'un Smart Switch séquencé :

~~~text
[SMART SWITCH : NAME]                       [MIDI LEARN facultatif]

[ STEP 01 ]
[    +    ]    <- gros +
[ LAYER 02 discret : + / EMPTY ]
~~~

Le gros **+** ouvre un **menu contextuel flottant** :

~~~text
+ ADD
  PHRASES   >
      PHRASE 01 / label éventuel
      PHRASE 02 / label éventuel
      PHRASE 03 / label éventuel
      PHRASE 04 / label éventuel
      ...
  MOVEMENTS >
      MOVEMENT 01 / label éventuel
      MOVEMENT 02 / label éventuel
      MOVEMENT 03 / label éventuel
      MOVEMENT 04 / label éventuel
      ...
~~~

- Sur desktop, **survol PHRASES** -> sous-menu des PHRASES ; survol MOVEMENTS -> sous-menu MOVEMENTS.
- Sur tactile, **tap** catégorie puis item. Aucune dépendance au survol exclusif.
- Cliquer un item ajoute directement la référence dans la cellule appropriée.
- Le menu accepte une longue liste sans overflow hors écran ; les noms personnalisés sont affichés, avec identification des sources non ambiguë.
- Aucune PHRASE LIBRARY permanente sur l'écran.
- Dès qu'on remplit le dernier STEP, le **STEP suivant avec gros +** apparaît automatiquement. Pas de clic ADD STEP supplémentaire.
- Un nom peut être renseigné ; MIDI Learn est facultatif. Tester à la souris sans pédalier doit être possible.

### 4.2. STEPS et LAYERS

- STEPS en colonnes horizontales.
- LAYERS verticalement dans chaque STEP.
- Deux emplacements visibles initialement, davantage ajoutés à la demande.
- **LAYER 01 = PHRASE MASTER ou EMPTY exclusivement. Jamais MOVEMENT.**
- Un STEP avec MOVEMENT seulement est valide : LAYER 01 EMPTY, MOVEMENT à partir de LAYER 02.
- Les autres LAYERS reçoivent PHRASES, MOVEMENTS ou actions supportées.
- Aucune opération (menu, édition, drag, duplicate, swap) ne peut contourner cette restriction.

### 4.3. Bloc compact : informations obligatoires

Chaque bloc présente :
1. **NOM / identité** de la SOURCE.
2. **PLAY MODE** pertinent.
3. **TRIGGER** : PRESS ou HOLD, propriété la plus utile pour comprendre quand il joue.

Exemple PHRASE :

~~~text
PHRASE 08 · F MINOR              [✎] [×]
LOOP · PRESS
~~~

Exemple MOVEMENT :

~~~text
MOVEMENT 03 · FILTER RISE        [✎] [×]
2.5 s · HOLD
~~~

Pour MOVEMENT, afficher la durée prioritairement car les PLAY MODES de PHRASE ne s'appliquent pas identiquement. Plus de détails seulement si l'espace le permet, sans surcharge.

**✎ EDIT** : ouvre le **panneau latéral contextuel** de propriétés locales/avancées, sans modifier implicitement la SOURCE. Bien distinguer INHERIT de OVERRIDE. Un bloc MOVEMENT peut exposer destination, courbe source et options d'exécution, sans transformer le CONDUCTOR en éditeur principal de courbe.

**× DELETE** : retire **la référence** du LAYER/STEP ; **ne supprime jamais la SOURCE**. UNDO immédiat.

Panneau EDIT de profondeur progressive : options pertinentes à ce type de bloc, catégories avancées repliées, pas de liste géante de toutes les options MBMF.

### 4.4. Drag & Drop uniforme dans MBMF

- Drag sur **en-tête de STEP** : insertion/réorganisation du STEP **complet** ; les autres se décalent, les LAYERS/propriétés restent attachés.
- Drag d'un **bloc sur cellule occupée** : **REPLACE** par défaut, annulable.
- Drag d'un bloc sur cellule vide : déplacement autorisé.
- **CTRL + drag** : **SWAP** entre éléments compatibles ; interdiction d'un swap créant MOVEMENT LAYER 01.
- **ALT + drag** : **DUPLICATE** avec propriétés locales conservées ; pas de copie de SOURCE.
- **Tactile** : commandes MOVE et REPLACE accessibles sans clavier ; ne pas exiger CTRL/ALT.
- **UNDO transversal** pour STEPS, LAYERS, propriétés, courbes, delete/replace/swap/duplicate. Ne jamais promettre d'annuler les événements MIDI déjà émis. Toute restauration de configuration en runtime doit demeurer sûre.

## 5. Defaults validés et parcours simple

| Paramètre | DEFAULT |
|---|---|
| Parcours | **SEQUENTIAL** |
| Transition | **IMMEDIATE** |
| Déclenchement | **PRESS / INSTANT**, sans attente de classification |
| STEP initial | STEP 01 |
| LAYER 01 | PHRASE MASTER ou EMPTY |
| Fin du dernier STEP | Retour STEP 01 |
| MIDI Learn | Facultatif |
| Options avancées | Repliées |

**Premier test obligatoire : quatre PHRASES, quatre PRESS, quatre STEPS, puis retour STEP 01.** Ne doit pas nécessiter une seule ouverture de paramètres avancés.

La position du STEP est indépendante de l'identité de la PHRASE. Si une même PHRASE apparaît aux STEPS 01 et 03, surligner **le STEP effectivement sélectionné**, pas les deux.

### 5.1. SEQUENTIAL

Un PRESS admissible sélectionne et déclenche le STEP suivant, avec wrap final -> STEP 01. Pas de lancement automatique de STEP par un timer.

### 5.2. RANDOM pur et SHUFFLE BAG

Deux modes avancés distincts.
- **SHUFFLE BAG par défaut parmi les modes aléatoires**, RANDOM pur reste disponible.
- Tirage sur les **positions de STEPS**, pas sur les IDs de PHRASES.
- Une PHRASE répétée sur deux STEPS compte pour deux positions.
- Sont éligibles au RANDOM/SHUFFLE **seulement les STEPS contenant au moins une PHRASE sur n'importe quel LAYER**.
- STEP avec MOVEMENT seul ou STOP seul : **exclu** des tirages, **accessible en SEQUENTIAL**.
- LAYER 01 EMPTY + PHRASE sur LAYER 02 : **éligible**.
- SHUFFLE BAG : chaque position éligible est tirée une fois par sac, puis remix ; modifications d'éligibilité prises en compte au prochain remix.
- RESET SHUFFLE BAG : remixe/réinitialise ; suppression de STEP/source manquante doit rester sûre.
- Conserver les modes historiques non contradictoires (BACKWARD/PING-PONG) sans polluer la première couche.

## 6. Transitions IMMEDIATE / END OF PHRASE

**Transition globale par Smart Switch**, option locale sur chaque STEP : **INHERIT / IMMEDIATE / END OF PHRASE**.

### 6.1. IMMEDIATE (default)

Le PRESS déclenche immédiatement le nouveau STEP.

**Ne signifie pas STOP des PHRASES précédentes.** Continuité/arrêt dépendent du PLAY MODE, MUTE GROUP, politique d'instance et actions STOP explicites. Aucun STOP implicite au changement de STEP.

### 6.2. END OF PHRASE (avancé)

LAYER 01 détermine le **MASTER** si une PHRASE y est effectivement active.
- MASTER ONCE : attente de sa fin effective.
- MASTER LOOP : attente de la fin effective du **cycle** en cours.
- Si pas de MASTER, LAYER 01 EMPTY, ou MASTER déjà terminé : transition **immédiate**.
- Lorsqu'attente : état **QUEUED**. Toute pression d'avancement supplémentaire pendant QUEUED est **ignorée**, pas empilée.
- Si MASTER stoppé prématurément par STOP ou MUTE GROUP : **annuler QUEUED**. Le prochain PRESS choisit et déclenche le STEP suivant normalement.
- En **RANDOM + END OF PHRASE**, destination choisie **à la frontière d'exécution réelle**, pas au PRESS initial. Une transition QUEUED annulée ne consomme pas le tirage.
- États ACTIVE/QUEUED/READY disponibles en lecture, discrets sur scène.

Le moteur musical, pas un timer Web, calcule ces frontières.

## 7. Gestes PRESS / HOLD / DOUBLE

### 7.1. INSTANT (default)

**PHRASE PRESS part immédiatement.** HOLD peut ajouter son action au franchissement du seuil, sans reporter l'action PRESS. RELEASE suit la sémantique propre de l'action ou de la source.

### 7.2. EXCLUSIVE (advanced)

Attendre si nécessaire pour distinguer les gestes, avec **avertissement de latence** visible. EXCLUSIVE ne doit pas devenir le défaut.

### 7.3. DOUBLE

**Réservé aux Smart Switches d'actions non séquencés.** Dans un Smart Switch séquencé, deux PRESS rapprochés doivent faire STEP 01 puis STEP 02. Ne pas absorber le second PRESS en DOUBLE.

Conserver les gestuelles et seuils existants là où applicables : Note On positif / Note Off ou vélocité 0 ; PRESS/RELEASE CC exacts ; gestion des repeated presses, Learn exclusif, conflits explicites, quarantine de release, TEST sans matériel.

MIDI THRU des commandes de Smart Switch **OFF par défaut** conformément à l'existant ; aucune commande de footswitch ne doit involontairement enregistrer de notes.

## 8. PHRASES, PLAY MODES et instances

- Le **PLAY MODE appartient à la SOURCE PHRASE**, avec éventuel **override local par bloc** en propriétés avancées ; jamais de modification implicite de la SOURCE.
- Respecter les modes effectivement supportés (LOOP, ONCE, HOLD) et les paramètres vélocité/temps/overdub existants.
- Une SOURCE peut apparaître plusieurs fois, sur plusieurs Smart Switches.
- Politique configurable à chaque demande de la même PHRASE : **JOIN EXISTING / RESTART / NEW INSTANCE**.
- Chaque mode doit gérer des instances réellement distinctes, des sources communes, des notes déjà tenues et des Note Off cohérents.
- Les modifications de paramètres de note transformatrice doivent continuer à respecter les transformations Note On/Note Off et les commits différés existants.

## 9. MUTE GROUP

- **MUTE GROUP est EXCLUSIVEMENT une propriété de SOURCE PHRASE. Aucun override local sur un bloc.**
- Déclencher une nouvelle PHRASE du groupe stoppe l'ancienne du même groupe selon la politique moteur, avec nettoyage ciblé.
- Deux PHRASES du même MUTE GROUP dans un même STEP : **warning mais autorisé**.
- **Plus petit ID de PHRASE prioritaire** dans le conflit intra-STEP. Ne pas dépendre d'un ordre mémoire accidentel.
- Après changement de MUTE GROUP dans la SOURCE, **réévaluer les warnings** des Smart Switches déjà construits.
- Le MASTER interrompu par MUTE GROUP annule QUEUED comme en §6.

## 10. MOVEMENT : source réutilisable et éditeur

MOVEMENT est une **source autonome** créée/éditée **hors CONDUCTOR**, puis ajoutée par référence.

### 10.1. Éditeur

Ouvrir **directement sur la courbe** ; presets à droite.
- Courbe libre multipoints, points et bends.
- Réutiliser l'éditeur graphique multipoints existant plutôt que créer un autre éditeur incompatible.
- Cliquer un preset **remplace immédiatement** la courbe courante ; elle devient modifiable ; **la bibliothèque originale n'est pas modifiée**.
- UNDO couvre les modifications de courbe.
- **Durée en secondes par défaut** ; option avancée durée musicale/tempo lorsque réellement supportée.
- Destination déclarée sur la SOURCE : **CC + canal** ou **paramètre MBMF effectivement exposé**.
- Destination pouvant être override localement dans un bloc CONDUCTOR (advanced).
- Édition d'une SOURCE pendant l'exécution : **effet au prochain déclenchement**, pas de modification de la courbe de l'instance active.
- Ne pas promettre de paramètres non pris en charge par les catalogues actuels.

### 10.2. Exécution

- MOVEMENT continue après changement de STEP, arrêt de MASTER et **STOP ALL PHRASES**.
- Fin naturelle : libérer son ownership et appliquer le Controller Engine TAKEOVER/BACK TO STATE ; pas de CC zéro arbitraire.
- Retrigger : **SOFT RESTART par défaut** ; variantes avancées localement.
- MOVEMENTS visant une même cible : arbitrage par Controller Engine existant, avec priorités, ownership, génération, reprise et retour sûrs.
- La nouvelle source gagnante détermine le comportement de transfert **SOFT / DIRECT** ; une ancienne source dominée ne reprend pas spontanément le contrôle.
- MOVEMENTS sur différentes cibles indépendants.
- MOVEMENT déclenché par HOLD : **ONE SHOT par défaut**, continue après RELEASE ; **GATED** en advanced.

## 11. JOIN : PHRASES et MOVEMENTS

**JOIN concerne LES DEUX TYPES DE SOURCES.**

JOIN utilise un temps réellement écoulé sur la timeline de référence. **Ce n'est pas du time stretch ni de l'alignement proportionnel.**

- **JOIN NOW default** : alignement immédiatement au trigger.
- **JOIN AT LOOP START advanced** : attendre le début du cycle de référence suivant.
- Référence MASTER : PHRASE effectivement active de LAYER 01, selon le contexte ; si plusieurs instances de la PHRASE sont actives, utiliser **la DERNIÈRE INSTANCE ENCORE ACTIVE, même si déclenchée par un autre Smart Switch**.
- MASTER LOOP : **CYCLE default** utilise position dans le cycle en cours ; **ELAPSED advanced** utilise temps depuis début de l'instance.
- **Aucun stretching du MOVEMENT** : sa durée reste celle définie par sa source.
- Si position JOIN théorique dépasse la durée MOVEMENT : il démarre depuis **son début (TRIGGER)**.
- Si aucun MASTER ne joue : MOVEMENT démarre librement depuis zéro.
- Après JOIN effectif, arrêt du MASTER ne stoppe pas le MOVEMENT.
- JOIN PHRASE en milieu de timeline : **NEXT NOTES ONLY**. N'émettre aucun Note On qui aurait dû commencer avant JOIN.
- Les Note Off correspondant à des Note On non émis ne doivent pas être envoyés comme événements autonomes qui coupent des notes d'autres instances.
- Associer chaque Note On/Off à sa propriété effective ; pas de Note Off orphelins.

**Arbitrage Q2 VALIDÉ (option A) :** si JOIN demande une position au-delà de la durée d'une **PHRASE non bouclée**, la PHRASE est déclenchée **normalement depuis le début (temps 0)**, avec son PLAY MODE et ses propriétés habituelles. Elle n'est ni étirée, ni raccourcie, ni artificiellement synchronisée. Cette règle s'applique à la PHRASE comme la règle de repli déjà validée pour MOVEMENT.

## 12. REVEAL

REVEAL est une PHRASE qui **démarre silencieusement à PRESS, partage l'origine temporelle avec MASTER et devient audible au HOLD sans redémarrer à zéro**.

- PRESS : MASTER audible et PHRASE REVEAL cachée mais réellement en progression temporelle.
- HOLD : révéler la couche à sa position actuelle ; pas de nouveau PLAY depuis zéro.
- RELEASE **sans HOLD reconnu** : **STOP** de la couche encore cachée.
- Après HOLD : **LATCH default** ; après RELEASE, continuer selon PLAY MODE.
- **GATE advanced** : état dépend de maintien.
- CC7 par layer possible mais MIDI CC7 est canal-wide : sur canaux partagés, plusieurs couches peuvent être affectées. **Warning mais autoriser** et demander routage indépendant pour isolation réelle.
- STOP ciblé coupe la PHRASE qu'elle soit cachée ou révélée ; aucun état orphelin.
- Le moteur doit éviter de détruire les volumes/notes des autres layers lors du masquage, de la révélation et du nettoyage.

## 13. Blocs actions : STOP / PAUSE / RESUME / RESET

- Blocs d'action accessibles dans les STEPS, avec réglages avancés par crayon EDIT.
- **STOP** peut cibler **PHRASE / MUTE GROUP / ALL PHRASES**.
- **STOP ciblant une PHRASE** : arrête **TOUTES ses instances globalement**, incluant instances cachées, révélées, joined, provenant de n'importe quel Smart Switch.
- **STOP ALL** : arrête **PHRASES seulement**, **MOVEMENTS continuent**.
- **PAUSE** conserve la position ; **RESUME explicite par défaut**. Advanced : reprendre au prochain PLAY.
- Les notes physiquement actives doivent être relâchées ou protégées correctement en cas de PAUSE.
- **RESET CURSOR** : annule QUEUED, remet le curseur au **STEP 01**, **sans arrêter les sources** déjà actives.
- **RESET SHUFFLE BAG** : réinitialise/remixe bag.
- **STOP + RESET** : action distincte associant les effets correspondants.
- PRESS après RESET doit déclencher normalement STEP 01 selon la politique d'instance ; pas de cas spécial qui annule automatiquement des sources.

## 14. FECK = urgence PANIC globale

**FECK est une commande distincte de STOP ALL.**

FECK doit immédiatement :
- arrêter toutes PHRASES et MOVEMENTS et nettoyer leurs instances ;
- annuler actions différées encore pertinentes et transitions QUEUED ;
- couper les notes générées par MBMF de façon sûre ;
- empêcher les propriétaires périmés de reprendre la main ;
- appliquer les mécanismes sûrs Controller Engine de retour/annulation d'ownership ;
- annuler l'activité en cours sans effacer les SOURCES ni configuration.

**FECK CONSERVE le STEP sélectionné** : il **ne remet pas le curseur à STEP 01**. RESET est distinct.

**Arbitrage Q1 VALIDÉ (option A) :** après FECK, **le prochain PRESS rejoue depuis le début le STEP conservé**, en relançant normalement les PHRASES, MOVEMENTS et actions de ce STEP selon leurs règles habituelles. Le PRESS suivant reprend le parcours normal vers le STEP suivant selon le mode configuré. FECK ne remet jamais le curseur à STEP 01 à lui seul. Exemple SEQUENTIAL : `STEP 03 → FECK → PRESS (rejoue STEP 03) → PRESS (STEP 04)`. Une transition QUEUED annulée par FECK ne doit pas se déclencher après la reprise.

L'interaction entre panic d'urgence et notes physiquement jouées en direct doit respecter la sécurité du moteur et les limitations du MIDI partagé ; documenter le contrat et le tester.

## 15. Controller Engine existant et ownership

Tout MOVEMENT est soumis au Controller Engine commun, pas un writer parallèle.

Pipeline logique :

~~~text
MIDI physique ou TEST source / MOVEMENT
   -> mapping / réponse courbe
   -> TAKEOVER
   -> priorité & ownership
   -> valeur effective normalisée
   -> scaling / descripteur
   -> application dans vrai moteur
~~~

Réutiliser les politiques existantes :
- DIRECT, PICKUP, GLIDE, SLEW ;
- priorité et égalité par événement récent / ID de mapping (selon moteur actuel) ;
- IDLE, RELEASE, COMMAND, OFF et BACK TO STATE ;
- ownership generation pour empêcher retour obsolète ;
- protection lors des changements de Transformers affectant Note Off.

Quand MOVEMENT termine, ne jamais forcer zéro ni remettre une valeur ancienne possédée par un autre contrôleur.

## 16. Web CONTROLLERS : sliders TEST

**Exigence explicite de dernière minute, obligatoire.**

Chaque CONTROLLER créé dispose d'un **slider TEST compact et directement utilisable** dans l'interface Web, sans hardware et sans Learn.

- CC/unassigned : 0–127 continu.
- NOTE : binaire 0/127.
- Souris, tactile et clavier.
- Valeur visible et effet réellement appliqué **pendant** le déplacement (ne pas attendre RELEASE ou DONE).
- Passe par **le vrai Controller Engine**, par identité stable du Controller et ses vraies courbes/mappings/takeover/glide/slew/return.
- Test **ne crée pas de mapping**, **ne modifie pas MIDI Learn**, **n'altère pas les bases persistantes**, **ne sauvegarde pas sa position transitoire**.
- Ne pas générer de fausses entrées MIDI dans le routage pour simuler la commande.
- Préserver distinction des fonctions EDIT / CLEAR MIDI (efface assignation physique, garde source/mappings) / REMOVE (efface source et mappings).
- **Déjà décrit dans docs/issue-53-interactions.md sur PR #50** : contrôler et préserver, tester véritablement contre une destination MBMF et MIDI émis. Ne pas développer un doublon si l'existant passe l'acceptation.

## 17. Propriété des notes : critère bloquant

La robustesse MIDI est un **prérequis structurel**, non un supplément après UI.

Distinguer SOURCE, référence CONDUCTOR et **instance** ; tenir un ledger permettant de relier les Note Off aux Note On **effectivement émis** par cette instance, après routage/transformations.

Cas indispensables :
- même PHRASE jouée par deux Smart Switches ;
- deux instances même canal + pitch ;
- JOIN démarrant après le Note On historique mais avant son Off ;
- REVEAL caché puis révélé, ou arrêté caché ;
- STOP ciblé sur une instance/source/groupe ;
- STOP ALL laissant MOVEMENTS intacts ;
- FECK global ;
- sustain CC64 ;
- changements note-transformers avec notes tenues ;
- overload/XRUN ;
- Note On/Off simultanés, répétitions et canaux multiples.

**Ne pas utiliser un simple booléen channel/pitch** incapable de distinguer des propriétaires qui se chevauchent.

Ne pas casser une note appartenant à une autre instance en envoyant un Off orphelin.

Documenter la limite fondamentale des récepteurs MIDI partageant pitch/canal : le synthétiseur final ne distingue pas forcément les propriétaires logiques, même si MBMF les distingue en interne. Tester et avertir selon les contextes.

## 18. Horloge musicale et contraintes temps réel

**Le moteur audio/MIDI est l'horloge, pas le browser.**

Doivent être calculés/déclenchés côté moteur :
- temps des notes ;
- fin effective ONCE/LOOP MASTER ;
- HOLD threshold ;
- JOIN NOW / LOOP START ;
- durée/interpolation des MOVEMENTS ;
- QUEUED, annulation, exécution ;
- ordering des événements ;
- ownership et releases.

Contraintes :
- aucun accès disque/HTTP/JSON/GUI dans callback audio ;
- aucune allocation non bornée ni mutex bloquant en callback ;
- handoff de configuration sécurisé ;
- temps basé sur horloge/sample/blocks existants, avec précision documentée ;
- capacity et overflow bornés ;
- stabilité de l'ordre MIDI ;
- nettoyage PANIC/STOP/SAVE/LOAD ;
- ne pas annoncer un niveau de latence non mesuré.

Auditer la capacité actuelle des voix et des séquences avant d'ajouter des instances/layers ; une UI montrant une infinité de blocs ne doit pas cacher une capacité moteur dépassée.

## 19. Persistence et migration

Persistants :
- Smart Switches IDs stables, noms, mappings ;
- STEPS ordonnés, LAYERS, références ;
- options du switch, STEP et bloc ;
- MOVEMENTS sources, durée, courbes, destinations ;
- PLAY MODES/overrides ;
- sources PHRASES existantes et leurs contenus.

Non persistants en tant qu'état musical actif :
- notes tenues, instances actives, timestamps ;
- ownership/retours en cours ;
- gestes physiques en cours ;
- QUEUED ;
- bag/cursors runtime ;
- MIDI Learn candidat ;
- TEST slider temporaire.

**Au LOAD : configuration restaurée, curseurs à l'état initial, AUCUN playback actif.** Pas de notes fantômes ni de MOVEMENT auto-relancé.

Versionner les nouveaux records sans réinterpréter les offsets de legacy/banques. Tester lecture des vieux schemas, données inconnues, IDs supprimés, cases vides, import/export, patches natifs et export REAPER. Ne jamais tronquer une phrase free-time pour forcer compatibilité.

Lorsqu'une SOURCE manque/supprimée : afficher référence manquante, ne jamais rejouer une autre SOURCE par réutilisation d'index, protéger les paramètres restants pour correction ultérieure, ne produire aucun MIDI inattendu.

## 20. REAPER / Zynthian : vérité musicale commune

Viser la même intention musicale et les mêmes comportements pour les fonctions déclarées compatibles.

- Réutiliser logique partagée quand possible.
- Si deux implémentations sont nécessaires, établir contrat, fixtures et résultats MIDI équivalents.
- Ne pas confondre partage de nom avec **parité de traitement**.
- La documentation actuelle indique des limites de Controller Engine dans REAPER et d'import/export ; ne pas les masquer.
- Une livraison native d'un module ne permet pas d'annoncer son support REAPER.
- Fournir matrice **native implémenté/testé, JSFX implémenté/testé, limitations, migration**.
- Ne pas sacrifier REAPER pour obtenir une fonctionnalité Zynthian rapide.

## 21. Matrice d'acceptation automatisée

Chaque ligne doit posséder un test automatisé pertinent **sur moteur réel ou adapter de moteur**, plus recette musicale lorsque nécessaire. Si une fonction n'a pas de test, ne pas la déclarer DONE.

### A. Premier usage (impitoyablement simple)

A01 Smart Switch vide -> STEP 01 +.  
A02 Menu PHRASES/MOVEMENTS avec labels.  
A03 Ajouter PHRASE 01 -> STEP 02 apparaît automatiquement.  
A04 Quatre PHRASES sans options avancées.  
A05 PRESS x4 -> quatre STEPS dans l'ordre.  
A06 PRESS #5 -> STEP 01.  
A07 Même scénario sans MIDI Learn/hardware via TEST.  
A08 Même résultat avec MIDI physique simulé/réel.  
A09 Une PHRASE répétée sur plusieurs STEPS -> seul STEP sélectionné surligné.

### B. UI/édition

B01 Longue liste, menu ne déborde pas.  
B02 Hover desktop.  
B03 Tap tactile.  
B04 ✎ ouvre propriétés contextuelles et héritage.  
B05 × supprime référence seulement.  
B06 UNDO restaure.  
B07 Interdiction MOVEMENT LAYER 01.  
B08 LAYER 01 EMPTY + MOVEMENT LAYER 02.  
B09 Propriétés locales distinctes des SOURCES.  
B10 Résumé bloc nom/mode/trigger, durée MOVEMENT.  
B11 Pas de PHRASE LIBRARY persistante.  
B12 Première couche utilisable sur écran réduit.

### C. Drag & Drop / UNDO

C01 Drag en-tête STEP = insertion de colonne complète.  
C02 Drag bloc sur cellule occupée = REPLACE.  
C03 UNDO remplacement.  
C04 CTRL drag = SWAP compatible.  
C05 ALT drag = DUPLICATE avec propriétés.  
C06 Destination incompatible refusée.  
C07 Touch MOVE/REPLACE sans clavier.  
C08 UNDO propriétés/courbes.  
C09 UNDO ne promet pas d'effacer MIDI passé.

### D. Transitions

D01 IMMEDIATE direct, sans STOP implicite.  
D02 END OF PHRASE ONCE MASTER.  
D03 END OF PHRASE LOOP frontière cycle.  
D04 LAYER 01 EMPTY => immédiat.  
D05 MASTER déjà terminé => immédiat.  
D06 QUEUED n'empile pas PRESS.  
D07 STOP prématuré annule QUEUED.  
D08 MUTE GROUP prématuré annule QUEUED.  
D09 PRESS suivant une annulation exécute le STEP suivant.  
D10 RANDOM + END OF PHRASE tire au boundary réel.  
D11 Annulation n'utilise pas tirage inexécuté.  
D12 Global INHERIT/override STEP SAVE/LOAD.

### E. Parcours aléatoire

E01 MOVEMENT-only exclu.  
E02 STOP-only exclu.  
E03 PHRASE en LAYER 02 incluse.  
E04 Bag sans remise sur positions éligibles.  
E05 Deux STEPS avec même PHRASE = deux positions.  
E06 RESET BAG.  
E07 Changement éligibilité au prochain remix.  
E08 Deletion/source manquante n'invalide pas moteur.

### F. PHRASES / instances / groupes

F01 Même SOURCE sur plusieurs STEPS.  
F02 Même SOURCE sur plusieurs Smart Switches.  
F03 JOIN EXISTING.  
F04 RESTART.  
F05 NEW INSTANCE.  
F06 Notes de même pitch/canal superposées.  
F07 STOP source arrête toutes ses instances, pas les autres.  
F08 MUTE GROUP ciblé.  
F09 Deux PHRASES du même groupe dans un STEP -> warning + plus petit ID prioritaire.  
F10 Changement ultérieur de groupe re-détecté.  
F11 Legacy LOOP/ONCE/HOLD et decay préservés.

### G. MOVEMENTS

G01 SOURCE créée indépendamment.  
G02 Courbe multipoints éditable.  
G03 Preset appliqué immédiatement, source preset intacte.  
G04 Durée secondes exacte selon précision hôte.  
G05 JOIN ne stretch pas durée.  
G06 Continue après changement STEP.  
G07 Continue après stop MASTER.  
G08 Continue après STOP ALL.  
G09 SOFT RESTART sans saut injustifié.  
G10 Collision même cible -> ownership déterministe.  
G11 Cibles différentes indépendantes.  
G12 BACK TO STATE correct.  
G13 Édition source en lecture -> prochain trigger.  
G14 HOLD ONE SHOT continue après RELEASE.  
G15 HOLD GATED arrête/libère correctement.

### H. JOIN

H01 JOIN NOW au temps écoulé réel.  
H02 JOIN AT LOOP START à bonne frontière.  
H03 CYCLE vs ELAPSED distincts.  
H04 Dernière instance MASTER active même depuis autre switch.  
H05 Durée MOVEMENT inchangée.  
H06 Position > durée MOVEMENT => début 0.  
H07 Aucun MASTER => départ 0 MOVEMENT.  
H08 JOIN PHRASE mi-note : pas de faux Note On.  
H09 Pas de Note Off orphelin coupant autre instance.  
H10 MASTER s'arrête après JOIN -> MOVEMENT continue.  
H11 JOIN PHRASE non-LOOP, position demandée au-delà de sa durée -> démarrage à temps 0, PLAY MODE et propriétés conservés, sans time-stretch.

### I. REVEAL

I01 PRESS démarre timeline cachée.  
I02 HOLD révèle sans restart.  
I03 RELEASE sans HOLD stoppe la source cachée.  
I04 LATCH conserve après RELEASE.  
I05 GATE varie au maintien.  
I06 LOOP cachée/révélée conserve temporalité.  
I07 STOP ciblé hidden.  
I08 STOP ciblé revealed.  
I09 Conflit CC7 partagé => warning non bloquant.

### J. STOP / PAUSE / RESET / FECK

J01 STOP ALL PHRASES laisse MOVEMENTS.  
J02 RESET STEP 01 sans STOP.  
J03 RESET annule QUEUED.  
J04 PRESS après RESET suit politique d'instance normale.  
J05 PAUSE préserve position et notes de façon sûre.  
J06 RESUME explicite par défaut.  
J07 STOP + RESET combine effets.  
J08 FECK coupe PHRASES, MOVEMENTS, pending/QUEUED.  
J09 FECK ne remet pas STEP 01.  
J10 Pas de Note Off parasite, stuck note ou ownership ancien après FECK.  
J11 Après FECK, le premier PRESS rejoue **depuis le début** le STEP conservé avec ses règles habituelles ; le PRESS suivant avance selon le parcours normal.  
J12 Aucune transition QUEUED antérieure au FECK ne se déclenche après le redémarrage.  
J11 STOP caché/revealed/joined.

### K. Web Controller TEST

K01 Nouveau Controller sans MIDI hardware.  
K02 Slider visible immédiatement.  
K03 CC/unassigned 0–127.  
K04 NOTE binaire 0/127.  
K05 Effet réel pendant glissement.  
K06 Mapping/curve/takeover traversés.  
K07 GLIDE/SLEW/RETURN.  
K08 Pas de MIDI Learn synthétique.  
K09 Pas de mutation du patch/base.  
K10 Mouse/touch/keyboard.  
K11 SAVE/LOAD conserve mappings, pas TEST transitoire.  
K12 CLEAR MIDI ≠ REMOVE source.

### L. Persistence / compatibilité

L01 STEPS/LAYERS.  
L02 MOVEMENT courbes/durées/destinations.  
L03 Overrides.  
L04 Stable IDs.  
L05 Legacy patches.  
L06 LOAD silencieux, runtime stoppé.  
L07 Aucun playback fantôme.  
L08 Deux banques / anciennes extensions.  
L09 MIDI PHRASES originaux intacts.  
L10 Réutilisation d'index ne change pas la référence.  
L11 Export REAPER ne détruit pas native-only extensions.

## 22. Recettes musicales de terrain

**R1 — Quatre accords :**

~~~text
STEP 01 L1: PHRASE Am
STEP 02 L1: PHRASE F
STEP 03 L1: PHRASE C
STEP 04 L1: PHRASE G

PRESS / PRESS / PRESS / PRESS / PRESS
=> STEP 01 / 02 / 03 / 04 / 01, sans options avancées.
~~~

**R2 — Master + HOLD MOVEMENT :**

~~~text
STEP 01
  LAYER 01: PHRASE 01 / LOOP / PRESS
  LAYER 02: MOVEMENT 01 / 2.5 s / HOLD / ONE SHOT
~~~

PRESS lance PHRASE immédiatement. HOLD lance MOVEMENT. RELEASE laisse MOVEMENT finir et RETURN approprié ; PHRASE suit son PLAY MODE.

**R3 — JOIN :** MASTER en cours à 1,5 s ; JOIN NOW démarre au temps pertinent, sans stretching. Une nouvelle instance MASTER via autre switch devient la référence si elle est la dernière active.

**R4 — REVEAL :** MASTER A + couche B silencieuse depuis PRESS ; HOLD révèle B à son temps courant ; RELEASE LATCH la conserve. Sans HOLD, RELEASE détruit B cachée.

**R5 — MUTE GROUP :** deux PHRASES du même groupe dans STEP -> warning + plus petit ID ; modifier ensuite le groupe SOURCE -> warning actualisé.

**R6 — STOP / FECK :** plusieurs PHRASES/MOVEMENTS + END OF PHRASE QUEUED ; STOP ALL laisse MOVEMENTS ; FECK annule tous, garde position du STEP et ne laisse aucune note bloquée.

**R7 — Controller TEST vs hardware :** piloter vrai paramètre MBMF, comparer réponse MIDI/mapping/glide/return avec slider Web et contrôleur physique.

## 23. Tests hôtes et captures

Cloud/desktop :
- Lancer suites existantes pertinentes : `scripts/combined-test.py`, `scripts/controller-test.sh`, `scripts/screenshots.sh` et suites de migration/SMF/browser/JSFX/JACK.
- Tests **moteur réel**, pas mock de couche HTTP seulement.
- Sanitizers, overlap des notes, callback safe, bounded queue et regressions précédentes.
- Ne pas désactiver asserts / relâcher guards pour obtenir PASS.
- Documenter XRUN et environnement d'exécution.

REAPER :
- Vérifier réellement le support des fonctions déclarées.
- Préserver phrases, overdub, SAVE/LOAD et chemin MIDI.
- Publier la liste exacte des fonctions natives sans parité JSFX.

Zynthian V4 :
- Pas de déploiement sans autorisation et SHA approuvé.
- Backups patch/Zynthian snapshot avant mise à jour.
- Vérifier version active, Firefox réel, Helix PRESS/HOLD/RELEASE, Piano/Bass/Synth, sustain, STOP/FECK, timing, XRUN et redémarrages.
- Procédure rollback documentée.
- Résultat Cloud dummy-JACK à 8192 frames n'est **pas** un certificat de faible latence V4.

Captures réellement issues de l'application :
- Smart Switch vide STEP01+, menus, PHRASE sélectionnée, quatre STEPS ;
- deux LAYERS, résumé NOM/MODE/TRIGGER/✎/× ;
- panneau EDIT et advanced ;
- MOVEMENT curve+presets ;
- CONTROLLER + slider TEST ;
- QUEUED, warning MUTE GROUP et warning REVEAL/CC7.
- Plusieurs formats desktop, petit écran, tactile ; pas de contrôles essentiels cachés/overflow.
- Style compact, brut, minimal, technique, sans décoration inutile.

## 24. Roadmap d'implémentation à jalons vérifiables

Ne pas faire un commit monolithique non vérifiable.

**PHASE 0 — AUDIT / CONTRAT**
- Inspection code exact, dépendances PR, schéma et fonctions à réutiliser.
- Tableau d'écarts, risques, plan des PR, propositions d'intégration.
- Pas de grand refactoring avant compréhension.

**PHASE 1 — CONDUCTOR MINIMAL**
- STEPS/LAYERS, gros +, menus PHRASES/MOVEMENTS, restrictions LAYER 01, autocréation STEP.
- Bloc NOM/MODE/TRIGGER/EDIT/DELETE.
- PRESS/SEQUENTIAL/IMMEDIATE, Web TEST et SAVE/LOAD.
- **Gate : quatre accords joués réellement, sans advanced.**

**PHASE 2 — ÉDITION**
- Panneau latéral/overrides, Drag STEP INSERT, bloc REPLACE, CTRL SWAP, ALT DUPLICATE, tactile MOVE/REPLACE, UNDO, warnings.

**PHASE 3 — PARCOURS / TRANSITIONS**
- RANDOM, SHUFFLE BAG, END OF PHRASE, QUEUED, interruption MASTER, reset.

**PHASE 4 — MOVEMENT SOURCES**
- Sources persistantes, éditeur multipoints/presets/durée/destinations, références et exécution autonome.

**PHASE 5 — CONTROLLER INTEGRATION**
- Arbitres, ownership, SOFT RESTART, takeover/return, préserver/tester Web Controller TEST.

**PHASE 6 — INSTANCES / JOIN / REVEAL**
- Ledger notes, politiques d'instances, JOIN PHRASES+MOVEMENTS, REVEAL, LATCH/GATE, warnings CC7.

**PHASE 7 — ACTIONS / FECK**
- STOP ciblé/ALL, PAUSE/RESUME, RESET CURSOR/BAG, STOP+RESET, FECK, nettoyage.

**PHASE 8 — PERSISTENCE / PARITÉ / RELEASE GATES**
- Migrations complètes, vieux patches, fixtures cross-host, screenshots réels, récette REAPER, protocole V4, docs.

L'ordre interne de fondations peut être adapté si une dépendance réelle l'exige (ex. ledger de notes avant une politique d'instance), **mais ne pas déclarer une phase livrée sans sa fonctionnalité et ses tests**.

## 25. Livrables exigés pour chaque phase/PR

1. Fonctionnalités et comportements implémentés, versus non implémentés.
2. Fichiers modifiés, points d'intégration, réutilisation de composants.
3. Choix d'architecture et justification.
4. Schéma/persistence/migrations si concernés.
5. Tests ajoutés et **commandes réellement exécutées**.
6. Résultats PASS/FAIL et limitations.
7. SHA exact, branch et lien de PR.
8. Captures réelles si UI modifiée.
9. Procédure de vérification musicale/hardware.
10. Problèmes ouverts ; aucun faux « all done ».
11. Pas de merge ni mise en production sans revue.

## 26. Points EXPRESSÉMENT non validés : demander, ne pas improviser

**Q1. Premier PRESS après FECK — RÉSOLU, option A validée :** FECK conserve le STEP sélectionné ; le premier PRESS suivant **rejoue ce STEP depuis le début**, avec toutes ses sources et règles habituelles ; le PRESS suivant reprend le parcours normal. **Aucune demande d'arbitrage supplémentaire sur Q1.**

**Q2. JOIN PHRASE non-LOOP au-delà de sa durée — RÉSOLU, option A validée :** redémarrer la PHRASE au **temps 0** en cas de JOIN demandé au-delà de sa durée ; respecter PLAY MODE et propriétés, sans stretching. Aucun arbitrage supplémentaire requis sur Q2.

**Q3. Paramètres numériques/limites d'implémentation non décidés :** fréquence maximale d'update MOVEMENT, maximum de LAYERS/MOVEMENTS/instances, durée chiffrée d'un SOFT handover, limites exactes de courbes, stockage. **Auditer les capacités réelles, mesurer, proposer**, ne pas prétendre que l'utilisateur a validé des chiffres.

**Q4. Comportement détaillé de quelques cas PAUSE/RESUME sur notes tenues et limites MIDI partagées :** le contrat impose position conservée et Note Off sûrs. Les modalités d'implémentation doivent être documentées et testées, pas supposées validées au-delà de ce contrat.

Ne pas redemander les dizaines d'arbitrages *déjà* tranchés dans les sections précédentes.

## 27. Motifs de refus explicites

Non conforme si :
- bibliothèque PHRASES permanente, tunnel de fenêtres, Add Step obligatoire ;
- besoin d'advanced pour lancer quatre accords ;
- presse retardée par défaut ou DOUBLE qui absorbe PRESS du séquenceur ;
- IMMEDIATE arrête toutes les PHRASES ;
- MOVEMENT en LAYER 01 ;
- DELETE efface la SOURCE ; EDIT modifie silencieusement SOURCE ;
- RANDOM prend MOVEMENT-only/STOP-only ;
- END OF PHRASE bloque sans MASTER ou QUEUED survit à la mort du MASTER ;
- JOIN étire la courbe, synthétise d'anciennes notes ou envoie des Off orphelins ;
- REVEAL recommence à zéro ou laisse hidden orphelin ;
- STOP ALL coupe MOVEMENTS ; RESET coupe PHRASES ;
- FECK remet au STEP 01 ;
- MOVEMENTS contournent le Controller Engine ;
- slider TEST décoratif ou qui modifie base sauvegardée ;
- LOAD démarre de la musique ou perd des PHRASES ;
- migration tranche des données ou efface native-only extensions ;
- REAPER présenté comme complet sans preuve ;
- tests supprimés/affaiblis, assertions contournées ;
- merge/main/deploy non autorisé.

## 28. Definition of Done

DONE seulement si :
1. Vrai modèle de données.
2. Vraie interface utilisable.
3. Vraie sortie MIDI/contrôle du moteur.
4. Arrêt, cleanup et cas limites prouvés.
5. SAVE/LOAD correct si persistant.
6. Tests réels pertinents.
7. Aucune régression connue dissimulée.
8. Parité et limites par hôte explicites.
9. Captures/preuves associées au **SHA exact**.
10. État annoncé honnêtement : implémenté, testé logiciel, validé matériel, ou restant.

**Un bouton n'est pas une fonction ; un Cloud PASS n'est pas un concert.**

## 29. Ordre de mission immédiat pour Codex

1. Lire cette spécification et les docs existants.
2. Auditer le dernier HEAD effectif et ses dépendances.
3. Rendre matrice des existants/manquants et risques de schéma/notes/temps réel/REAPER.
4. Proposer plan de PRs avec tests et gates.
5. Démarrer ensuite **CONDUCTOR MINIMAL**, en préservant toute la profondeur d'architecture requise par les phases suivantes.
6. Ne merger ni déployer automatiquement.

**FIRST ACCEPTANCE TEST :**

~~~text
NEW SMART SWITCH
  STEP 01 [+] -> PHRASE 01
  STEP 02 [+] -> PHRASE 02

PRESS -> PHRASE 01 plays immediately
PRESS -> PHRASE 02 plays immediately
~~~

**Build this correctly first. Preserve its simplicity forever.**
