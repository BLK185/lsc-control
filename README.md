# LSC Control

**Vos lumières LSC, dans une fenêtre et près de l’horloge Windows.**

[![Windows](https://github.com/BLK185/lsc-control/actions/workflows/windows.yml/badge.svg)](https://github.com/BLK185/lsc-control/actions/workflows/windows.yml)
[![Version](https://img.shields.io/badge/version-0.1.0-8A00FC)](https://github.com/BLK185/lsc-control/releases)
[![Licence MIT](https://img.shields.io/badge/licence-MIT-51007A)](LICENSE)

Une application de bureau pour deux ampoules déjà associées à LSC Smart Connect : **A65 CCT** et **A60 RGB-CCT**. L’objectif est de retrouver les réglages du téléphone, les commandes rapides et le planning partagé, sans imposer de migration vers une autre application.

Projet personnel développé avec **OpenAI Codex**, avec l’aide de **REA (Reverse Engineer Anything)** pour l’analyse d’interopérabilité. Il n’est ni édité ni certifié par LSC, Action ou Tuya.

![Interface Windows — données de démonstration](docs/images/windows.png)

## Première version Windows

Télécharger l’[installateur ou l’archive portable dans les releases](https://github.com/BLK185/lsc-control/releases). L’installateur s’utilise sans droits administrateur. Le programme n’est pas signé numériquement ; les empreintes SHA-256 sont jointes à chaque version.

**La version publique n’embarque aucun module privé de connexion au cloud.** Le QR code LSC nécessite l’import local d’un module compatible fourni séparément par l’utilisateur dans un cadre autorisé. Sans ce module, la démonstration et le mode local avancé restent disponibles. Aucun mot de passe, compte partagé ou identité fabricant n’est livré.

→ [Installation et configuration Windows](docs/INSTALLATION_WINDOWS.md)

## Ce que l’application permet

| Fonction | État |
| --- | --- |
| Marche/arrêt, luminosité, blancs chaud/froid | Implémenté |
| Couleur et saturation sur l’A60 RGB-CCT | Implémenté |
| Icône de notification, commandes individuelles et groupées | Implémenté |
| Compte à rebours interne à l’ampoule, jusqu’à 24 h | Implémenté et confirmé par le propriétaire sur la RGB |
| Lecture, ajout, modification, activation et suppression du planning LSC | Implémenté et confirmé par le propriétaire |
| Connexion QR au compte LSC existant | Fonctionnelle dans l’environnement de développement ; module local requis dans la distribution publique |
| Contrôle LAN rapide et repli cloud | Implémenté ; cloud selon configuration et disponibilité du service |
| Scènes et conservation des dernières variantes reçues | Implémenté ; validation physique complète encore à faire |
| Notifications Windows des changements marche/arrêt observés | Disponible ; ce ne sont pas les événements push LSC |
| macOS et Centre de contrôle | Envisagé après Windows ; non livré dans cette version |

Les changements du téléphone sont repris lors des lectures d’état. Le planning reste celui du compte LSC : aucun ordonnanceur parallèle n’est créé sur le PC. Le compte à rebours et les horaires continuent sans laisser l’ordinateur allumé.

Les scènes non reçues du compte utilisent des ambiances proposées ; l’application ne prétend pas importer tout le catalogue personnalisé du téléphone. La compatibilité d’autres modèles n’est pas établie.

## Une interface simple

Anthracite, violet profond et accent violet vif. Le minuteur sépare les unités des champs ; un clic sélectionne les chiffres à remplacer. Dans un horaire, heures et minutes s’éditent séparément.

Le planning utilise une icône **verte pour allumer**, **rouge pour éteindre**. L’activation de l’horaire est affichée à part.

| Compte à rebours | Planning |
| --- | --- |
| ![Compte à rebours — démonstration](docs/images/countdown.png) | ![Planning — démonstration](docs/images/planning.png) |

## Démarche et historique

- [Pourquoi et comment : Codex, REA, QR, LAN et planning partagé](docs/DEMARCHE.md)
- [Journal des étapes des 13, 14 et 18 octobre 2026](CHANGELOG.md)
- [Confidentialité et signalements](SECURITY.md)

Le journal reconstitue le travail à partir des notes et essais. Les commits de publication sont créés à leur date réelle ; ils ne simulent pas une activité GitHub passée.

## Développer et tester

Python 3.12 et Windows x64 sont l’environnement de référence.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r app/requirements-windows.lock.txt
.\.venv\Scripts\python.exe app/desktop.py --demo
.\.venv\Scripts\python.exe -m unittest discover -s app -p "test_*.py"
```

**90 tests automatiques** couvrent transports, conversions, planning, stockage des sessions, import privé, interaction des panneaux, saisie au clic et commandes du menu. Ils n’utilisent aucun compte réel. Les validations physiques du propriétaire sont indiquées séparément.

Pour compiler l’installateur public, installer [Inno Setup 6](https://jrsoftware.org/isdl.php), puis :

```powershell
.\.venv\Scripts\python.exe tools/build_windows.py
```

Les fichiers sont produits dans `release/`. Le script ne copie aucune identité privée ; la CI Windows suit la même recette et publie ses artefacts. Les releases publiques sont préparées après revue des fichiers et contrôle de confidentialité.

## Données et licences

Les sessions et clés des ampoules restent dans le coffre du système ; les paramètres et modules importés restent dans le profil local. Aucun profil du développeur n’est embarqué. Les captures du dépôt sont générées avec des données fictives. Les rapports bruts, APK, exécutables fabricant et identités privées sont exclus.

Code original sous [licence MIT](LICENSE). Les dépendances conservent leurs licences : [notices tierces](THIRD_PARTY_NOTICES.md).
