# Synthèse exécutive — audit MBMF

Le socle logiciel fonctionne dans les tests Cloud, mais **la qualification concert
sur Zynthian V4 reste ouverte**. Main ne contient pas la majorité du produit actuel :
la pile de drafts doit être revue dans son ordre de dépendance. Les rapports de
checkpoints ne suffisent pas à prouver une fonctionnalité ou une validation matérielle.

Trois corrections isolées et testées sont livrées en drafts :

- #72 : SAVE/LOAD refusent les données natives inconnues au lieu de les effacer.
  Les tests reproduisent l'ancienne perte de données via la vraie API et vérifient
  la conservation des fichiers et de la révision moteur. Les gates manquants
  pour routage #67, sorties de PHRASE #68 et administration #71 sont ajoutés.
- #73 : les clients WebSocket partagent l'encodage JSON d'une même observation.
  Sur un état natif réel de 11 714 octets, une lecture déjà encodée coûte en médiane
  0,36 µs de CPU worker contre 144,65 µs pour un réencodage. Ce résultat ne mesure
  ni le callback MIDI ni les XRUN ; le premier encodage reste nécessaire.
- La correction UPDATE A22 refuse une configuration devenue différente pendant
  la préparation, avant journalisation et arrêt des services. Le test conserve le
  port modifié 9000 et n'appelle aucun service. Le redémarrage global de l'UI n'est
  pas transformé en hot-update MBMF.

Le gel REAPER est explicite dans AGENTS.md, README et le document dédié. Le JSFX
est conservé sans modification ; projets anciens et tests pertinents d'interchange
restent protégés. Les nouvelles fonctionnalités ciblent uniquement native/Web.

Le danger confirmé à traiter ensuite est l'isolation Controller : apprendre une
source CH2/CC21 annule actuellement un MOVEMENT CH1/CC11. Le compteur natif passe
réellement de 1 à 0. Cette mission ne change pas arbitrairement cette politique
musicale ; sa correction demande les tests d'isolation Snapshot/MOVEMENT/Controller.
Éviter cet apprentissage pendant une audition d'automation en attendant.

Les XRUN/pics CPU de #63 restent inexpliqués en partie, y compris sans navigateur.
L'instrumentation #63 n'est pas héritée par #71. Le compteur historique actuel ne
couvre pas le callback entier. Le worker UPDATE exige une autorisation distincte,
mais HTTP n'encrypte pas le mot de passe ; réseau isolé ou proxy HTTPS existant.
Aucune release stable éligible n'est publiée. Aucun update de draft n'est autorisé.

À tester **d'abord**, après revue du SHA et hors concert :

1. Relever le SHA réellement exécuté, pas seulement « v1.27.1 ». Sauvegarder projet
   et snapshot Zynthian. Ne pas supposer que le matériel suit le dernier draft.
2. Un MBMF, trois synthés sur CH2/CH3/CH4 : vérifier ZynMidiRouter, absence de liens
   directs/duplications/feedback, changements de chaîne et rappel du snapshot.
3. Enregistrer puis boucler, superposer les notes, tenir la pédale sustain ; tester
   STOP sélectif, PANIC et sorties PHRASE ORIGINAL/ALL/CH1–16. Vérifier les messages
   au récepteur, pas seulement un compteur d'activité MBMF.
4. Fermer le navigateur et tester LIGHT/NORMAL à 512 frames pendant 15 minutes,
   puis 256 seulement si propre : CPU/RAM, deadlines/XRUN, ports, Helix et transport.
   Ne pas faire de SAVE/LOAD/update pendant cette mesure musicale.
5. Dans une session d'administration arrêtée et dédiée, tester refus de mot de
   passe, activation compatible, conservation des projets et rollback/recovery.
   L'UI Zynthian peut être interrompue ; ce n'est pas un update de concert.

**GO pour revue des petites corrections ; NO-GO pour affirmer une qualification
concert ou fusionner aveuglément la pile.** Aucun merge, déploiement, changement
JACK/OS/LUMAZ ou modification des 25 fichiers protégés de l'issue #54.

Rapport détaillé, priorités et plan d'intégration :
[engineering-audit-2026-10.md](engineering-audit-2026-10.md).
