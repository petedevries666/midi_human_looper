# CC/MOD TEACH et ouverture directe des courbes

## Apprendre un CC dans Zynthian

Lier l’instrument MBMF à une chaîne Zynthian, activer son CC/MOD et choisir son
numéro de CC. Sur le contrôle désiré de cette même chaîne, faire un appui long
sur le potentiomètre puis sélectionner « Chain learn… ». Déplacer MOD LEVEL ou
cliquer TEACH dans l’éditeur du transformateur. Un simple tap tactile ne suffit
pas à sélectionner la cible ; le mode général Learn peut également demander de
tourner l’encodeur ou de faire glisser son contrôle pour le présélectionner.

TEACH assigne explicitement le CC courant au contrôle armé, puis lui applique la
valeur actuelle de MOD LEVEL. Il fonctionne donc même sans changement de valeur.
Il utilise le relais de contrôleurs Zynthian : il ne prétend pas émettre un
nouveau paquet MIDI JACK et ne déclenche pas le Learn interne d’un plugin ouvert
dans VNC. Ce dernier demande un chemin MIDI propre au plugin.

L’assignation est liée à la chaîne et au canal. Elle utilise le mécanisme Learn
Zynthian existant ; elle peut remplacer l’ancienne assignation du contrôle armé.
La sauvegarde de l’état Zynthian reste nécessaire pour la retrouver après rappel.
Une cible non armée, d’une autre chaîne, un processeur remplacé ou une route non
admise sont refusés. Bank Select et les CC système 120–127 ne sont pas appris.
Les événements du relais restent consommés avant les commandes MIDI globales.
Les vrais CC reçus peuvent également apprendre le contrôle armé de leur chaîne.
Après succès, la sortie du mode Learn est également envoyée à la file du GUI :
l’affichage et les points d’interrogation ne restent pas bloqués alors que la
cible du moteur a déjà été désarmée.

## Courbe d’un paramètre déjà lié

Un clic sur un slider lié, ou Entrée lorsqu’il a le focus, ouvre directement sa
courbe. Une assignation en bypass reste éditable. Aucune réassignation ni commande
MIDI n’est envoyée par cette sélection.

Le panneau CONTROLLER CURVE EDITOR est indépendant de TRANSFORMER EDITOR, placé
juste après lui par défaut, et possède les mêmes commandes de déplacement haut /
bas. Un ordre personnalisé déjà enregistré est conservé. L’éditeur du
transformateur peut rester ouvert. Reclique sur la même cible conserve son
brouillon ; changer de cible demande de confirmer l’abandon du brouillon.
DONE enregistre la courbe ; CANCEL ferme sans l’enregistrer.

## Validation

Tests des handlers JavaScript de production pour la sélection, la conservation
du brouillon, l’indépendance des panneaux et le commit limité à l’assignation.
Tests du relais et de ChainLinks avec objets Oram simulés pour Learn, les gardes
de session/identité, le bypass et le refus des événements réservés. Ces tests ne
qualifient pas l’entrée physique MIDI ni le Learn interne des plugins.

L’ouverture et la disposition ont été inspectées sur l’interface réelle. La
dispense humaine autorise cette validation directe ; les cinq tailles du
workflow screenshots n’ont pas été qualifiées. Les preuves privées, patches et
identifiants d’exploitation ne font pas partie du dépôt.
