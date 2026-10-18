# Installer LSC Control sous Windows

Cette version vise Windows 10/11 x64. L’application est personnelle, expérimentale et non officielle.

## Installation

1. Télécharger `LSC-Control-0.2.0-windows-x64-setup.exe` dans les [releases](https://github.com/BLK185/lsc-control/releases).
2. Lancer l’installateur. L’installation est propre à l’utilisateur et ne demande pas de droits administrateur.
3. Ouvrir LSC Control depuis le menu Démarrer. Un raccourci de bureau est facultatif.

Le programme et l’installateur ne sont pas signés numériquement. Windows peut afficher un avertissement de réputation. Comparer le SHA-256 du fichier au `SHA256SUMS.txt` de la même release avant de décider de l’exécuter.

La variante `portable.zip` s’utilise en extrayant **tout** le dossier, puis en ouvrant `LSC-Control.exe`. Le dossier `_internal` doit rester à côté de l’exécutable.

## Connexion LSC : configuration locale nécessaire

La version publique ne fournit aucune identité applicative privée de fabricant. Elle n’est donc pas prête à se connecter au cloud LSC sans configuration supplémentaire.

Si vous disposez déjà d’un module de connexion compatible obtenu dans un cadre autorisé, ouvrir **Connexion LSC → Importer le module de connexion** et sélectionner son fichier JSON. Ce module doit contenir uniquement `defaults` et `portable_signing_key`, jamais une session ou une clé d’ampoule. Il est copié dans votre profil local, pas dans le dépôt.

Ensuite, scanner le QR code depuis **LSC Smart Connect → Moi → scanner**, et confirmer sur le téléphone. Le serveur peut désigner le client comme « LSC Battletron ». Aucun mot de passe LSC n’est demandé par cette application.

Sans module, la démonstration reste utilisable. Les anciens profils locaux sont conservés, mais l’éditeur « Réglages avancés » a été supprimé : la connexion au compte et les fonctions déclarées par les éclairages remplacent la saisie des modèles, identifiants et clés. Le dépôt ne fournit ni accès partagé, ni compte de démonstration réel, ni module de connexion à télécharger.

## Utilisation

- Ajouter ou retirer un éclairage dans LSC mobile : la liste Windows est synchronisée environ toutes les 30 secondes lorsque l’application tourne. **Synchroniser** force aussi la relecture des fonctions. Il n’y a plus de limite à une ampoule blanche et une RGB.
- L’application vise Lighting : ampoules, rubans, guirlandes et luminaires reconnus, en excluant les boîtiers HDMI et les appareils des autres catégories. Seuls les réglages déclarés modifiables sont proposés ; chaque modèle supplémentaire reste à valider sur du matériel réel.
- **Connexion locale rapide** retrouve les éclairages du compte sur le réseau courant. Cette détection ne les appaire pas ; le cloud reste utilisé lorsqu’ils ne répondent pas en local.
- L’appairage initial reste à faire sur le téléphone. Le transport de configuration Wi-Fi/Bluetooth propre à LSC n’est pas encore implémenté et validé sous Windows.

- Cliquer sur les chiffres du minuteur pour les remplacer directement. Dans un horaire, cliquer sur les heures ou les minutes pour modifier la partie choisie.
- Les icônes du planning décrivent l’action : **vert = allumer**, **rouge = éteindre**. « Activé » indique séparément si l’horaire est en service.
- Fermer la fenêtre laisse l’application dans la zone de notification. Un clic gauche rouvre la fenêtre ; un clic droit affiche les commandes. Choisir « Quitter » pour arrêter complètement le programme.
- Les horaires partagés et le compte à rebours sont gérés par LSC/l’ampoule. Le PC n’a pas besoin de rester allumé pour leur exécution.

## Données et désinstallation

Les paramètres restent dans `%USERPROFILE%\.lsc-control`. Les sessions et clés locales sont conservées dans le coffre Windows via keyring, service « LSC Control ». L’installateur ne contient aucun de ces éléments.

La désinstallation depuis les paramètres Windows retire les fichiers du programme et ses raccourcis. Elle conserve volontairement votre profil et vos entrées du coffre ; leur suppression éventuelle se fait séparément. Ne partagez pas ces données dans une issue GitHub.
