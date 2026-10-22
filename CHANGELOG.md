# Journal de développement

## 0.5.1 beta — Réactivité et configuration native — 22 octobre 2026

- Correctif du contrôle natif vide : configuration demandée à l’ajout, aperçu explicite sans ampoule et requête de sélection sans erreur avant association.
- Sélections distinctes pour plusieurs instances du contrôle ; tests Swift du fournisseur de valeur et de l’intention réels.
- Priorité aux commandes entre lectures, recherche LAN automatique en arrière-plan, connexions cloud réutilisées.
- Suppression d’une lecture préalable redondante si la description vérifiée a moins de 15 s ; confirmation après publication conservée.
- Valeur native lue depuis un état récent vérifié, avec expiration et contrôle de l’identité de l’appareil.
- Indicateur de connexion native et de code refusé dans le panneau de configuration de l’app.
- 168 tests Python ; latence effective et configuration dans le Centre de contrôle à retester sur le Mac du propriétaire.


## 0.5.0 beta — Centre de contrôle natif — 21 octobre 2026

- Extension WidgetKit macOS 26+ configurable sur l’inventaire du compte : marche/arrêt d’un éclairage ou de tous ensemble.
- Association par code local distinct de la session LSC, sans groupe d’applications ni certificat Developer ID ; rotation du code pour révoquer les anciens accès.
- API liée à 127.0.0.1, uniquement inventaire minimal et marche/arrêt, authentification obligatoire, refus des origines navigateur.
- Actualisation native après changements observés par l’app.
- 160 tests ; compilation et enregistrement de l’extension vérifiés sur macOS. L’affichage et l’exécution dans le Centre de contrôle du propriétaire restent à confirmer.
- Le propriétaire confirme le bon fonctionnement de l’app macOS 0.4.0 sur son Mac M4.


## 0.4.0 — macOS Apple Silicon — 21 octobre 2026

- Application autonome ARM64 et DMG pour Mac M1 et suivants, sans Rosetta.
- Fenêtre et commandes de barre des menus partageant les fonctions Windows.
- Préparation de connexion QR sur Mac : extraction locale vérifiée, lecteur portable des ressources de signature, aucun code Windows exécuté.
- Session dans le Trousseau macOS ; aucun profil du propriétaire distribué.
- Construction et essais du paquet sur macOS en CI, dont QR sans session.
- Préversion sans notarisation ; Centre de contrôle natif encore non livré.


Ce journal reconstitue les étapes à partir des notes du projet et des essais du propriétaire. Il ne prétend pas que les commits GitHub ont été créés ces jours-là : la mise en dépôt a lieu le 18 octobre 2026. Aucune activité n’est inventée pour les jours sans trace.

## 21 octobre 2026 — curseurs directs, v0.3.1

- Clic n’importe où sur la barre de luminosité ou saturation, puis glissement direct ; suppression de l’avancement natif par petits pas.
- Position calculée avec la géométrie réelle du style Qt ; prise du curseur sans saut et valeurs bornées aux extrémités.
- Zone de souris de 28 pixels, poignée légèrement agrandie et survol plus clair.
- Conservation du réglage si une ancienne lecture se termine après le relâchement, avant l’envoi de la commande en attente.
- Une seule commande au relâchement, avec aperçu immédiat à l’écran.
- 141 tests, dont clic/glissement sur différentes tailles et styles, limites, disposition inversée, conservation HSV et ancienne lecture en cours.

## 21 octobre 2026 — connexion sur une installation neuve, v0.3.0

- Remplacement de l’import manuel du module privé par une préparation guidée depuis le client Action officiel, sans redistribuer ses fichiers dans le paquet.
- Téléchargements HTTPS de versions connues Action/7-Zip, taille et SHA-256 vérifiés avant extraction ; hôtes de redirection limités et transfert annulable.
- Lecture du MSI 7-Zip en mode base de données, extraction CAB puis NSIS/7z : aucun installateur exécuté et aucune installation système.
- Configuration lue comme données, sans évaluer le JavaScript ; identifiant d’installation unique, aucune session copiée.
- Exécution du pont natif restreint avec le runtime officiel préparé localement. L’ancien transport autonome reste disponible pour les profils qui le possèdent déjà.
- Suppression des recherches implicites dans les outils privés de développement ; ajout du pont au paquet public.
- QR serveur obtenu avec un profil vide, sans session et sans module privé ; lecture authentifiée du compte vérifiée séparément avec le runtime nouvellement préparé.
- 130 tests automatiques et contrôles de confidentialité étendus aux configurations natives.

## 18 octobre 2026 — éclairages du compte, v0.2.0

- Remplacement de l’association fixe A65/A60 par tous les éclairages compatibles du compte, avec plusieurs exemplaires d’un même modèle.
- Synchronisation des ajouts, suppressions et noms toutes les 30 secondes ; schémas relus toutes les cinq minutes ou à la demande.
- Conservation des profils et clés par identifiant d’appareil, sans publier ces données.
- Filtrage des catégories Lighting, exclusion des boîtiers HDMI et commandes adaptées aux fonctions déclarées.
- Grille défilante et menu de notification alimentés par ce catalogue ; suppression des réglages avancés.
- Correction du ciblage des commandes groupées : la commande suivante conservait une variable réaffectée lors du retour d’état.
- 113 tests automatiques, dont une file Qt complète avec trois cibles et une cible en erreur. Lecture réelle du compte et des deux éclairages sans modification de leur état.
- Appairage Windows examiné avec REA et les sources Tuya ; non livré faute de transport natif validé. L’ajout mobile est suivi par la synchronisation du compte.

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
