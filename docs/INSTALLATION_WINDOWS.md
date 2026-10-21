# Installer LSC Control sous Windows

Cette version vise Windows 10/11 x64. L’application est personnelle, expérimentale et non officielle.

## Installation

1. Télécharger `LSC-Control-0.3.0-windows-x64-setup.exe` dans les [releases](https://github.com/BLK185/lsc-control/releases).
2. Lancer l’installateur. L’installation est propre à l’utilisateur et ne demande pas de droits administrateur.
3. Ouvrir LSC Control depuis le menu Démarrer. Un raccourci de bureau est facultatif.

Le programme et l’installateur ne sont pas signés numériquement. Windows peut afficher un avertissement de réputation. Comparer le SHA-256 du fichier au `SHA256SUMS.txt` de la même release avant de décider de l’exécuter.

La variante `portable.zip` s’utilise en extrayant **tout** le dossier, puis en ouvrant `LSC-Control.exe`. Le dossier `_internal` doit rester à côté de l’exécutable.

## Connexion LSC au premier lancement

1. Ouvrir **Connexion LSC…**, puis **Préparer la connexion LSC**.
2. Laisser télécharger environ 64 Mo. Les sources sont le [client officiel Action](https://www.action.com/fr-fr/brand/battletron-lsc-smart-gaming/) et le lecteur d’archives [7-Zip](https://github.com/ip7z/7zip/releases/tag/26.04). Les versions et SHA-256 sont épinglés ; un fichier différent est refusé. Les installateurs sont extraits sans installation système ni demande de droits administrateur.
3. Dans **LSC Smart Connect → Moi → scanner**, scanner le QR affiché et confirmer. Le téléphone peut nommer le client **LSC Battletron**.
4. Continuer : les éclairages du compte apparaissent dans la fenêtre et le menu près de l’horloge.

Aucun module privé n’est à récupérer auprès du développeur. Aucun mot de passe LSC n’est demandé par LSC Control. La session obtenue après votre validation reste dans le coffre Windows.

Si le téléchargement Action est indisponible, télécharger le programme depuis sa page officielle puis utiliser **Choisir le programme officiel déjà téléchargé…**. La version acceptée est Battletron **2.0.17**, vérifiée par empreinte. Le lecteur 7-Zip nécessite toujours un téléchargement de 2 Mo. Si cette version est retirée ou si le serveur change, la préparation devra être mise à jour ; elle n’essaie pas de contourner un refus du service.

Les composants officiels restent dans `%USERPROFILE%\.lsc-control\connection`. L’identifiant d’installation est généré sur votre poste ; aucune session, clé d’ampoule ou identité du développeur n’est copiée. Les anciens modules privés compatibles déjà importés restent utilisables.

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

Les paramètres et composants téléchargés restent dans `%USERPROFILE%\.lsc-control`. Les sessions et clés locales sont conservées dans le coffre Windows via keyring, service « LSC Control ». L’installateur ne contient aucun de ces éléments.

La désinstallation depuis les paramètres Windows retire les fichiers du programme et ses raccourcis. Elle conserve volontairement votre profil et vos entrées du coffre ; leur suppression éventuelle se fait séparément. Ne partagez pas ces données dans une issue GitHub.
