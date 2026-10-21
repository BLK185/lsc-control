# Installer LSC Control sur Mac Apple Silicon

Version 0.4.0 — Mac M1, M2, M3, M4 et suivants, macOS 13 ou ultérieur.
Cette version ARM64 contient Python et ses dépendances. Rosetta, Homebrew et
un compte développeur Tuya ne sont pas nécessaires.

1. Télécharger `LSC-Control-0.4.0-macos-arm64.dmg` depuis les releases GitHub.
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

## Centre de contrôle natif

Cette distribution fournit la **barre des menus**. Elle ne fournit pas encore
une extension fonctionnelle du Centre de contrôle. Une telle extension doit
être signée et partager ses commandes avec l’app au moyen d’un groupe
d’applications autorisé par Apple. Aucun certificat de distribution n’est
actuellement configuré pour ce projet.

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
