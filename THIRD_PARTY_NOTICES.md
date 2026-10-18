# Logiciels tiers

La licence MIT de ce dépôt couvre le code original de LSC Control. Les dépendances conservent leurs propres licences. Les distributions Windows comportent un dossier `licenses/` avec les textes disponibles dans les distributions Python utilisées.

| Composant | Usage | Projet |
| --- | --- | --- |
| Python | Exécution embarquée | https://www.python.org/ |
| PySide6 / Qt | Interface et zone de notification | https://doc.qt.io/qtforpython-6/ |
| TinyTuya | Communications locales avec les ampoules | https://github.com/jasonacox/tinytuya |
| Requests | HTTPS | https://requests.readthedocs.io/ |
| cryptography | Primitives cryptographiques | https://cryptography.io/ |
| keyring | Coffre système | https://github.com/jaraco/keyring |
| qrcode | Affichage du QR code | https://github.com/lincolnloop/python-qrcode |
| PyInstaller | Assemblage Windows | https://pyinstaller.org/ |
| Inno Setup | Installateur | https://jrsoftware.org/ |

PySide6 et les bibliothèques Qt sont distribués sans modification, sous leurs licences applicables, notamment LGPLv3/GPLv3. Leurs DLL restent séparées de l’exécutable et peuvent être remplacées par des versions compatibles. Les sources et informations de compilation sont disponibles sur https://code.qt.io/ et https://www.qt.io/qt-for-python. Les notices fournies font autorité pour chaque fichier.

LSC, LSC Smart Connect, Action, Tuya, NZXT et les autres marques citées appartiennent à leurs propriétaires. Aucune affiliation ni certification n’est revendiquée. Aucun APK, client propriétaire, DLL fabricant ni identité applicative privée n’est redistribué dans le dépôt ou les versions publiques.
