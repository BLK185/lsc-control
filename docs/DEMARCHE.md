# Démarche : de deux ampoules à une application Windows

## Le besoin

Commander une LSC A65 CCT et une A60 RGB-CCT depuis une vraie fenêtre de bureau et l’icône près de l’horloge. Le téléphone devait rester utilisable, avec le même compte et les mêmes programmations. L’accès depuis un autre réseau faisait partie de l’objectif. Une intégration Mac est envisagée, mais Windows a été priorisé.

## Codex et REA

Le développement a été réalisé en collaboration avec **OpenAI Codex**. Le propriétaire a fourni le besoin, les captures de l’application mobile, les retours d’utilisation et les autorisations de connexion et d’essai. Codex a contribué à l’analyse, à l’implémentation, aux tests et à l’assemblage Windows.

Le projet s’est appuyé sur **[REA — Reverse Engineer Anything](https://github.com/morluto/rea)**, utilisé depuis Codex. REA a servi à inspecter l’APK LSC et le client Electron de bureau : inventaire, recherche des méthodes de connexion, lecture des sources-map embarquées et suivi des appels QR/API. Les réponses runtime ont ensuite servi à vérifier les hypothèses avec le compte du propriétaire après son consentement.

Une observation statique a été traitée comme une piste, pas comme une preuve de fonctionnement. Le flux QR a été confirmé par une validation sur téléphone ; les commandes ont été vérifiées par lecture d’état puis par les retours physiques du propriétaire. Les schémas reçus ont servi à choisir les fonctions réellement présentes sur chaque ampoule.

Le transport Python a été comparé à la primitive native observée sur 20 cas de test aléatoires, avec et sans suffixe de session. Cette comparaison a permis de retirer la dépendance d’exécution à Electron et à la DLL fabricant dans l’application de développement. Les identités privées nécessaires au cloud ne sont pas redistribuées dans la version publique.

## Choix de conception

- **Pas de migration imposée** : conserver les ampoules dans LSC Smart Connect et lire les programmations existantes.
- **Local puis cloud** : associer les appareils par leur identifiant, utiliser le réseau local lorsqu’il répond, puis revenir au cloud si nécessaire.
- **Une commande est vérifiée** : relire l’état de l’appareil ; ne pas considérer une simple acceptation HTTP comme une validation physique.
- **Un seul planning partagé** : pas de second ordonnanceur sur le PC. Les ajouts et modifications passent par les opérations LSC et conservent leurs paramètres.
- **Une interface lisible** : commandes groupées mises en file, gestes validés au relâchement, unités hors des champs, saisie au clic, icônes d’action et thème violet/anthracite.
- **Des traces privées** : ne pas publier de session, de réponse de compte, de clé d’ampoule, d’APK, de DLL propriétaire ni de module d’identité.

## Limites connues

Les retours du propriétaire confirment marche/arrêt, blancs, couleurs et compte à rebours sur la RGB, ainsi que le fonctionnement du planning. Les tests automatiques n’allument aucune ampoule réelle. Les scènes disposent d’un codec et d’une interface, mais toutes leurs variations physiques ne sont pas encore confirmées. Les scènes non reçues utilisent des propositions locales, sans prétendre reconstruire tout le catalogue personnalisé du téléphone.

Les notifications Windows observent les changements marche/arrêt entre deux lectures. Elles ne constituent pas un abonnement aux événements push LSC et n’attribuent pas une variation à une programmation précise. La compatibilité d’autres modèles, la distribution cloud sans configuration et le déploiement Mac restent ouverts.

## Références techniques

- [REA](https://github.com/morluto/rea) et ses outils Android, JavaScript/Electron et natifs.
- [Tuya : connexion QR utilisateur](https://developer.tuya.com/en/docs/app-development/userqrlogin?id=Kceugtdh6y3h9).
- [Tuya : opérations de planning du SDK de panneaux](https://github.com/tuya/tuya-panel-sdk/blob/main/packages/tuya-panel-api/src/common/timer.ts).
- [TinyTuya](https://github.com/jasonacox/tinytuya), pour la communication LAN.

Ce dépôt documente un travail d’interopérabilité personnelle. Il ne revendique aucun partenariat avec LSC, Action, Tuya, OpenAI ou REA.
