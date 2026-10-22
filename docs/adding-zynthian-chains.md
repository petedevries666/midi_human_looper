# Ajouter une chaîne Zynthian avec MBMF

Il n’est pas nécessaire de prévenir MBMF. Arrêter la lecture et relâcher les notes,
ajouter la chaîne synthé dans Zynthian avec un canal MIDI distinct, puis vérifier
les liens dans CONFIG / MIDI OUTPUT. « RELIER PAR CANAL OUT » associe les modules
INSTRUMENTS existants à leurs chaînes par canal de sortie ; il ne crée pas un
nouveau module INSTRUMENT pour chaque nouvelle chaîne. Ajouter ce module si
nécessaire, choisir son IN et le canal OUT du nouveau synthé, puis le relier.

Après vérification, sauvegarder le patch et son snapshot Zynthian pour conserver
la nouvelle configuration complète. Un ancien snapshot restaure son ancien
ensemble de chaînes : les chaînes ajoutées après sa sauvegarde n’y figurent pas.
Les snapshots créés dans une banque sans préfixe de trois chiffres ne sont pas
listés par l’écran Zynthian Oram. Pour une banque visible, utiliser un nom comme
`001-MBMF`. Le rappel programmatique peut néanmoins utiliser une banque existante
nommée `MBMF` ; ne pas déplacer ses fichiers sans actualiser les liens.

En cas de silence, arrêter la lecture, utiliser PANIC si une note reste tenue,
vérifier que le contrôleur est connecté, puis vérifier les canaux IN/OUT et les
liaisons dans MBMF. Une note de commande de Smart Switch ne doit pas jouer
directement un synthé ; si elle le fait, vérifier le trajet d’entrée avant de
modifier les synthés. Recharger un snapshot connu rétablit ses chaînes et ses
réglages, mais ne rebranche pas un appareil physiquement absent.

Correction du cas constaté : une nouvelle chaîne provoque une réévaluation du
routage. L’ancien code refusait toute sortie MBMF si un seul des ports d’entrée
explicitement configurés était absent. Désormais, les entrées configurées et
présentes restent isolées vers MBMF ; une entrée configurée qui revient rejoint
ce routage lors de l’autoconnexion suivante. Aucun autre appareil n’est substitué.
Si aucune entrée configurée n’est présente, la sortie reste bloquée. Les exclusions
des retours MIDI et des appareils non sélectionnés restent appliquées.
