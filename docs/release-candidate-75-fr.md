# Synthèse — consolidation native MBMF (#75)

Une seule branche depuis main réunit le socle natif, PHRASES/overdub/HOLD,
Transformers/ARP, Controller, Snapshots, Smart Switches, CONDUCTOR/MOVEMENT,
routage Oram filtré, sorties PHRASE ORIGINAL/ALL/CH1–16, projets/SMF,
mbmf.local, portail AZ séparé, UPDATE autorisé et rollback, corrections #72–#74.
Les diagnostics optionnels #63 sont réconciliés ; les anciennes implémentations
#45/#46 ne sont pas réintroduites. HUMANIZER/ECHOCITY restent des fondations,
BYPASS/MIDI LOG et les phases avancées ne sont pas déclarés livrés.

Le défaut Learn est corrigé : réapprendre/effacer une source ne fait plus PANIC
sur tous les propriétaires Controller. Les autres pédales, snapshots et MOVEMENTS
continuent. Les tests C++, l'API native et la vraie sortie JACK vérifient cette
isolation, dont 201 valeurs de CC à cadence exacte pendant l'apprentissage.
PANIC reste global. Deux défauts Web sont aussi corrigés et reproduits : le bouton
EDIT détaché entre relâchement et clic, et le choix du prochain Transformer effacé
par une réponse ADD en attente. Les choix restent indépendants par Instrument et
n'ajoutent rien au schéma musical. Les tests de géométrie sont rendus atomiques sans assouplir
leurs seuils ; les timeouts JACK continuent d'échouer en conservant les diagnostics.

**Pas de merge automatique.** La première qualification LIVE a effectivement échoué :
XRUN dans les six profils, pic CPU réel de 99,75 ms en LIGHT/256 et capture MIDI
non chronologique en NORMAL/256. Le compteur d'ordre natif à zéro ne suffit pas
à innocenter cette capture. L'étape suivante précise est d'instrumenter le cycle
du récepteur et les acquisitions de buffer JACK avant de modifier le moteur.
Les résultats détaillés ne sont ni cachés ni attribués globalement au Cloud.

Les suites combinées et leur SHA final sont publiés sur la PR d'intégration #76.
Les tentatives intermédiaires échouées restent dans les preuves ; les tests
matériels sont distincts. La PR reste DRAFT tant que les gates de revue/fiabilité
ne sont pas satisfaits. Aucun tag RC ne doit être publié pour contourner UPDATE.

UPDATE interrompt potentiellement l'UI et les instruments Zynthian ; son dernier
contrôle STOP n'est pas un verrou atomique contre une reprise MIDI. Le mot de
passe administrateur exige un réseau isolé ou un accès HTTPS existant. L'import
SMF reste limité aux notes. Ces limites sont explicites, pas des fonctions promises.

REAPER est gelé, conservé byte-identique à #74. Les 25 fichiers de l'issue #54
restent protégés. Aucun accès/déploiement sur le V4, aucune modification des sources
LUMAZ, du système Zynthian ou du service JACK.

Après revue seulement : vérifier le SHA réellement exécuté, sauvegarder projet et
snapshot, tester un MBMF vers trois synthés CH2/3/4 via Oram, sustain/STOP/PANIC,
enregistrement et restauration. Qualifier ensuite 512 frames navigateur fermé,
puis 256 si propre. Tester UPDATE/rollback séparément, à l'arrêt, jamais en concert.

[Rapport et rollback](release-candidate-75.md) ·
[Mesures LIVE et échec](release-candidate-75-live.md) ·
[Inventaire des PRs](release-candidate-75-pr-inventory.md).

Mise à jour mesurée : la suite combinée source3acebd5 termine à0, sanitizer sans
diagnostic, les deux courses historiques et le nouveau sélecteur passent. Le
second run LIVE termine encore à1 : NORMAL est propre à512/256 pendant12 secondes,
mais LIGHT/256 atteint228,221 ms CPU /373,065 ms écoulées et STRESS/256 échoue sur
l’ordre temporel capturé. Cette fois le grand pic est dans le bracket CC/actions
MOVEMENT ; le plus grand pic STRESS est dans EEL. La fonction responsable n’est
pas identifiée, aucune conclusion globale « c’est le Cloud » n’est justifiée.
Les nouvelles traces restent avec les anciennes, sans sélection des seuls PASS.
[Preuves et table actualisées](evidence/release-candidate-75/final-source-3acebd5/README.md).
