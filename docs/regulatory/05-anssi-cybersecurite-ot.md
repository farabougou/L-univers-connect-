# Cybersécurité OT / GTB — ANSSI

## Référence officielle

- ANSSI, cybersécurité des systèmes industriels (mesures détaillées) :
  <https://www.ssi.gouv.fr/> (guides « La cybersécurité des systèmes
  industriels »).
- Les systèmes OT (Operational Technology — automatismes, terrain,
  équipements physiques) ont des contraintes différentes de l'IT classique :
  disponibilité et sûreté physique prioritaires sur la confidentialité,
  cycle de vie des équipements beaucoup plus long, protocoles de terrain
  souvent sans authentification native (Modbus, BACnet).

## Ce qu'ENORYX doit prévoir

Utiliser les recommandations ANSSI pour l'architecture Edge/OT :
segmentation, identités, accès, journalisation et résilience.

## Audit de l'architecture existante contre les thèmes ANSSI (02/10/2026)

| Thème ANSSI | Mesure déjà en place | Où |
|---|---|---|
| **Réduire la surface d'attaque** | Règle non négociable 1 : aucune commande vers un équipement réel, lecture seule garantie en base (`ck_points_read_only_c0`) — élimine la catégorie de risque la plus grave en OT (une commande non autorisée sur un équipement physique) avant même de parler de cybersécurité | `app/connectors/modbus.py` (aucune fonction d'écriture), migration F3 |
| **Segmentation** | L'agent Edge se place entre le bus de terrain (Modbus/BACnet/OPC UA/MQTT, local au site) et le cloud (HTTPS sortant uniquement) : aucun équipement de terrain n'est exposé directement à Internet, aucun port entrant requis sur le site du client | `services/edge-agent` (démons par protocole) |
| **Identités et accès** | Identité des appareils Edge par paire de clés asymétriques (EC P-256) et preuve cryptographique à usage unique (JWT ES256, anti-rejeu), jamais un secret partagé transmis en clair pour les nouveaux appareils ; identité des personnes séparée (OIDC/Keycloak), jamais confondue avec celle des machines | `app/devices.py`, ADR 012 §2.10 |
| **Journalisation** | Journal d'audit append-only chaîné par hachage pour toute action sensible ; journal système séparé (`app/events.py`) pour les changements de connectivité, données périmées, cycle de vie des commandes, raccordé à la chronologie consultable | `app/audit.py`, `app/events.py`, `app/timeline.py` |
| **Résilience / tolérance aux pannes** | Un tenant en échec n'empêche jamais les autres (balayage périodique par tenant, `app/supervision_sweep.py`) ; donnée périmée détectée et signalée plutôt que silencieusement ignorée | `app/monitoring.py` |
| **Durcissement des composants** | Connecteurs protocolaires indépendants du fabricant, derrière un adaptateur (jamais de dépendance à un constructeur dans le noyau) | `app/connectors/` |

## Lacunes identifiées, honnêtement signalées

- **Pas de politique de segmentation réseau formalisée** : la segmentation
  décrite ci-dessus découle de l'architecture logicielle (Edge en sortant
  seulement), pas d'une politique réseau documentée et auditée sur le
  terrain — à produire une fois un premier site réel déployé (dépend du
  réseau du client, hors du contrôle du code).
- **Pas de détection d'intrusion ni de supervision de sécurité dédiée**
  (SIEM, détection d'anomalie réseau OT) : le journal d'audit existe, son
  exploitation par un outil de détection reste à construire.
- **Pas de plan de réponse à incident documenté** (qui fait quoi en cas de
  compromission d'un appareil Edge ou d'une fuite) — à écrire avec
  l'exploitant réel, pas à deviner depuis le code.
- **mTLS transport et PKI gérée (autorité de certification, rotation
  automatisée) : `DEFER`**, déjà signalé dans la feature-benchmark-matrix
  (ligne « Identité des appareils Edge / PKI ») — le concept d'identité ne
  changera pas quand cette étape sera construite.

## Décision

**KEEP** les mesures déjà en place (aucune n'a été ajoutée pour cette
directive : elles existaient déjà pour d'autres raisons de sécurité et se
trouvent alignées avec les thèmes ANSSI a posteriori). **DEFER** la
politique de segmentation formalisée et le plan de réponse à incident :
tous deux dépendent d'un déploiement réel chez un client, pas d'une
décision que le code peut prendre seul — cohérent avec
`DEFERRED_EXTERNAL_INTEGRATION`/`TO_FINALIZE` même si la cause ici est
opérationnelle plutôt qu'un compte ou une API manquante.
