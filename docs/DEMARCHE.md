# Démarche : de deux ampoules à une application Windows et Mac

## Le besoin

Commander une LSC A65 CCT et une A60 RGB-CCT depuis une vraie fenêtre de bureau et l’icône près de l’horloge. Le téléphone devait rester utilisable, avec le même compte et les mêmes programmations. L’accès depuis un autre réseau faisait partie de l’objectif. Windows a été priorisé ; une première préversion macOS est maintenant préparée.

## Codex et REA

Le développement a été réalisé en collaboration avec **OpenAI Codex**. Le propriétaire a fourni le besoin, les captures de l’application mobile, les retours d’utilisation et les autorisations de connexion et d’essai. Codex a contribué à l’analyse, à l’implémentation, aux tests et à l’assemblage Windows.

Le projet s’est appuyé sur **[REA — Reverse Engineer Anything](https://github.com/morluto/rea)**, utilisé depuis Codex. REA a servi à inspecter l’APK LSC et le client Electron de bureau : inventaire, recherche des méthodes de connexion, lecture des sources-map embarquées et suivi des appels QR/API. Les réponses runtime ont ensuite servi à vérifier les hypothèses avec le compte du propriétaire après son consentement.

Une observation statique a été traitée comme une piste, pas comme une preuve de fonctionnement. Le flux QR a été confirmé par une validation sur téléphone ; les commandes ont été vérifiées par lecture d’état puis par les retours physiques du propriétaire. Les schémas reçus ont servi à choisir les fonctions réellement présentes sur chaque ampoule.

Le transport Python a été comparé à la primitive native observée sur 20 cas de test aléatoires, avec et sans suffixe de session. Cette comparaison a permis de retirer la dépendance d’exécution à Electron et à la DLL fabricant dans l’application de développement. Les identités privées ne sont pas redistribuées. Depuis la version 0.3.0, les nouvelles installations préparent localement le client officiel obtenu chez Action, puis utilisent son runtime et notre pont natif restreint. L’import manuel d’un module privé n’est plus nécessaire. Le transport Python autonome reste utilisé pour les profils qui en disposent déjà.

## Choix de conception

- **Catalogue du compte** : synchroniser les éclairages par identifiant stable, conserver leur profil après renommage et retirer les appareils absents d’un inventaire complet. Les catégories et schémas servent à filtrer Lighting et à proposer les réglages disponibles.
- **Pas de migration imposée** : conserver les ampoules dans LSC Smart Connect et lire les programmations existantes.
- **Local puis cloud** : associer les appareils par leur identifiant, utiliser le réseau local lorsqu’il répond, puis revenir au cloud si nécessaire.
- **Une commande est vérifiée** : relire l’état de l’appareil ; ne pas considérer une simple acceptation HTTP comme une validation physique.
- **Un seul planning partagé** : pas de second ordonnanceur sur le PC. Les ajouts et modifications passent par les opérations LSC et conservent leurs paramètres.
- **Une interface lisible** : commandes groupées mises en file, gestes validés au relâchement, unités hors des champs, saisie au clic, icônes d’action et thème violet/anthracite.
- **Des traces privées** : ne pas publier de session, de réponse de compte, de clé d’ampoule, d’APK, de DLL propriétaire ni de module d’identité.

## Limites connues

Les retours du propriétaire confirment marche/arrêt, blancs, couleurs et compte à rebours sur la RGB, ainsi que le fonctionnement du planning. Les tests automatiques n’allument aucune ampoule réelle. Les scènes disposent d’un codec et d’une interface, mais toutes leurs variations physiques ne sont pas encore confirmées. Les scènes non reçues utilisent des propositions locales, sans prétendre reconstruire tout le catalogue personnalisé du téléphone.

Les notifications Windows observent les changements marche/arrêt entre deux lectures. Elles ne constituent pas un abonnement aux événements push LSC et n’attribuent pas une variation à une programmation précise. La compatibilité physique des autres modèles et les essais sur le Mac du propriétaire restent ouverts. La préparation initiale dépend de la disponibilité du téléchargement officiel épinglé et du service LSC.

## Connexion distribuable — 21 octobre

Le défaut des premières distributions était réel : le QR dépendait d’un fichier privé absent du paquet. La correction prépare les composants sur chaque poste à partir des sources officielles, sans publier ce fichier ni les données du propriétaire. Le client Battletron 2.0.17 téléchargé chez Action a exactement le SHA-256 de l’artefact déjà examiné avec REA. Le lecteur 7-Zip 26.04 vient du dépôt officiel Igor Pavlov, avec empreinte contrôlée séparément.

Les installateurs sont seulement lus et extraits. Seul le runtime officiel vérifié exécute ensuite notre pont natif, caché, avec une liste bornée d’opérations et sans journaliser les données de compte. La configuration est analysée comme des valeurs littérales, sans exécuter le code JavaScript du paquet. Un identifiant d’installation est généré localement.

Validation : téléchargement et préparation depuis zéro dans un profil séparé, puis création d’un QR serveur sans restaurer de session. Une lecture authentifiée distincte a utilisé le nouveau runtime avec la session existante, sans commande ni modification d’horaire. Cela vérifie la préparation et les appels ; une validation sur téléphone reste nécessaire pour autoriser le compte propre à chaque nouvelle installation.

Ce mécanisme reste une intégration non officielle, liée au protocole et au composant Action connus ; il ne constitue pas une nouvelle identité applicative approuvée par LSC.

## Appairage et synchronisation

La version 0.2.0 sépare l’inventaire des appareils déjà associés de leur appairage initial. Les ajouts réalisés sur téléphone remontent automatiquement dans Windows. REA et la documentation primaire ont servi à examiner l’appairage, sans réinitialiser de lampe ni créer de jeton réel. La piste AP Wi-Fi nécessite un jeton de foyer, le transport UDP chiffré et la gestion Wi-Fi Windows ; les modes EZ, BLE, Zigbee et Matter ne sont pas interchangeables. Aucun appairage natif non validé n’est présenté comme fonction disponible.

## Portage macOS — 21 octobre

La fenêtre et la barre des menus partagent le moteur Python de Windows : catalogue dynamique, commandes, planning et compte à rebours. Le paquet ARM64 contient son interpréteur et ses bibliothèques ; le propriétaire autorise son propre compte par QR et ses secrets restent dans le Trousseau macOS.

La dépendance native Windows ne peut pas s’exécuter sur un Mac M4. REA a confirmé l’identité exacte de la DLL examinée ; les fournisseurs de décompilation native disponibles étaient absents ou incompatibles avec le poste. Une analyse locale ciblée des instructions et des ressources a permis de reconstruire le lecteur des parts polynomiales du BMP. Des données synthétiques indépendantes ont ensuite donné la même clé dérivée et la même signature avec la vraie primitive native. Aucune constante d’identité fabricant n’est copiée dans le code public : le lecteur accepte seulement les ressources de la version officielle épinglée.

Le transport Python a obtenu un QR réel sans session à partir de cette nouvelle préparation. La CI macOS construit le DMG, démarre l’exécutable en démonstration et demande un QR depuis un profil vierge, sans publier ce profil. Cela ne remplace pas la validation physique sur le Mac du propriétaire. Le Centre de contrôle natif reste séparé de la barre des menus et n’est pas annoncé comme livré : signature Apple et partage autorisé des commandes restent à mettre en place.

## Références du portage

- [Apple : contrôles WidgetKit](https://developer.apple.com/documentation/widgetkit/controls-collection).
- [Apple : accès aux groupes d’applications macOS et signature](https://developer.apple.com/documentation/xcode/accessing-app-group-containers).
- [GitHub : machines macOS Apple Silicon pour la compilation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job).

## Autres références techniques

- [Action : client Battletron officiel](https://www.action.com/fr-fr/brand/battletron-lsc-smart-gaming/).
- [7-Zip 26.04 officiel](https://github.com/ip7z/7zip/releases/tag/26.04) et [licences](https://www.7-zip.org/license.txt).
- [REA](https://github.com/morluto/rea) et ses outils Android, JavaScript/Electron et natifs.
- [Tuya : connexion QR utilisateur](https://developer.tuya.com/en/docs/app-development/userqrlogin?id=Kceugtdh6y3h9).
- [Tuya : opérations de planning du SDK de panneaux](https://github.com/tuya/tuya-panel-sdk/blob/main/packages/tuya-panel-api/src/common/timer.ts).
- [Tuya : catégories Lighting](https://developer.tuya.com/en/docs/iot/oemapp-light?id=Kb77kja5woao6).
- [Tuya : appairage AP Wi-Fi](https://developer.tuya.com/en/docs/app-development/hotspot-mode?id=Kaixk6wxla1oy).
- [TinyTuya](https://github.com/jasonacox/tinytuya), pour la communication LAN.

Ce dépôt documente un travail d’interopérabilité personnelle. Il ne revendique aucun partenariat avec LSC, Action, Tuya, OpenAI ou REA.
