# Confidentialité et signalements

Ne publiez jamais de mot de passe, QR code de connexion, session `sid`/`ecode`, clé locale d’ampoule, identifiant d’appareil, identifiant de maison, adresse IP personnelle ou module de connexion privé dans une issue, un commit ou une capture.

Les sessions et clés locales utilisent le coffre du système via keyring. Les paramètres de l’application sont conservés dans le profil local `.lsc-control` ; ils ne font pas partie de l’installateur. Le module de connexion importé reste dans ce profil. L’application n’intègre ni télémétrie ni compte utilisateur du mainteneur.

Le dépôt ignore les profils, journaux, rapports bruts, artefacts de recherche et fichiers de clés. La publication ajoute un contrôle des fichiers suivis et une comparaison locale avec les secrets connus du poste de développement. Ces contrôles complètent la revue humaine ; ils ne garantissent pas l’absence de toute donnée sensible imaginable.

Pour signaler une vulnérabilité, utilisez le signalement privé GitHub s’il est disponible. Sinon, ouvrez une issue sans détail exploitable ni secret pour convenir d’un canal privé. N’activez pas de logs réseau contenant vos jetons pour joindre un diagnostic.
