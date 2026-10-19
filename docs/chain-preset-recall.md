# Rappel et SAVE indépendants des chaînes Zynthian

Dans CONFIG / MIDI OUTPUT, RAPPEL DES CHAÎNES montre, pour chaque destination
instrument : canal, instrument, preset, effets MIDI/audio et leurs presets.
La ligne RÉFÉRENCE décrit ce qui est enregistré dans le snapshot du patch actif.
Le bouton SAVE appartient uniquement à cette chaîne.

## Portée du bouton

SAVE met à jour les slots instrument/effets et leurs réglages dans le snapshot
déjà associé au patch. Il conserve les autres chaînes, les sources et fichiers
de patches MBMF, les autres ZS3, le séquenceur, les profils MIDI et le routage.
Le volume/pan et les réglages du canal de mixage ciblé sont conservés avec le son.
Il n’exécute ni rappel, ni arrêt musical, ni changement de preset courant.

Un snapshot complet doit d’abord être associé. Une chaîne absente de ce snapshot,
un changement de canal/mixeur ou une collision d’identité demandent une nouvelle
sauvegarde globale explicite : SAVE individuel ne remplace jamais une autre chaîne
pour contourner une ambiguïté. Les ajouts/retraits d’effets dans la chaîne existante
sont pris en compte si leurs identités ne sont pas utilisées ailleurs.

## État réel des plugins

Pour un plugin LV2 indépendant, SAVE demande au moteur Zynthian son export de
preset, qui capture aussi l’état opaque : par exemple les réglages internes de
Surge XT modifiés via VNC ENGINE. La capture reçoit une identité de fichier unique ;
elle n’écrase aucun preset du musicien ni les ressources d’une ancienne capture.
Le snapshot référence cette capture, avec le nom lisible du preset d’origine.
Les contrôles visibles Zynthian sont également sauvegardés.

Les plugins/moteurs partagés entre chaînes sont refusés si leur état ne peut pas
être isolé. Un moteur non LV2 utilise son preset, ses contrôles et son éventuelle
configuration étendue indépendante ; ce support doit être qualifié par moteur.

RÉFÉRENCE ENREGISTRÉE / MODIFIÉ compare les paramètres observables par Zynthian,
le preset et le mixage. Un changement opaque dans la fenêtre d’un plugin ne peut
pas toujours être détecté par le Web ; le nom inchangé n’est pas une preuve de
son identique. Le rappel de cette limite est disponible sur l’indicateur.
SAVE capture toujours l’état réel du plugin LV2, même si son nom n’a pas changé.

## Intégrité et activité

- L’écriture est préparée hors du callback audio. L’action est mise en file du
  worker existant et utilise le verrou de bibliothèque.
- La lecture, les notes, REC, les instances, MOVEMENTS et morphs actifs refusent
  SAVE ; l’application n’arrête pas la musique à la place de l’utilisateur.
- Session, identité, empreinte des réglages et snapshot sont revérifiés. Un état
  devenu obsolète est refusé ; un fichier modifié en parallèle reste conservé.
- Une copie précédente du snapshot est conservée localement avant publication
  atomique. Un échec de publication laisse l’ancienne référence utilisable.
- Les captures sont contrôlées avant rappel : fichier local autorisé, existence
  et empreinte. Un preset absent/corrompu produit une erreur avant l’arrêt musical.
- Les empreintes et ressources de capture restent locales ; elles ne sont pas
  envoyées au navigateur. Les noms affichés utilisent textContent.

## Validation

Tests de service avec vrais documents JSON et moteurs simulés : isolation de la
chaîne/FX/mixeur, phrase et autre chaîne inchangées, export opaque, alias après
rappel, concurrence, refus pendant lecture, fichier corrompu et publication ratée.
Les anciens tests du rappel MIDI et les handlers JavaScript sont également lancés.
Ces tests ne certifient pas le rappel audio matériel de tous les synthés et effets.

Le déploiement et l’inspection de l’interface réelle sont à réaliser avec le
musicien au repos. La dispense de captures aux cinq formats accordée par le
musicien s’applique à cette inspection directe ; pas de qualification responsive
complète revendiquée. Aucune modification du JSFX REAPER figé ni de LUMAZ.
