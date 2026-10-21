# Logiciels tiers

La licence MIT de ce dépôt couvre le code original de LSC Control. Les dépendances conservent leurs propres licences. Les distributions Windows et macOS comportent un dossier `licenses/` avec les textes disponibles dans les distributions Python utilisées (sur Mac : `LSC Control.app/Contents/Resources/licenses`).

| Composant | Usage | Projet |
| --- | --- | --- |
| Python | Exécution embarquée | https://www.python.org/ |
| PySide6 / Qt | Interface et zone de notification | https://doc.qt.io/qtforpython-6/ |
| TinyTuya | Communications locales avec les ampoules | https://github.com/jasonacox/tinytuya |
| Requests | HTTPS | https://requests.readthedocs.io/ |
| cryptography | Primitives cryptographiques | https://cryptography.io/ |
| keyring | Coffre système | https://github.com/jaraco/keyring |
| qrcode | Affichage du QR code | https://github.com/lincolnloop/python-qrcode |
| PyInstaller | Assemblage Windows et macOS | https://pyinstaller.org/ |
| Inno Setup | Installateur | https://jrsoftware.org/ |

PySide6 et les bibliothèques Qt sont distribués sans modification, sous leurs licences applicables, notamment LGPLv3/GPLv3. Leurs DLL restent séparées de l’exécutable et peuvent être remplacées par des versions compatibles. Les sources et informations de compilation sont disponibles sur https://code.qt.io/ et https://www.qt.io/qt-for-python. Les notices fournies font autorité pour chaque fichier.

LSC, LSC Smart Connect, Action, Tuya, NZXT et les autres marques citées appartiennent à leurs propriétaires. Aucune affiliation ni certification n’est revendiquée. Aucun APK, client propriétaire, DLL fabricant ni identité applicative privée n’est redistribué dans le dépôt ou les versions publiques.


## Composants obtenus au premier lancement

Ils ne sont pas inclus dans les releases LSC Control. La préparation télécharge le client propriétaire **LSC Battletron 2.0.17 depuis Action**, et le lecteur **7-Zip 26.04 depuis le dépôt officiel ip7z/7zip**, avec taille et SHA-256 contrôlés. Les textes de licence du client (dont Electron/Chromium) restent dans le dossier local extrait. Les fichiers 7-Zip ne servent qu’à l’extraction dans le dossier temporaire, ensuite supprimé ; aucune copie n’est installée au niveau système.

Ces logiciels conservent leurs licences respectives ; la licence MIT du projet ne les couvre pas. Sources et licences 7-Zip : https://github.com/ip7z/7zip/releases/tag/26.04 et https://www.7-zip.org/license.txt . LSC Control ne revendique ni droit de redistribution du client propriétaire ni approbation de son intégration par le fabricant.
