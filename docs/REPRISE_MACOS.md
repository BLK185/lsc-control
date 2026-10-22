# Reprendre le diagnostic dans Codex sur Mac

État au 22 octobre 2026. Cette note ne contient aucun identifiant ni code de connexion.

## Ouvrir le projet

Ouvrir dans Codex le dossier local du dépôt
[BLK185/lsc-control](https://github.com/BLK185/lsc-control).
S'il existe déjà, conserver ses modifications avant toute mise à jour.
Sinon, dans le Terminal du Mac, depuis le dossier où ranger le projet :

```sh
git clone https://github.com/BLK185/lsc-control.git
```

Ajouter ensuite le dossier `lsc-control` comme projet local dans Codex.
La conversation et l'accès aux fichiers sont distincts : cette note fournit
le contexte même si la conversation Windows n'est pas disponible sur le Mac.

Message de reprise :

> Lis docs/REPRISE_MACOS.md et les instructions du dépôt. Reproduis puis corrige
> sur ce Mac la latence de LSC Control et les commandes natives du Centre de
> contrôle, avec une commande configurable par éclairage. Commence par vérifier
> la version réellement exécutée et observer l'échec dans le vrai Centre de
> contrôle. Préserve ma session LSC, mon Trousseau et mes horaires. Ne publie
> aucun secret. Vérifie le résultat dans macOS avant d'annoncer la correction.

## Ce qui fonctionne et ce qui reste ouvert

- Le propriétaire utilise un MacBook Air M4. Relever le numéro exact avec
  `sw_vers` ; le nom de version fourni oralement ne suffit pas.
- L'app Mac et sa barre des menus ont fonctionné avec le compte LSC, mais une
  forte latence a ensuite été signalée.
- L'extension apparaît dans la galerie native. Les captures montrent une
  commande vide avec un chargement et un éditeur dont les champs « Code de
  connexion » et « Éclairage » sont vides. On ne sait pas encore à quelle étape
  la configuration échoue, ni si le dernier paquet est réellement exécuté.
- Le propriétaire veut autant de commandes natives que d'éclairages. L'ajout
  multiple et l'exécution depuis le vrai Centre de contrôle restent à valider.
- Dernière release : [v0.5.1-beta.1](https://github.com/BLK185/lsc-control/releases/tag/v0.5.1-beta.1),
  source `5982eba`, suivie du commit documentaire `bd31954`.
- La CI a validé les tests Python, le client Swift sandboxé, les providers et
  intentions, la construction ARM64 et l'enregistrement de l'extension. Cela
  ne valide pas les interactions dans l'hôte WidgetKit réel.

## Diagnostic à faire sur le Mac

1. Identifier le chemin et la version du processus actif. Fermer la fenêtre
   laisse l'app ouverte : utiliser Quitter ou `⌘Q` avant remplacement. Vérifier
   qu'une ancienne copie ou une app lancée depuis le DMG ne reste pas active.
2. Reproduire l'ajout et la configuration native en observant les journaux
   pertinents de WidgetKit, AppIntents et du Centre de contrôle. Ne pas se
   contenter du test Swift en ligne de commande.
3. Dans l'app, ouvrir « Centre de contrôle… », copier le code puis le coller
   avec `⌘V` dans la valeur du champ natif « Code de connexion ». Observer si
   une liste d'éclairages apparaît et si les requêtes atteignent l'app.
   Son dialogue indique attente, code refusé ou requêtes reçues. Ne jamais
   demander au propriétaire de coller le code dans la conversation.
4. Vérifier le choix d'un éclairage, l'action marche/arrêt et la persistance
   après relance. Ajouter une seconde instance avec un autre éclairage et
   vérifier que les deux destinations restent indépendantes.
5. Mesurer la latence par phase sans journaliser les données privées : attente
   dans la file, accès LSC, écriture, relecture de confirmation, délai local.
   Vérifier l'autorisation Réseau local et l'utilisation effective du chemin LAN.
   Une réponse d'envoi seule ne prouve pas que l'ampoule a changé d'état.

## Repères dans le code

| Fichier | Rôle |
| --- | --- |
| `app/desktop.py` | Interface Qt, file des commandes, rafraîchissements et découverte locale |
| `app/core.py` | Transports, caches d'états et détails, stockage |
| `app/lsc_account.py`, `app/lsc_portable.py` | Compte LSC, session HTTPS, inventaire dynamique |
| `app/macos_runtime.py` | Intégration Mac, service natif, rechargement des commandes |
| `app/control_center.py` | API locale authentifiée sur `127.0.0.1:47832` |
| `macos/Controls/LampControls.swift` | Entité éclairage, configuration, provider, SetValueIntent |
| `macos/Shared/ControlsClient.swift` | Client HTTP de l'extension, code dans ses préférences sandboxées |
| `macos/ReloadControls.swift` | Rechargement WidgetKit depuis le processus de l'app |
| `tools/check_controls_macos.py`, `macos/Tests/Probe.swift` | Tests Swift et vérifications du paquet |
| `app/test_responsiveness.py` | Tests de priorité des commandes et réduction des lectures |

Le bundle principal est `fr.carfr.LSCControl`, l'extension
`fr.carfr.LSCControl.Controls`. Il n'y a pas d'App Group. L'extension n'accède
pas à la session LSC : elle utilise un code local distinct et l'app doit rester
active. Le service refuse les accès non authentifiés.

La version 0.5.1 réutilise les connexions HTTPS et les états vérifiés récents,
priorise les commandes entre les lectures et lance la découverte LAN en arrière-plan.
Elle demande la configuration native à l'ajout et protège le cas sans éclairage
sélectionné. Ces changements ne constituent pas une résolution confirmée sur ce Mac.

## Environnement, données et vérification

Lire `docs/INSTALLATION_MACOS.md` et `.github/workflows/macos.yml` avant de
construire. L'app distribuée est autonome ; construire les sources demande
Python 3.12 ARM64 et, pour l'extension, Xcode avec SDK macOS 26 et XcodeGen.
Inspecter les outils déjà présents avant d'installer des dépendances.
Sur Mac, un environnement virtuel utilise `app/.venv/bin/python` ; ne pas copier
l'environnement Windows. Les dépendances sont dans `app/requirements-macos.lock.txt`.

Préserver `~/.lsc-control` et les entrées du Trousseau du service « LSC Control ».
Le journal de démarrage éventuel est `~/.lsc-control/startup-error.log` ; le lire
localement et masquer les données privées avant tout partage. Ne pas importer
le profil dans Git, les rapports, les paquets ou les captures publiées.
Ne pas réinitialiser les ampoules ni modifier les vrais horaires pour ce diagnostic.

L'app n'a pas de signature Developer ID ni de notarisation. Diagnostiquer les
signatures et l'enregistrement sans désactiver Gatekeeper ou SIP, inventer une
identité Apple ou modifier les bases protégées de macOS.

Après correction, exécuter les tests appropriés, puis valider réellement dans
le Centre de contrôle avec le propriétaire. Avant publication, exécuter
`python tools/check_publication.py --tracked --known-local` dans l'environnement
du projet ; auditer aussi le paquet s'il est distribué. Ne pas publier les codes
locaux, sessions, clés, profils, journaux bruts ou captures privées.
