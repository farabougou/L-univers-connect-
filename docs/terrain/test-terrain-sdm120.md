# Guide de test terrain : compteur Eastron SDM120

Document de travail rédigé le 21/10/2026 pour Mohamed, mis à jour le même jour (consolidation
V5 : procédure exécutable hors ligne, vérificateur automatique). Il décrit, pas à pas,
comment relever un vrai compteur Eastron SDM120 avec la plateforme, et comment décider
honnêtement si le test est réussi.

Ce guide ne change aucun statut de validation. Seul un résultat obtenu sur le vrai
matériel, consigné dans la fiche de la section 12, peut faire passer le connecteur
Modbus/SDM120 à `FIELD_TESTED` (voir `docs/adr/017-*.md`). **Tant qu'aucun essai matériel
réel n'a eu lieu, ce statut reste `BLOCKED_EXTERNAL`.**

## 1. À quoi sert ce test, et ce qu'il prouve ou non

Jusqu'ici, toute la chaîne (compteur → Edge → API → console) a été vérifiée avec un
simulateur (`SIMULATOR_TESTED`) et des tests automatiques. Un simulateur répond
toujours exactement comme nous l'avons écrit. Un vrai compteur peut répondre autrement :
autre adresse, autre vitesse, valeurs en retard, coupures du réseau. Ce test sert à le
découvrir sur un cas réel et petit, avant d'engager un site client.

### 1.1 Ce que le pilote validera, s'il réussit

Un SDM120 réel, relié par une passerelle réseau à un ordinateur portable qui exécute le
démon Edge et la pile locale, pendant un essai d'environ 45 minutes :

- les 5 grandeurs (tension, courant, puissance, fréquence, énergie) sont lues sans erreur
  et concordent avec l'afficheur du compteur (T1 à T4) ;
- les unités sont cohérentes de bout en bout : registre du compteur, valeurs, unité des deux
  points de la plateforme (puissance en W, énergie en kW.h) ;
- la plateforme enregistre une mesure par intervalle, sans mesure manquante ni double
  mesure, sans indicateur de qualité inattendu (T5, T6) ;
- l'énergie ne recule jamais et correspond à la puissance multipliée par la durée (T7) ;
- une coupure de l'API ne fait perdre aucune mesure : elles sont mises en tampon et renvoyées
  (T8) ;
- une coupure de la passerelle n'invente aucune valeur et la relève reprend d'elle-même (T9) ;
- l'arrêt puis le redémarrage du démon reprennent sans doublon et sans retour en arrière de
  l'énergie.

### 1.2 Ce qu'il ne validera pas (à tester séparément)

| Hors périmètre | Pourquoi / comment le tester |
| --- | --- |
| Tenue sur 30 jours, fuites de ressources | L'essai dure moins d'une heure. Prévoir un essai de longue durée distinct. |
| Plusieurs compteurs, adresses Modbus autres que 1 | Le démon interroge l'adresse 1 uniquement (section 5). |
| Un autre modèle de compteur ou un autre constructeur | La carte de registres est celle du SDM120. |
| Liaison série directe (sans passerelle) | Non implémentée : décision séparée. |
| Tension, courant et fréquence **dans la plateforme** | Le vocabulaire ne les connaît pas encore : ils sont contrôlés par la lecture directe seulement. |
| Affichage « donnée périmée » dans la console pendant la coupure de la passerelle | À regarder à l'écran (étape 7.2) ; le vérificateur ne lit pas l'interface. |
| Redémarrage du démon **pendant** une coupure de l'API | Sans configuration connue, le démon ne peut rien lire avant le retour de l'API (section 5, limite 8). |
| Sécurité du réseau du site (Modbus TCP n'est ni chiffré ni authentifié) | Audit réseau distinct. |
| Matériel Edge définitif (PC industriel, alimentation de secours, coupures de courant) | L'essai utilise un ordinateur portable. |
| Comportement sur Railway / hébergement | L'essai utilise la pile locale, volontairement. |

Ne l'écrivez jamais comme « validé terrain » au-delà du périmètre 1.1.

## 2. Sécurité : à lire avant de toucher au matériel

- Le produit est en lecture seule (niveau C0). Le compteur est un capteur de mesure :
  la plateforme ne lui envoie aucune commande. Le code de lecture
  (`app/connectors/modbus.py`) ne contient aucune fonction d'écriture. Le test ne doit
  jamais tenter de modifier un réglage du compteur par Modbus.
- Le raccordement électrique du compteur est fait hors tension, par une personne
  habilitée, avec une protection (disjoncteur ou fusibles) en amont. Respectez la notice
  du compteur pour le calibre (courant maximal) et le câblage.
- Le Modbus TCP n'est ni chiffré ni authentifié. Branchez la passerelle sur un petit
  réseau isolé (le PC de test et la passerelle, rien d'autre), jamais sur un réseau
  partagé avec des tiers.
- Ne copiez jamais de clé ou de mot de passe dans le dépôt. La clé privée de l'appareil
  Edge reste dans votre dossier personnel, hors du dépôt.

## 3. Matériel nécessaire

| Élément | Remarque |
| --- | --- |
| Compteur Eastron SDM120 version Modbus (RS-485) | Monophasé. La version à impulsions seules ne convient pas. |
| Passerelle RS-485 vers Ethernet, en mode Modbus RTU vers Modbus TCP | Obligatoire avec le logiciel actuel (voir section 5). Un simple adaptateur USB-RS485 ne suffit pas. |
| Alimentation de la passerelle | Selon sa notice. |
| Câble de liaison RS-485 (paire torsadée, A et B) vers le compteur | À raccorder hors tension. |
| Charge de test connue | Idéalement résistive (radiateur, bouilloire) d'au moins 500 W, dont vous connaissez la puissance indiquée sur la plaque. Il faut au moins 0,1 kW.h consommés pendant l'essai pour comparer l'énergie à la puissance (12 minutes à 500 W). |
| Ordinateur portable | Il fait tourner l'API locale, la base et le démon Edge. |
| Câble réseau (et routeur ou commutateur de test si besoin) | Réseau isolé. |
| Appareil photo ou téléphone | Pour photographier l'afficheur du compteur (preuve du test). |
| Une montre ou l'horloge de l'ordinateur | Pour noter l'heure de chaque coupure (section 8.2). |

À vérifier sur la notice de votre exemplaire, et à noter dans la fiche de résultats : adresse
Modbus du compteur, vitesse (baud), parité et bits d'arrêt. Ne vous fiez pas à la mémoire
des valeurs d'usine : lisez-les dans le menu du compteur.

## 4. Schéma de la chaîne

```
Compteur SDM120 --RS-485--> Passerelle --Ethernet--> Ordinateur portable
                            (Modbus TCP)              |- démon Edge (scripts/modbus_daemon.py)
                                                      |- API locale (localhost:8000)
                                                      |- base PostgreSQL (docker, localhost:5432)
                                                      |- Keycloak (docker, localhost:8080)
                                                      |- vérificateur (scripts/sdm120_verify.py)
```

Le démon lit le compteur par la passerelle, puis envoie les mesures à l'API par HTTP avec
l'identité de l'appareil Edge. Si l'API est injoignable, il garde les mesures dans un
fichier tampon et les renvoie ensuite. La console web (`localhost:3000`) est facultative
pour cet essai, sauf pour l'affichage « donnée périmée » (étape 7.2).

## 5. Limites connues du logiciel (à connaître avant d'arriver sur place)

Ces limites sont réelles et vérifiées dans le code le 21/10/2026. Elles ne bloquent pas le
test, mais elles en fixent le périmètre.

1. **Modbus TCP seulement.** Le connecteur n'ouvre pas de port série. Il faut une
   passerelle RS-485 vers Ethernet. Lire un compteur directement par adaptateur USB
   demanderait un nouveau connecteur série (à décider séparément, non fait).
2. **Une seule adresse de compteur : 1.** Le démon interroge toujours l'adresse Modbus 1.
   Votre compteur doit être réglé sur l'adresse 1, et il doit être le seul sur la
   passerelle.
3. **Seuls 2 des 5 registres peuvent devenir des points validés aujourd'hui.** Le
   vocabulaire de la plateforme (`app/point_vocabulary.py`) connaît la puissance
   (`electric_power_sensor`, unité `W`) et l'énergie (`energy_meter_reading`, unité
   `kW.h`). Il ne connaît pas encore la tension, le courant ni la fréquence. Le test
   enregistre donc `active_power` et `total_active_energy` dans la plateforme ; la
   tension, le courant et la fréquence sont contrôlés par la lecture directe (étape 2).
   Ajouter ces trois grandeurs demande une décision séparée (vocabulaire, glossaire,
   textes, tests).
4. **Le script de relève manuelle `modbus_poll.py` ne s'authentifie qu'avec un secret
   partagé** (mode ancien, déconseillé). Avec une clé d'appareil (modèle cible), utilisez
   directement le démon : il fait le même chemin et affiche le résultat du premier tour.
5. **Il n'y a pas d'écran de création de points Modbus.** Les points se créent par l'API
   (commandes `curl` ci-dessous), puis la connexion Modbus se configure dans la console.
6. **L'API n'est pas déployée sur Railway.** Le test se fait avec la pile locale, ce qui
   est volontaire : rien n'est déployé sans votre accord.
7. **Les scripts se lancent avec `PYTHONPATH=.`** depuis `services/api` (sinon Python
   répond `No module named 'app'`). Sous Windows PowerShell : `$env:PYTHONPATH="."` puis la
   commande sans le préfixe.
8. **Démarrage du démon pendant une coupure de l'API.** Le démon relit sa configuration
   auprès de l'API à chaque tour. Il garde la dernière reçue pour continuer à relever (et
   mettre en tampon) quand l'API tombe. S'il est lancé alors que l'API est déjà coupée, il
   n'a aucune configuration connue : il attend le retour de l'API et ne relève rien d'ici
   là (il ne plante plus et n'invente rien). Une copie de la configuration sur disque
   résoudrait ce cas : **DEFER**, à décider avant un déploiement sur un site sans
   alimentation de secours.
9. **L'unité est contrôlée à trois endroits (depuis le 21/10/2026, ADR 020).** À la création de
   la connexion Modbus, l'unité du registre est comparée à celle du point : un registre en watts
   ne peut pas alimenter un point en `kW` (erreur `MODBUS_UNIT_CONVERSION_REQUIRED`, avec le
   facteur). À l'envoi, le démon déclare l'unité de chaque mesure et l'API refuse tout désaccord
   (`MEASUREMENT_UNIT_CONVERSION_REQUIRED`), **sans jamais convertir** : la conversion est un acte
   volontaire (point dans l'unité du registre, ou conversion à la source). Le démon journalise
   chaque refus en erreur. Enfin le vérificateur contrôle l'unité des deux points. Limite : un
   émetteur qui ne déclare pas son unité (BACnet, OPC UA, MQTT aujourd'hui) n'est pas contrôlé ; seul
   le drapeau `out_of_range` signale alors après coup une valeur hors plage.
10. **Les démons BACnet, OPC UA et MQTT avaient le même défaut que le démon Modbus avant
    correction** (configuration demandée à l'API à chaque tour, sans mémoire : une coupure de
    l'API arrêtait la relève). Corrigés le 21/10/2026 (V5.1), avec les mêmes garanties et les
    mêmes scénarios de test que Modbus, contre des simulateurs réels. Aucun n'a été essayé sur un
    équipement réel : ce guide ne concerne que le SDM120 en Modbus.

## 6. Préparation hors ligne (à faire AVANT, avec Internet)

L'essai doit pouvoir se dérouler sans Internet. Tout ce qui se télécharge se prépare à la
maison :

1. Dépôt à jour : `git pull`, puis dans `services/api` un environnement Python avec les
   dépendances installées (`pip install -r requirements.txt -r requirements-dev.txt`, comme la
   CI). Vérifiez : `PYTHONPATH=. python -c "import app.main"`.
2. Images Docker téléchargées : `cd infra && docker compose pull db keycloak`. Les images
   de Keycloak, MinIO et Mosquitto sont étiquetées `latest` : **ne faites pas de
   `docker compose pull` sur le site**, vous obtiendriez peut-être une version différente de
   celle de votre répétition. Seuls `db` et `keycloak` servent à ce pilote.
3. Base prête : `docker compose up -d db keycloak`, puis dans `services/api` :
   `alembic upgrade head`.
4. **Essai en mode avion** : coupez le Wi-Fi et le réseau, relancez les étapes 3 à 5 ci-dessous
   avec le simulateur. Si une étape échoue sans réseau, c'est qu'elle dépend d'Internet :
   notez laquelle et corrigez-la ici, pas sur le site. (Cet essai en mode avion n'a pas pu
   être fait dans l'environnement de rédaction : à faire une fois chez vous.)
5. Imprimez ou copiez ce guide, et la fiche de la section 12, sur le portable.
6. Fuseau horaire : toutes les heures de ce guide sont en UTC (`...Z`). Bamako est à UTC+0
   toute l'année : l'heure locale et l'heure UTC sont les mêmes.

## 7. Étape 0 : répétition à blanc avec le simulateur

Faites tout le guide une première fois avec le simulateur, chez vous, avant d'aller sur
place. Ce n'est pas un test terrain (statut `SIMULATOR_TESTED`) : cela sert à repérer ici
une erreur de saisie plutôt que devant le compteur.

1. Démarrer la pile locale (voir `infra/README.md`) :

   ```bash
   cd infra
   docker compose up -d db keycloak
   cd ../services/api
   alembic upgrade head
   uvicorn app.main:app --no-access-log
   ```

2. Démarrer le simulateur dans un autre terminal :

   ```bash
   cd services/api
   PYTHONPATH=. python scripts/modbus_simulator.py 5020
   ```

   Il affiche les valeurs fictives : 231,4 V, 2,37 A, 548 W, 50 Hz, 1284,6 kWh. **Ces valeurs
   ne changent jamais** : l'énergie reste figée.

3. Déroulez les étapes 1 à 8 en remplaçant l'adresse de la passerelle par `127.0.0.1` et
   le port par `5020`.

Résultat attendu de la répétition : toutes les vérifications passent, **sauf une** :
`T7 — Énergie cohérente avec la puissance multipliée par la durée`. Elle est « non évaluée »
si l'essai dure moins de 12 minutes (énergie attendue sous 0,1 kW.h), et « échec » avec la
raison « compteur ou simulateur figé » au-delà. C'est normal et utile : le vérificateur
sait détecter une énergie qui ne bouge pas. Le verdict global ne peut donc pas être « Réussi »
avec le simulateur ; il le peut sur le vrai compteur.

### Ce que la répétition réelle du 21/10/2026 a montré

Chaîne complète en processus séparés (API, simulateur, démon, base), intervalle de 3 s,
trois coupures provoquées (API 27 s, passerelle 21 s, démon 7 s), puis le vérificateur :

| Démon | Coupure de l'API (T8) | Passerelle (T9) | Redémarrage du démon | Verdict |
| --- | --- | --- | --- | --- |
| **Avant correction** | **18 mesures perdues**, 0 renvoyée | réussi | réussi | **Échec** |
| **Corrigé** (2 passages) | 0 perdue, 9 renvoyées par le tampon | réussi | réussi | « Incomplet » (énergie trop faible pour conclure) |

La correction : le démon ne relevait plus rien pendant une coupure de l'API, car il demandait
sa configuration à l'API avant chaque lecture (voir `scripts/modbus_daemon.py`, tests dans
`tests/test_modbus_daemon.py`). Ces chiffres viennent du simulateur : ils ne valent pas
validation terrain.

## 8. Procédure sur le matériel

### Étape 1 : câbler et régler le réseau

1. Hors tension, raccordez le compteur et la liaison RS-485 vers la passerelle. Faites
   vérifier le câblage par la personne habilitée avant de remettre sous tension.
2. Réglez la passerelle (selon sa notice) : mode Modbus RTU vers Modbus TCP, port TCP 502,
   et les mêmes paramètres série que le compteur (vitesse, parité, bits d'arrêt).
3. Donnez des adresses fixes sur un même réseau. Exemple (adresses d'exemple à adapter) :
   passerelle `192.168.1.200`, ordinateur `192.168.1.10`, masque `255.255.255.0`.
4. Vérifiez que l'ordinateur voit la passerelle : `ping 192.168.1.200`.
5. Réglez le compteur sur l'adresse Modbus 1 (menu du compteur, voir la notice).
6. Remettez sous tension et branchez la charge de test (puissance stable).

### Étape 2 : lecture directe du compteur, sans la plateforme

C'est la vérification la plus précieuse : elle isole le compteur et la passerelle de tout
le reste. Depuis `services/api`, avec la charge branchée et **l'afficheur du compteur sous les
yeux** (relevez ses valeurs pendant les trois lectures) :

```bash
PYTHONPATH=. python scripts/sdm120_preflight.py --host 192.168.1.200 \
  --resistive-load \
  --display voltage=231,2 --display current=2,38 --display active_power=549 \
  --display frequency=50 \
  --json-out ~/sdm120-lecture-directe.json
```

Remplacez les valeurs par celles de **votre** afficheur. Retirez `--resistive-load` si la
charge n'est pas résistive (le contrôle T4 devient « non évalué »). Ajoutez
`--nominal-voltage 220` si la tension nominale locale est 220 V.

Ce que le script fait : trois lectures (code de fonction Modbus 04, lecture seule), puis les
contrôles T1 à T4 : lectures complètes, valeurs plausibles, **unité de la puissance
cohérente avec tension × courant** (détecte un W lu comme un kW), concordance avec ce que
vous avez saisi de l'afficheur, puissance égale à tension × courant sous charge résistive.
Il écrit une preuve (`--json-out`) que le vérificateur final reprend.

Code de sortie : 0 aucun échec, 1 au moins un échec, 2 compteur injoignable. Photographiez
l'afficheur. Si la commande échoue, passez à la section 10 (dépannage) avant d'aller plus loin.

### Étape 3 : préparer la plateforme

**3.1 Jeton d'accès (valable quelques minutes, à redemander si une commande répond 401).**
Avec les identifiants de développement local (`infra/README.md`) :

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/realms/paios/protocol/openid-connect/token \
  -d "client_id=paios-api" -d "grant_type=password" \
  -d "username=demo.admin" -d "password=demo-dev-only" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s http://localhost:8000/me -H "Authorization: Bearer $TOKEN"
```

Notez `tenant_id` dans la réponse : c'est l'identifiant à donner au démon et au vérificateur
(`<TENANT_ID>`).

**3.2 Site et équipement (console web, écran Registre).** Créez un site (fuseau
`Africa/Bamako`) puis un équipement de test (par exemple « Compteur SDM120 test »).
Ouvrez la fiche de l'équipement et notez son identifiant (dans l'adresse de la page) :
c'est `<ID_EQUIPEMENT>`.

**3.3 Les deux points.** Remplacez `<ID_EQUIPEMENT>`. **Vérifiez l'unité avant de
valider : un point validé ne se modifie plus.** La puissance est en `W` (pas `kW`), l'énergie
en `kW.h` :

```bash
curl -s -X POST http://localhost:8000/points \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"code":"sdm120-test.puissance","name":"Puissance active","value_type":"number",
       "point_class":"electric_power_sensor","unit":"W",
       "functional_location_id":"<ID_EQUIPEMENT>","expected_interval_seconds":60}'

curl -s -X POST http://localhost:8000/points \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"code":"sdm120-test.energie","name":"Énergie active totale","value_type":"number",
       "point_class":"energy_meter_reading","unit":"kW.h",
       "functional_location_id":"<ID_EQUIPEMENT>","expected_interval_seconds":60}'
```

Si vous créez par erreur le point de puissance en `kW`, la connexion de l'étape 3.5 sera refusée
(registre en watts, point en kilowatts) : créez un nouveau point en `W`, un point validé ne se
modifie plus.

Chaque réponse contient un `id` : notez-les (`<ID_POINT_PUISSANCE>`, `<ID_POINT_ENERGIE>`).
Puis validez-les (mise en service) :

```bash
curl -s -X POST http://localhost:8000/points/<ID_POINT_PUISSANCE>/validate \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"reason":"Test terrain SDM120"}'
```

(même commande avec `<ID_POINT_ENERGIE>`). Un point non validé reçoit les mesures avec
l'indicateur de qualité `unvalidated_point` : ne sautez pas cette étape.

**3.4 Identité de l'appareil Edge.** La clé privée reste hors du dépôt :

```bash
cd services/api
PYTHONPATH=. python scripts/generate_device_key.py --out ~/cle-sdm120-test.pem
openssl pkey -in ~/cle-sdm120-test.pem -pubout -out ~/cle-sdm120-test.pub.pem
python3 - <<'EOF' > ~/appareil-sdm120-test.json
import json, pathlib
print(json.dumps({
    "device_id": "sdm120-test-01",
    "public_key_pem": (pathlib.Path.home() / "cle-sdm120-test.pub.pem").read_text(),
}))
EOF
curl -s -X POST http://localhost:8000/devices \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d @$HOME/appareil-sdm120-test.json
```

La réponse confirme l'enregistrement. Seule la clé publique a quitté votre ordinateur.

**3.5 Connexion Modbus (console web).** Sur la fiche de l'équipement, section
« Connexion Modbus » : adresse de la passerelle (`192.168.1.200`), port `502`, associez
`active_power` au point de puissance et `total_active_energy` au point d'énergie, saisissez
un motif, puis enregistrez. La version est créée en brouillon : cliquez sur « Activer ».

### Étape 4 : lancer le démon Edge

Notez l'heure de début : `date -u +%Y-%m-%dT%H:%M:%SZ` (c'est `<DEBUT>`).

```bash
cd services/api
PYTHONPATH=. python scripts/modbus_daemon.py \
  --api-url http://localhost:8000 \
  --tenant <TENANT_ID> \
  --device-id sdm120-test-01 \
  --private-key-file ~/cle-sdm120-test.pem \
  --equipment <ID_EQUIPEMENT> \
  --interval 60 \
  --buffer ~/tampon-sdm120-test.jsonl
```

Ce que vous devez voir dans le premier tour : une ligne « relève effectuée » avec
`'inserted': 2`, `'rejected': 0`. Laissez tourner. Arrêt propre : Ctrl+C.

### Étape 5 : vérifier à l'écran

- Console, écran Edge (`/edge`) : l'appareil `sdm120-test-01` est en ligne, le tampon en
  attente est à 0.
- Console, écran Télémétrie (`/telemetrie`) : les deux points affichent leur dernière valeur.
- Valeurs brutes d'un point :

  ```bash
  curl -s "http://localhost:8000/measurements?point_id=<ID_POINT_PUISSANCE>&limit=20" \
    -H "Authorization: Bearer $TOKEN"
  ```

  Vérifiez que `origin` vaut `measured`, que `source` commence par `edge:` et que
  `quality_flags` est vide.

### Étape 6 : comparer à l'afficheur

À trois moments pendant la durée de la relève (début, milieu, fin), photographiez
l'afficheur du compteur et notez dans la fiche la valeur affichée, l'heure, et la dernière
valeur reçue par la plateforme. Une puissance qui varie entre la photo et la dernière
relève provoque un petit écart naturel : comparez de préférence sous charge stable.

### Étape 7 : épreuves de panne (environ 25 minutes)

**Règle d'or : notez l'heure exacte du début et de la fin de chaque coupure**, avec
`date -u +%Y-%m-%dT%H:%M:%SZ` dans un second terminal, ou sur papier avec l'horloge de
l'ordinateur (en UTC). Le vérificateur tolère un intervalle (60 s) d'imprécision à chaque borne,
pas davantage. Laissez le démon tourner **10 minutes avant la première coupure** (référence
sans panne), et **5 minutes entre deux coupures** (retour à la normale).

**7.1 Coupure de l'API (5 minutes).** Notez `<API_DEBUT>`, arrêtez `uvicorn` (Ctrl+C) 5
minutes, relancez-le, notez `<API_FIN>` dès que `curl localhost:8000/health` répond. Le démon
doit continuer, relever le compteur, mettre les mesures en tampon (le journal le dit : « mise(s)
en tampon local »), puis les renvoyer au retour de l'API. Aucune relève ne doit manquer.

**7.2 Coupure de la passerelle (5 minutes).** Notez `<GW_DEBUT>`, débranchez l'alimentation
de la passerelle 5 minutes, rebranchez-la, notez `<GW_FIN>`. Le démon doit journaliser
« lecture impossible » sans s'arrêter ; aucune valeur ne doit être enregistrée pendant la
coupure. **À l'écran** (console, écran Télémétrie ou Edge) : au bout de 3 intervalles (3 minutes)
la donnée doit être signalée **périmée** avec sa dernière valeur et sa date, puis rétablie au
retour des relevés. Notez-le dans la fiche : le vérificateur ne peut pas le voir.

**7.3 Arrêt et reprise du démon (2 minutes).** Notez `<DEMON_DEBUT>`, arrêtez le démon
(Ctrl+C), attendez 2 minutes, relancez-le, notez `<DEMON_FIN>`. Il reprend sans intervention,
sans doublon.

Laissez ensuite le démon tourner encore 5 minutes, puis notez `<FIN>` et arrêtez-le (Ctrl+C).
Durée totale : environ 45 minutes.

### Étape 8 : vérification automatique

Depuis `services/api`, avec la pile locale encore démarrée (la base suffit, l'API n'est plus
nécessaire) :

```bash
PYTHONPATH=. python scripts/sdm120_verify.py \
  --tenant <TENANT_ID> \
  --power-point <ID_POINT_PUISSANCE> --energy-point <ID_POINT_ENERGIE> \
  --start <DEBUT> --end <FIN> --interval 60 \
  --outage api=<API_DEBUT>,<API_FIN> \
  --outage gateway=<GW_DEBUT>,<GW_FIN> \
  --outage daemon=<DEMON_DEBUT>,<DEMON_FIN> \
  --direct-json ~/sdm120-lecture-directe.json \
  --json-out ~/sdm120-rapport.json
```

Les heures s'écrivent avec fuseau (`2026-10-21T09:10:00Z`) : une heure sans fuseau est
refusée. Le script lit la base locale (lecture seule, sous la sécurité par client) : il ne
demande ni jeton ni Internet. Si la base n'est pas sur `localhost`, définissez
`DATABASE_URL`.

Il affiche un constat par contrôle, la liste des **trous** trouvés dans les mesures (à
rapprocher de vos notes), et un verdict :

| Verdict | Code de sortie | Sens |
| --- | --- | --- |
| Réussi | 0 | Tous les contrôles requis sont évalués et réussis. |
| Échec | 1 | Au moins un contrôle échoue : lisez-le, il dit quoi et combien. |
| Incomplet | 3 | Aucun échec, mais un contrôle requis n'a pas pu être évalué (épreuve non faite, énergie trop faible, afficheur non saisi). **Ce n'est pas un succès.** |
| (erreur) | 2 | Point introuvable pour ce client. |

Le rapport JSON (`--json-out`) ne contient que des codes et des nombres. Joignez-le à la fiche.

## 9. Critères de réussite

Ces seuils sont une proposition de ma part, à relire et à ajuster par Mohamed avant le
test. Fixez-les avant de mesurer, jamais après avoir vu les résultats. Ils sont codés dans
`app/sdm120_check.py` (constantes en tête de fichier).

| N° | Vérification | Seuil proposé | Qui l'évalue |
| --- | --- | --- | --- |
| T1 | Lecture directe (étape 2) | 3 essais sur 3 renvoient les 5 valeurs, sans erreur | `sdm120_preflight.py` |
| T2 | Plausibilité et unités | Tension à ±10 % de la nominale, fréquence 50 Hz ±1 Hz, puissance active ≤ tension × courant × 1,05 (sinon unité suspecte) | `sdm120_preflight.py` |
| T3 | Concordance avec l'afficheur | Écart de 1 % au plus (ou le pas d'affichage) pour les grandeurs saisies | Vous saisissez, le script compare |
| T4 | Cohérence interne sous charge résistive | Puissance active égale à tension × courant à 5 % près | `sdm120_preflight.py` |
| T5 | Enregistrement | 0 mesure manquante hors coupure déclarée, 0 double mesure, intervalle médian à ±20 % de celui configuré | `sdm120_verify.py` |
| T6 | Qualité des données | Champ `quality_flags` vide (seule `late_arrival` est admise, pour une mesure rejouée après coupure de l'API) | `sdm120_verify.py` |
| T7 | Énergie et unités des points | Jamais décroissante ; augmentation = puissance × durée à 10 % près (au moins 0,1 kW.h) ; point de puissance en W, d'énergie en kW.h ; un facteur proche de 1000 est signalé comme confusion d'unité | `sdm120_verify.py` |
| T8 | Coupure de l'API | 0 mesure perdue, mesures rejouées | `sdm120_verify.py` |
| T9 | Coupure de la passerelle | Aucune valeur enregistrée pendant la coupure, reprise sous 2 intervalles | `sdm120_verify.py` ; affichage « périmé » : **vous** |
| T9b | Redémarrage du démon | Reprise sous 2 intervalles, sans doublon, énergie jamais en arrière | `sdm120_verify.py` |
| T10 | Lecture seule | Optionnel mais recommandé : avec Wireshark sur l'ordinateur (filtre `mbtcp`), tous les codes de fonction observés valent 4 | **Vous** |

Verdict : **PASS** seulement si T1 à T9b sont tous réussis (verdict « Réussi » du script **et**
vos propres constats : concordance de l'afficheur sur les photos, affichage « périmé »). Un
seul échec donne **FAIL** et une ligne dans la fiche qui dit pourquoi. Un critère non mesuré
est « non évalué », jamais « réussi ».

## 10. Dépannage

| Symptôme | Cause probable | Que faire |
| --- | --- | --- |
| `No module named 'app'` | Commande lancée sans `PYTHONPATH=.` | Ajouter `PYTHONPATH=.` et lancer depuis `services/api` |
| `Lecture impossible (…:502)` | Mauvaise adresse, câble, pare-feu, passerelle éteinte | `ping` de la passerelle ; vérifier le port 502 ; vérifier l'adresse IP de l'ordinateur |
| `Appareil en erreur pour « voltage »` | Mauvaise adresse Modbus du compteur ou paramètres série différents | Régler le compteur sur l'adresse 1 ; aligner vitesse, parité, bits d'arrêt avec la passerelle |
| Valeurs absurdes (très grandes ou nulles) | Mauvais ordre des octets ou mauvais registre | Ne pas corriger au hasard ; noter les valeurs brutes, comparer à la notice, me les transmettre |
| `Unité de la puissance cohérente` en échec | Puissance en kW ou en mW, ou tension/courant mal lus | Comparer avec l'afficheur ; ne pas corriger sans comprendre |
| `T7 — Unités des points` en échec | Point créé avec une autre unité que `W` / `kW.h` | Créer un nouveau point correct (un point validé ne se modifie pas), refaire l'essai |
| `T8` en échec avec « 0 renvoyée » | Le démon a été arrêté ou relancé pendant la coupure, ou n'a pas pu lire le compteur | Regarder le journal du démon ; noter, ne pas supposer |
| `401` de l'API | Jeton expiré | Redemander le jeton (étape 3.1) |
| Rejet `POINT_NOT_FOUND` | Mauvais `point_id` dans la connexion Modbus | Reprendre la configuration dans la console |
| `quality_flags` contient `unvalidated_point` | Point pas validé | Valider le point (étape 3.3) |
| `quality_flags` contient `clock_suspect` | Horloge de l'ordinateur décalée | Mettre l'ordinateur à l'heure (synchronisation réseau, avant d'être hors ligne) |
| « Aucune configuration Modbus active » au démarrage | Version laissée en brouillon | Cliquer sur « Activer » (étape 3.5) |
| `heure sans fuseau` | Heure saisie sans `Z` | Ajouter `Z` (UTC) |
| Lignes mises de côté dans `…jsonl.corrupt` | Le tampon a été coupé net (coupure de courant) | Normal : les lignes illisibles sont conservées, les autres sont renvoyées |

Règle : si un blocage persiste après deux tentatives, notez ce que vous avez essayé et
arrêtez-vous pour en discuter, plutôt que de modifier plusieurs réglages à la fois.

## 11. Après le test

1. Arrêtez le démon, coupez la charge, remettez le matériel dans l'état d'origine.
2. Supprimez ou archivez les données de test dans la plateforme locale si elles ne servent
   plus (la clé privée de test peut être supprimée de votre dossier personnel).
3. Remplissez la fiche ci-dessous, avec les photos de l'afficheur et le rapport JSON.
4. Mettez à jour `docs/spec/feature-benchmark-matrix.md` : le statut du connecteur
   Modbus/SDM120 passe à `FIELD_TESTED` uniquement si le verdict est PASS, avec la date
   et le périmètre exact de la section 1.1. En cas de FAIL, ajoutez les défauts trouvés
   comme travaux à planifier.
5. Ne décidez pas seul(e) d'étendre le périmètre : tension, courant, fréquence dans le
   vocabulaire, connecteur série direct, autres adresses Modbus, contrôle d'unité à l'activation,
   copie de configuration sur disque, correction des autres démons et de `modbus_poll.py` sont
   des étapes séparées, à ouvrir après ce test.

## 12. Fiche de résultats (à copier et remplir)

```
Date et heure de début / fin :
Lieu (sans nom de personne) :
Compteur : modèle, numéro de série, version du micrologiciel affichée :
Passerelle : modèle, réglages série (vitesse / parité / bits d'arrêt), adresse IP :
Charge de test : type, puissance indiquée sur la plaque :
Version du code (commit) :
Intervalle de relève (s) :
Heures notées (UTC) : API ___ → ___   Passerelle ___ → ___   Démon ___ → ___

T1  Lecture directe 3/3 :           PASS / FAIL / non évalué   Notes :
T2  Plausibilité et unités :        PASS / FAIL / non évalué   Notes :
T3  Concordance afficheur :         PASS / FAIL / non évalué
      V : afficheur ___ / plateforme ___     A : ___ / ___
      W : afficheur ___ / plateforme ___     Hz : ___ / ___
      kWh : afficheur ___ / plateforme ___
T4  Cohérence P = V x I :           PASS / FAIL / non évalué   Écart : ___ %
T5  Enregistrement :                PASS / FAIL / non évalué   Manquantes ___ Doubles ___
T6  Qualité des données :           PASS / FAIL / non évalué
T7  Énergie et unités des points :  PASS / FAIL / non évalué   Écart : ___ %
T8  Coupure de l'API :              PASS / FAIL / non évalué   Perdues : ___ Renvoyées : ___
T9  Coupure de la passerelle :      PASS / FAIL / non évalué
      Affichage « périmé » observé à l'écran après ___ min : oui / non
T9b Redémarrage du démon :          PASS / FAIL / non évalué
T10 Lecture seule (Wireshark) :     PASS / FAIL / non évalué / non fait

Verdict du script sdm120_verify.py : Réussi / Échec / Incomplet   (rapport joint)
Verdict : PASS / FAIL
Défauts observés (un par ligne, avec la preuve) :
Ce qui n'a PAS été vérifié :
Photos jointes (afficheur, câblage) :
```
