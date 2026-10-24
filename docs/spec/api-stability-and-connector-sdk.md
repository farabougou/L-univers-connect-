# Stabilité de l'API et SDK de connecteur (V4, priorité « API / Écosystème »)

ADR de référence : `docs/adr/012-fondations-architecture-v2.md` §2.12 (contrat
du SDK de connecteur). Ce document rend ce contrat concrètement exploitable —
par un développeur de ce dépôt aujourd'hui, par un intégrateur externe le
jour où cela a du sens — sans en changer une ligne.

## 1. Stabilité et versioning de l'API

**État réel (07/10/2026)** : l'API n'a aujourd'hui qu'un seul contrat, non
préfixé (`/sites`, `/points`, `/connectors`, …), consommé par trois clients
que nous maîtrisons entièrement (web, mobile, démons Edge). Aucun tiers
externe n'en dépend encore. Introduire un préfixe `/v1/` maintenant serait un
changement cassant sur toutes les routes, pour un bénéfice nul tant qu'aucun
second consommateur indépendant n'existe — l'inverse de « produire d'abord
l'impact architectural avant toute modification majeure ».

**Politique retenue, applicable dès maintenant, sans changement d'URL** :

- Tant qu'un seul jeu de clients (celui de ce dépôt) consomme l'API, chaque
  évolution reste **additive** : un champ ajouté à une réponse, un paramètre
  optionnel ajouté à une requête, un nouvel endpoint. Jamais un champ
  renommé, retiré ou dont le sens change sous le même nom — c'est la
  définition opérationnelle de « stable » ici.
- Le jour où un premier consommateur réellement externe apparaît
  (intégrateur, partenaire), **c'est cet événement, pas une date**, qui
  déclenche : (1) le gel explicite du contrat alors en vigueur sous un
  préfixe `/v1/`, (2) toute évolution incompatible désormais passée par un
  nouveau préfixe (`/v2/`) servi en parallèle, jamais un remplacement sur
  place. Le code applicatif (`app/routers/*.py`) n'a pas besoin de changer
  pour que ce jour-là arrive : un préfixe FastAPI s'ajoute par-dessus les
  routeurs existants (`APIRouter(prefix="/v1")`), jamais une réécriture.
- Risque de blocage à surveiller (section dédiée de l'ADR 012) : si cette
  politique n'est pas suivie — un champ renommé sans y penser — le premier
  consommateur externe le découvrirait en cassant. Revue de code : tout
  changement de forme d'une réponse déjà publique doit se demander
  explicitement « un consommateur existant casse-t-il ? ».
- `GET /connectors` (V4, catalogue des connecteurs) porte déjà
  `schema_version` par connecteur — le même principe appliqué à un objet
  précis avant de l'appliquer à l'API entière : une preuve que la discipline
  de versioning est déjà pratiquée, pas seulement écrite ici.

## 2. SDK de connecteur : ajouter un cinquième protocole de terrain

Le contrat (ADR 012 §2.12) n'est pas théorique : les quatre connecteurs
existants (Modbus, BACnet, OPC UA, MQTT) le suivent déjà, chacun avec ses
propres tests de conformité par injection de pannes. Ajouter un cinquième
protocole suit exactement les mêmes étapes — jamais une nouvelle
abstraction, jamais un nouveau moteur. Repère concret : MQTT
(`app/connectors/mqtt.py`) est le plus récent des quatre et le plus simple à
relire en entier avant de commencer.

1. **`app/connectors/<protocole>.py`** — une fonction de lecture pure
   (`read_<protocole>_points(host, port, points) -> dict[str, float]`), une
   exception dédiée (`<Protocole>ReadError`), une structure `<Protocole>Point`
   (nom logique → adresse réelle dans le protocole). Jamais de fonction
   d'écriture : la règle non négociable 1 ne laisse aucune exception pour un
   appareil réel.
2. **`app/connectors/device_mapping.py`** — un type de configuration
   `<PROTOCOLE>_DEVICE_MAPPING` (voir `MQTT_DEVICE_MAPPING` comme modèle),
   son schéma de version, un modèle Pydantic de contenu, enregistré via
   `register_config_type`. C'est ce type qui rend la configuration
   versionnée (ADR 012 §2.11), jamais une table de plus.
3. **`scripts/<protocole>_daemon.py`** — même structure que les quatre
   démons existants : lit la configuration active (`GET /edge/config/<protocole>`),
   relève à intervalle régulier, met en tampon localement
   (`app/connectors/offline_buffer.py`) si l'API est injoignable, reporte
   `AGENT_VERSION` et la taille de son tampon à chaque relève réussie (V4,
   santé de la flotte — voir `app/connectors/edge_client.py`).
4. **`app/connectors/catalog.py`** — une entrée de plus dans
   `CONNECTOR_CATALOG` : protocole, capacités réellement implémentées,
   `certification_level="experimental"` au départ (jamais `"verified"` sans
   la suite de tests de l'étape 5). `GET /connectors` et la section
   « Connecteurs » de l'écran web `/edge` l'affichent **sans aucun changement
   de code supplémentaire** — c'est le bénéfice concret d'avoir un catalogue
   déclaratif plutôt qu'un écran codé en dur par protocole.
5. **Tests de conformité** — contre un vrai serveur/courtier du protocole
   (jamais un mock, jamais un équipement physique réel) : hôte injoignable,
   identifiant/sujet/nœud inconnu, valeur invalide. C'est cette suite,
   quand elle existe et passe, qui justifie de passer
   `certification_level` à `"verified"` dans le catalogue — jamais une
   déclaration sans preuve.
6. **Documentation** — une entrée KEEP/REFACTOR/REPLACE/ADD/DEFER dans
   `docs/spec/feature-benchmark-matrix.md`, comme pour MQTT.

**Ce qui n'est délibérément pas construit** : un mécanisme de chargement
dynamique de connecteurs tiers (plugins installés à chaud, marketplace).
Avec quatre connecteurs maintenus dans ce dépôt et aucun intégrateur externe
aujourd'hui, un tel mécanisme serait une architecture pour un besoin
hypothétique — **DEFERRED**, à concevoir le jour où un premier connecteur
réellement externe au dépôt le justifie (voir aussi « droits
intégrateurs/prestataires », DEFERRED pour la même raison, feature-benchmark-matrix.md).

## 3. Onboarding d'un intégrateur (matériel, pas identité)

Provisionner un nouvel appareil Edge (le seul onboarding qui existe
réellement aujourd'hui — l'identité de connexion d'un intégrateur externe
reste DEFERRED, section 2) :

1. `POST /devices` (rôle de gestion) crée l'identité machine et renvoie un
   secret à usage unique, jamais revu en clair ensuite (`app/devices.py`).
2. Modèle cible : l'appareil génère sa propre paire de clés
   (`scripts/generate_device_key.py`), seule la clé publique est envoyée au
   serveur (`PUT /devices/{id}/public-key`) — la clé privée ne quitte jamais
   l'appareil.
3. Le démon du protocole concerné (étape 3 de la section 2 si c'en est un
   nouveau) s'authentifie (`POST /devices/auth`), lit sa configuration
   active, relève — voir `infra/README.md` pour l'exécution locale, et
   `scripts/<protocole>_daemon.py --help` pour les options.
4. La console web (`/edge`) montre l'appareil dès sa première
   authentification : statut de communication, version de l'agent, mesures
   en tampon (V4) — jamais besoin d'accès direct à la base pour vérifier
   qu'un nouvel appareil fonctionne.
