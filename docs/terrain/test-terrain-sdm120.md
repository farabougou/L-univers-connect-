# Guide de test terrain : compteur Eastron SDM120

Document de travail rédigé le 21/10/2026 pour Mohamed. Il décrit, pas à pas, comment
relever un vrai compteur Eastron SDM120 avec la plateforme, et comment décider
honnêtement si le test est réussi.

Ce guide ne change aucun statut de validation. Seul un résultat obtenu sur le vrai
matériel, consigné dans la fiche de la section 11, peut faire passer le connecteur
Modbus/SDM120 à `FIELD_TESTED` (voir `docs/adr/017-*.md`).

## 1. À quoi sert ce test, et ce qu'il ne prouve pas

Jusqu'ici, toute la chaîne (compteur → Edge → API → console) a été vérifiée avec un
simulateur (`SIMULATOR_TESTED`) et des tests automatiques. Un simulateur répond
toujours exactement comme nous l'avons écrit. Un vrai compteur peut répondre autrement :
autre adresse, autre vitesse, valeurs en retard, coupures du réseau. Ce test sert à le
découvrir sur un cas réel et petit, avant d'engager un site client.

Ce que ce test prouve s'il réussit : un SDM120 réel, relié par une passerelle réseau,
est relevé correctement et sans perte pendant une courte durée, et la plateforme
affiche les valeurs avec la bonne qualité.

Ce qu'il ne prouve pas : la tenue sur 30 jours, plusieurs compteurs, un autre modèle
de compteur, un autre site, ni la sécurité du réseau du site. Ne l'écrivez jamais
comme « validé terrain » au-delà de ce périmètre.

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
| Charge de test connue | Idéalement résistive (radiateur, bouilloire) dont vous connaissez la puissance indiquée sur la plaque. |
| Ordinateur portable | Il fait tourner l'API locale, la console et le démon Edge. |
| Câble réseau (et routeur ou commutateur de test si besoin) | Réseau isolé. |
| Appareil photo ou téléphone | Pour photographier l'afficheur du compteur (preuve du test). |

À vérifier sur la notice de votre exemplaire, et à noter dans la fiche de résultats : adresse
Modbus du compteur, vitesse (baud), parité et bits d'arrêt. Ne vous fiez pas à la mémoire
des valeurs d'usine : lisez-les dans le menu du compteur.

## 4. Schéma de la chaîne

```
Compteur SDM120 --RS-485--> Passerelle --Ethernet--> Ordinateur portable
                            (Modbus TCP)              |- démon Edge (scripts/modbus_daemon.py)
                                                      |- API locale (localhost:8000)
                                                      |- console web (localhost:3000)
```

Le démon lit le compteur par la passerelle, puis envoie les mesures à l'API par HTTP avec
l'identité de l'appareil Edge. Si l'API est injoignable, il garde les mesures dans un
fichier tampon et les renvoie ensuite.

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
   tension, le courant et la fréquence sont contrôlés par une lecture directe du compteur
   (étape 2), qui reste une vérification réelle du compteur. Ajouter ces trois grandeurs
   demande une décision séparée (vocabulaire, glossaire, textes, tests).
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

## 6. Étape 0 : répétition à blanc avec le simulateur

Faites tout le guide une première fois avec le simulateur, chez vous, avant d'aller sur
place. Ce n'est pas un test terrain (statut `SIMULATOR_TESTED`) : cela sert à repérer ici
une erreur de saisie plutôt que devant le compteur.

1. Démarrer la pile locale (voir `infra/README.md`) :

   ```bash
   cd infra
   docker compose up -d
   cd ../services/api
   alembic upgrade head
   uvicorn app.main:app --no-access-log
   ```

   Dans un autre terminal, la console : `cd apps/web && npm run dev` (voir `apps/web/README.md`).

2. Démarrer le simulateur dans un autre terminal :

   ```bash
   cd services/api
   PYTHONPATH=. python scripts/modbus_simulator.py 5020
   ```

   Il affiche les valeurs fictives : 231,4 V, 2,37 A, 548 W, 50 Hz, 1284,6 kWh.

3. Déroulez les étapes 2 à 7 ci-dessous en remplaçant l'adresse de la passerelle par
   `127.0.0.1` et le port par `5020`.

Résultat attendu de la répétition : toutes les vérifications passent, et vous savez où
cliquer. Notez ce qui vous a arrêté : c'est ce qu'il faut corriger dans ce guide.

## 7. Procédure sur le matériel

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
le reste. Depuis `services/api` :

```bash
PYTHONPATH=. python -c "
from app.connectors.sdm120 import SDM120_POINTS
from app.connectors.modbus import read_modbus_points
print(read_modbus_points('192.168.1.200', 502, SDM120_POINTS))
"
```

Ce que vous devez obtenir : un dictionnaire avec `voltage`, `current`, `active_power`,
`frequency`, `total_active_energy`. Relevez au même moment l'afficheur du compteur et
photographiez-le. Répétez trois fois à quelques secondes d'intervalle. Cette commande ne
fait que lire (code de fonction Modbus 04).

Si la commande échoue, passez à la section 9 (dépannage) avant d'aller plus loin.

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

Notez `tenant_id` dans la réponse : c'est l'identifiant à donner au démon (`<TENANT_ID>`).

**3.2 Site et équipement (console web, écran Registre).** Créez un site (fuseau
`Africa/Bamako`) puis un équipement de test (par exemple « Compteur SDM120 test »).
Ouvrez la fiche de l'équipement et notez son identifiant (dans l'adresse de la page) :
c'est `<ID_EQUIPEMENT>`.

**3.3 Les deux points.** Remplacez `<ID_EQUIPEMENT>` :

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

### Étape 7 : épreuves de panne (15 à 20 minutes)

1. **Coupure de l'API.** Arrêtez `uvicorn` (Ctrl+C) pendant 5 minutes, puis relancez-le. Le
   démon doit continuer, mettre les mesures en tampon (voir le journal), puis les renvoyer
   au retour de l'API. Aucune relève ne doit manquer dans l'historique.
2. **Coupure de la passerelle.** Débranchez l'alimentation de la passerelle 5 minutes, puis
   rebranchez-la. Le démon doit journaliser « lecture impossible » sans s'arrêter, la donnée
   doit être signalée périmée (comptez 3 intervalles, soit 3 minutes), puis rétablie au
   retour des relevés.
3. **Arrêt et reprise du démon.** Arrêtez le démon (Ctrl+C) 2 minutes, relancez-le : il
   reprend sans intervention.

## 8. Critères de réussite

Ces seuils sont une proposition de ma part, à relire et à ajuster par Mohamed avant le
test. Fixez-les avant de mesurer, jamais après avoir vu les résultats.

| N° | Vérification | Seuil proposé |
| --- | --- | --- |
| T1 | Lecture directe (étape 2) | 3 essais sur 3 renvoient les 5 valeurs, sans erreur |
| T2 | Plausibilité | Tension à ±10 % de la tension nominale du réseau local, fréquence à 50 Hz ±1 Hz |
| T3 | Concordance avec l'afficheur | Écart de 1 % au plus (ou 1 unité du dernier chiffre affiché) pour V, A, W, Hz ; kWh identique au pas d'affichage |
| T4 | Cohérence interne sous charge résistive | Puissance active égale à tension × courant à 5 % près |
| T5 | Enregistrement | Sur 30 minutes à 60 s, chaque tour insère 2 mesures : 0 relève manquante, 0 refus |
| T6 | Qualité des données | Champ `quality_flags` vide sur toutes les mesures (hors épreuves de panne) |
| T7 | Énergie | Jamais décroissante ; l'augmentation sur 30 minutes correspond à la puissance × durée à 10 % près |
| T8 | Coupure de l'API | 0 mesure perdue, tampon vidé au retour de l'API |
| T9 | Coupure de la passerelle | Le démon ne s'arrête pas ; donnée signalée périmée puis rétablie |
| T10 | Lecture seule | Optionnel mais recommandé : avec Wireshark sur l'ordinateur (filtre `mbtcp`), tous les codes de fonction observés valent 4 |

Verdict : **PASS** seulement si T1 à T9 sont tous réussis. Un seul échec donne **FAIL**
et une ligne dans la fiche qui dit pourquoi. Un critère non mesuré est « non évalué », jamais
« réussi ».

## 9. Dépannage

| Symptôme | Cause probable | Que faire |
| --- | --- | --- |
| `No module named 'app'` | Commande lancée sans `PYTHONPATH=.` | Ajouter `PYTHONPATH=.` et lancer depuis `services/api` |
| `Connexion impossible à ...:502` | Mauvaise adresse, câble, pare-feu, passerelle éteinte | `ping` de la passerelle ; vérifier le port 502 ; vérifier l'adresse IP de l'ordinateur |
| `Appareil en erreur pour « voltage »` | Mauvaise adresse Modbus du compteur ou paramètres série différents | Régler le compteur sur l'adresse 1 ; aligner vitesse, parité, bits d'arrêt avec la passerelle |
| Valeurs absurdes (très grandes ou nulles) | Mauvais ordre des octets ou mauvais registre | Ne pas corriger au hasard ; noter les valeurs brutes, comparer à la notice, me les transmettre |
| `401` de l'API | Jeton expiré | Redemander le jeton (étape 3.1) |
| Rejet `POINT_NOT_FOUND` | Mauvais `point_id` dans la connexion Modbus | Reprendre la configuration dans la console |
| `quality_flags` contient `unvalidated_point` | Point pas validé | Valider le point (étape 3.3) |
| `quality_flags` contient `clock_suspect` | Horloge de l'ordinateur décalée | Mettre l'ordinateur à l'heure (synchronisation réseau) |
| « Aucune configuration Modbus active » au démarrage | Version laissée en brouillon | Cliquer sur « Activer » (étape 3.5) |

Règle : si un blocage persiste après deux tentatives, notez ce que vous avez essayé et
arrêtez-vous pour en discuter, plutôt que de modifier plusieurs réglages à la fois.

## 10. Après le test

1. Arrêtez le démon, coupez la charge, remettez le matériel dans l'état d'origine.
2. Supprimez ou archivez les données de test dans la plateforme locale si elles ne servent
   plus (la clé privée de test peut être supprimée de votre dossier personnel).
3. Remplissez la fiche ci-dessous, avec les photos de l'afficheur.
4. Mettez à jour `docs/spec/feature-benchmark-matrix.md` : le statut du connecteur
   Modbus/SDM120 passe à `FIELD_TESTED` uniquement si le verdict est PASS, avec la date
   et le périmètre exact de la section 1. En cas de FAIL, ajoutez les défauts trouvés
   comme travaux à planifier.
5. Ne décidez pas seul(e) d'étendre le périmètre : tension, courant, fréquence dans le
   vocabulaire, connecteur série direct, autres adresses Modbus et correction de
   `modbus_poll.py` sont des étapes séparées, à ouvrir après ce test.

## 11. Fiche de résultats (à copier et remplir)

```
Date et heure de début / fin :
Lieu (sans nom de personne) :
Compteur : modèle, numéro de série, version du micrologiciel affichée :
Passerelle : modèle, réglages série (vitesse / parité / bits d'arrêt), adresse IP :
Charge de test : type, puissance indiquée sur la plaque :
Version du code (commit) :

T1  Lecture directe 3/3 :           PASS / FAIL / non évalué   Notes :
T2  Plausibilité :                  PASS / FAIL / non évalué   Notes :
T3  Concordance afficheur :         PASS / FAIL / non évalué
      V : afficheur ___ / plateforme ___     A : ___ / ___
      W : afficheur ___ / plateforme ___     Hz : ___ / ___
      kWh : afficheur ___ / plateforme ___
T4  Cohérence P = V x I :           PASS / FAIL / non évalué   Écart : ___ %
T5  Enregistrement 30 min :         PASS / FAIL / non évalué   Insérées ___ / attendues ___
T6  Qualité des données :           PASS / FAIL / non évalué
T7  Énergie :                       PASS / FAIL / non évalué   Écart : ___ %
T8  Coupure de l'API :              PASS / FAIL / non évalué   Perdues : ___
T9  Coupure de la passerelle :      PASS / FAIL / non évalué
T10 Lecture seule (Wireshark) :     PASS / FAIL / non évalué / non fait

Verdict : PASS / FAIL
Défauts observés (un par ligne, avec la preuve) :
Ce qui n'a PAS été vérifié :
Photos jointes (afficheur, câblage) :
```
