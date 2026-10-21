# Confidentialité et signalements

Ne publiez jamais de mot de passe, QR code de connexion, session `sid`/`ecode`, clé locale d’ampoule, identifiant d’appareil, identifiant de maison, adresse IP personnelle ou module de connexion privé dans une issue, un commit ou une capture.

Le code d’association au Centre de contrôle est également privé. C’est un jeton
aléatoire séparé de la session LSC, enregistré dans le Trousseau par l’app et dans
la configuration locale de son extension. Il autorise uniquement l’inventaire
minimal des éclairages et leur marche/arrêt sur `127.0.0.1:47832`. L’API refuse les
origines navigateur, les hôtes différents et les autres opérations. Elle ne
retourne ni session LSC, ni identifiant fabricant, ni clé locale, ni planning.
Réinitialiser ce code depuis **Centre de contrôle…** révoque les anciens accès.
L’extension conserve son bac à sable et n’utilise aucun groupe d’applications.

Les sessions et clés locales utilisent le coffre du système via keyring. Les paramètres de l’application sont conservés dans le profil local `.lsc-control` ; ils ne font pas partie de l’installateur. Les composants de connexion préparés et les anciens modules importés restent dans ce profil. Ne partagez pas le dossier `connection/`, qui contient la configuration locale du client officiel. L’application n’intègre ni télémétrie ni compte utilisateur du mainteneur.

Le dépôt ignore les profils, journaux, rapports bruts, artefacts de recherche et fichiers de clés. La publication ajoute un contrôle des fichiers suivis et une comparaison locale avec les secrets connus du poste de développement. Ces contrôles complètent la revue humaine ; ils ne garantissent pas l’absence de toute donnée sensible imaginable.

Pour signaler une vulnérabilité, utilisez le signalement privé GitHub s’il est disponible. Sinon, ouvrez une issue sans détail exploitable ni secret pour convenir d’un canal privé. N’activez pas de logs réseau contenant vos jetons pour joindre un diagnostic.


Au premier usage, le composant Action et le lecteur 7-Zip sont téléchargés depuis leurs sources officielles. Leurs tailles et SHA-256 sont épinglés. Les redirections HTTPS sont limitées à des hôtes connus ; les fichiers différents sont refusés. Les installateurs ne sont pas exécutés. Le runtime extrait et vérifié exécute ensuite le pont natif de LSC Control pour les opérations LSC autorisées ; la préparation n’installe aucun service.
