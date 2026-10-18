# Journal de développement

Ce journal reconstitue les étapes à partir des notes du projet et des essais du propriétaire. Il ne prétend pas que les commits GitHub ont été créés ces jours-là : la mise en dépôt a lieu le 18 octobre 2026. Aucune activité n’est inventée pour les jours sans trace.

## 18 octobre 2026 — première publication préparée, v0.1.0

- Commandes enrichies dans la zone de notification : noms LSC, états, luminosité, blancs, couleurs, scènes, minuteur et planning.
- File d’attente commune pour les commandes individuelles et groupées.
- Compte à rebours et planning confirmés par le propriétaire.
- Thème anthracite et violet inspiré de NZXT ; dialogues du minuteur, du planning et de l’éditeur réorganisés.
- Unités hors des champs, texte raccourci, jours sélectionnables, libellés français.
- Sélection des chiffres au clic ; modification séparée des heures/minutes.
- Icône verte pour allumer, rouge pour éteindre, avec suppression du libellé redondant.
- Préparation du dépôt public, de l’installateur par utilisateur, de l’archive portable, des notices et des contrôles de publication.
- Module de connexion privé importable localement ; exclusion des identités de la version publique.

## 14 octobre 2026 — consolider Windows

- Priorité donnée à Windows avant Mac.
- Transport Python autonome, sans exécution d’Electron ni chargement de la DLL fabricant.
- Vérification HMAC/AES contre la primitive native sur 20 cas aléatoires.
- Scènes encodées, conservation des dernières variantes reçues et compte à rebours interne à l’ampoule.
- Corrections de l’échelle de luminosité, de l’envoi blanc/luminosité en un paquet et du fuseau des horaires.
- Attente de l’expiration du cache LSC avant relecture du planning.
- 73 tests automatiques passaient à cette étape.

## 13 octobre 2026 — exploration et première connexion

- Définition du besoin à partir de deux modèles d’ampoules et des captures mobiles.
- Prototype de bureau et transports local/cloud, puis analyse de l’authentification avec REA dans Codex.
- Inspection de l’APK et du client Electron ; identification et vérification du flux QR.
- Connexion validée sur téléphone, récupération des appareils et des schémas ; sessions et clés placées dans le coffre système.
- Raccordement des commandes réelles, amélioration de la réponse locale et lecture du planning partagé.
- Test d’un unique horaire désactivé, explicitement autorisé, puis vérification de sa modification et de sa suppression.

## Suite envisagée

- Confirmer les scènes sur les deux ampoules et étendre la couverture matérielle.
- Simplifier la configuration du cloud sans redistribuer d’identité privée.
- Réception des événements LSC et notifications Windows mieux qualifiées.
- Signature des distributions et amélioration des mises à jour.
- Reprise de macOS après validation de Windows.
