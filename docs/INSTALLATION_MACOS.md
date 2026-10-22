# Installer LSC Control sur Mac Apple Silicon

Préversion 0.5.1 — Mac M1, M2, M3, M4 et suivants, macOS 13 ou ultérieur.
Les commandes natives expérimentales nécessitent macOS 26 ou ultérieur.
Cette version ARM64 contient Python et ses dépendances. Rosetta, Homebrew et
un compte développeur Tuya ne sont pas nécessaires.

1. Télécharger le DMG ARM64 correspondant à la version souhaitée depuis les releases GitHub.
2. Ouvrir le DMG puis glisser **LSC Control** dans **Applications**.
3. Lancer l’application depuis Applications.

## Première ouverture

Le paquet est signé localement pour son intégrité, mais **n’a pas de signature
Apple Developer ID ni de notarisation**. macOS peut donc bloquer sa première
ouverture. Après avoir essayé de l’ouvrir, utiliser **Réglages Système →
Confidentialité et sécurité → Ouvrir quand même**, si cette option est proposée.
Ne pas désactiver Gatekeeper. Les empreintes SHA-256 accompagnent les fichiers.

## Connecter son compte LSC

Ouvrir **Connexion LSC… → Préparer la connexion LSC**. Environ 64 Mo sont
téléchargés depuis les sources officielles Action et 7-Zip, avec vérification
de leur taille et de leur empreinte. Le client Windows est lu comme une archive :
aucun code Windows n’est exécuté sur le Mac. Les ressources nécessaires restent
sur ce Mac et ne sont pas incluses dans l’application distribuée.

Scanner ensuite le QR depuis **LSC Smart Connect → Moi → scanner**, puis confirmer
sur le téléphone. Il peut identifier le client comme **LSC Battletron**.
La session et les clés locales restent dans le **Trousseau macOS**. Le Mac doit
être autorisé séparément ; aucune session du développeur n’est fournie.

Les éclairages du compte apparaissent automatiquement. Les ajouts, retraits et
renommages depuis le téléphone sont synchronisés environ toutes les 30 secondes,
application ouverte. **Synchroniser** force cette lecture. Seuls les éclairages
compatibles sont retenus ; les boîtiers HDMI sont exclus.

## Fenêtre et barre des menus

L’icône d’ampoule en haut de l’écran donne accès aux commandes individuelles,
couleurs, blancs, luminosité, scènes disponibles, planning et compte à rebours.
Fermer la fenêtre laisse l’application active dans cette barre. **Afficher LSC
Control** rouvre la fenêtre ; **Quitter** ou `⌘Q` arrête l’application.

Les horaires sont ceux du compte LSC et restent partagés avec le téléphone.
Le contrôle à distance utilise le service LSC. **Connexion locale rapide** peut
retrouver les éclairages du même réseau ; macOS peut demander l’accès au réseau
local. Aucun appairage natif Mac n’est fourni : ajouter les appareils dans LSC mobile.

## Centre de contrôle natif — expérimental, macOS 26+

L’extension WidgetKit fournit une commande **Éclairage LSC**, configurable pour
un appareil du compte ou pour **Tous les éclairages**. Elle commande le
marche/arrêt ; les autres réglages restent dans l’app et la barre des menus.

1. Remplacer l’ancienne app dans Applications, puis lancer la nouvelle au moins une fois.
2. Dans le menu de LSC Control ou son icône d’ampoule, ouvrir **Centre de contrôle…**.
3. Cliquer **Copier le code de connexion**.
4. Ouvrir le Centre de contrôle du Mac → **Modifier les commandes** → chercher **LSC Control** → ajouter **Éclairage LSC**.
5. La nouvelle commande ouvre sa configuration : cliquer dans la valeur à droite de **Code de connexion**, coller avec `⌘V`, puis choisir l’éclairage et valider.
6. Pour chaque autre ampoule, faire glisser à nouveau **Éclairage LSC** depuis la galerie et choisir une autre ampoule. Retirer les anciennes commandes vides de la beta précédente avant de recommencer.

Les commandes suivantes peuvent réutiliser cette association. Ajouter plusieurs
fois **Éclairage LSC** pour commander plusieurs lampes séparément. Garder l’app
active dans la barre des menus. Si le code est réinitialisé dans l’app,
recopier le nouveau code dans les commandes déjà configurées.

Cette voie utilise un accès HTTP limité à cet ordinateur, protégé par un code
aléatoire distinct de la session LSC. Elle ne demande aucun groupe d’applications
Apple ni partage du Trousseau entre processus. L’extension reste signée localement,
sans Developer ID ni notarisation. Son affichage et son exécution dans le vrai
Centre de contrôle doivent être confirmés sur le Mac du propriétaire ; un simple
enregistrement par macOS ne constitue pas cette validation.

Si **LSC Control** n’apparaît pas dans la galerie après installation et lancement,
signaler ce résultat avec le numéro exact de macOS. Ne pas modifier les protections
de macOS pour forcer l’extension. La version 0.4.0 reste disponible et son app ainsi
que sa barre des menus ont été validées par le propriétaire sur Mac M4.

## Données et limites

Les paramètres sont dans `~/.lsc-control`, les secrets dans le Trousseau.
Déplacer l’application ou installer une mise à jour ne supprime pas le profil.
Le service LSC reste une intégration non officielle et peut changer.
Les fonctions physiques déjà validées sous Windows restent à essayer sur le Mac.
Les notifications de bureau signalent les changements d’état observés ; elles
ne reproduisent pas les événements push de LSC.

Construction depuis les sources : Python 3.12 ARM64, puis
`python -m pip install -r app/requirements-macos.lock.txt` et
`python tools/build_macos.py`, sur un Mac Apple Silicon.

## Réactivité — correctifs 0.5.1

Les commandes prennent la priorité sur la suite des lectures en cours. La recherche locale s’effectue automatiquement sur Mac, en arrière-plan, et peut être relancée avec Connexion locale rapide. Les connexions HTTPS au service LSC sont réutilisées. Une description d’ampoule vérifiée il y a moins de 15 secondes évite une lecture préalable redondante ; l’état après écriture est toujours relu pour confirmer la commande.

Le contrôle natif réutilise l’état récent vérifié par l’app. Sans configuration, il affiche Choisir une ampoule plutôt qu’un chargement permanent. La fenêtre Centre de contrôle… indique si des requêtes natives sont reçues ou si le code est refusé. La diminution effective de la latence et l’ajout multiple restent à confirmer sur le Mac du propriétaire.
