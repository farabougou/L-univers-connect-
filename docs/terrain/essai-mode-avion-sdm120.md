# Essai en mode avion : répétition du pilote SDM120 sans Internet

**Statut : NON VALIDÉ.** Cette procédure a été préparée le 21/10/2026, mais elle n'a **pas** été
exécutée : l'environnement de rédaction n'a ni Docker, ni console web, ni moyen de couper un
réseau. Elle ne sera considérée comme validée que lorsque vous l'aurez exécutée chez vous et
que la fiche de la section 7 aura été remplie et relue. Tant que ce n'est pas fait, le pilote
SDM120 garde le statut `SIMULATOR_TESTED` au mieux, et `FIELD_TESTED` reste `BLOCKED_EXTERNAL`.

## 1. Ce que cet essai doit prouver

Le guide principal (`test-terrain-sdm120.md`) se déroule chez le client, sans Internet. Cet essai
cherche donc **une seule chose** : une dépendance cachée à Internet, que vous découvririez
sinon devant le compteur. Il rejoue le guide avec le simulateur, réseau coupé.

Il ne prouve rien sur le compteur réel, la passerelle RS-485 ou le câblage.

## 2. Résultat attendu, en une phrase

Toutes les étapes se déroulent comme décrit ci-dessous, et le vérificateur se termine avec le
**verdict « Incomplet » (code de sortie 3)**, dont la seule ligne non évaluée est
`T7 — Énergie cohérente avec la puissance multipliée par la durée`. Ce n'est pas un défaut :
le simulateur renvoie toujours la même énergie, le vérificateur le sait, et un essai de moins de
12 minutes ne permet pas de conclure sur ce contrôle. Un verdict « Réussi » est impossible avec
le simulateur. Tout **échec** (code 1), sur un autre contrôle que T7, est à noter et à corriger.

## 3. Préparation, avec Internet (à faire d'abord)

Tout ce qui se télécharge se télécharge maintenant. Cochez chaque ligne.

1. Dépôt à jour et environnement Python prêt :

   ```bash
   git pull
   cd services/api
   pip install -r requirements.txt -r requirements-dev.txt
   PYTHONPATH=. python -c "import app.main" && echo "import OK"
   ```

   Attendu : `import OK`.

2. Dépendances de la console web, et construction :

   ```bash
   cd apps/web
   npm ci
   cd ../..
   ```

3. Images Docker présentes localement. Seuls `db` et `keycloak` servent ici :

   ```bash
   cd infra
   docker compose pull db keycloak
   docker image ls --format '{{.Repository}}:{{.Tag}}' | grep -E '^(postgres:16|quay.io/keycloak/keycloak:latest)$'
   cd ..
   ```

   Attendu : les **deux** lignes `postgres:16` et `quay.io/keycloak/keycloak:latest`. S'il en
   manque une, l'essai hors ligne échouera au démarrage : recommencez le `pull`.

4. Notez la version exacte de l'image Keycloak, pour que le jour du terrain soit identique :

   ```bash
   docker image inspect quay.io/keycloak/keycloak:latest --format '{{.Id}} {{.Created}}'
   ```

   Copiez la ligne dans la fiche (section 7). Ne refaites plus de `docker compose pull` après
   cette étape.

5. Horloge : vérifiez que l'heure de l'ordinateur est exacte **avant** de couper le réseau
   (le réseau n'étant plus là, elle ne se corrigera plus) : `date -u +%Y-%m-%dT%H:%M:%SZ`.

6. Imprimez ou copiez ce document et le guide principal sur le portable.

## 4. Couper le réseau, et prouver qu'il est coupé

1. Activez le mode avion, **et** débranchez le câble Ethernet s'il y en a un. Désactivez aussi
   le point d'accès mobile et tout VPN.
2. Prouvez-le. Ces trois commandes doivent **échouer** :

   ```bash
   curl -sS -m 5 https://example.com -o /dev/null; echo "code=$?"
   curl -sS -m 5 https://railway.com -o /dev/null; echo "code=$?"
   getent hosts example.com || echo "résolution impossible"
   ```

   Attendu : `code` différent de 0 (6 ou 28 en général) pour les deux premières, et
   `résolution impossible` pour la troisième. Si l'une réussit, **le réseau n'est pas coupé** :
   n'allez pas plus loin.
3. Prouvez que l'ordinateur parle encore à lui-même : `curl -sS -m 5 http://127.0.0.1:1 ; echo "code=$?"`
   doit répondre `code=7` (connexion refusée), pas un délai dépassé. Cela confirme que le
   « localhost » fonctionne.

À partir d'ici, ne rallumez le réseau qu'à la fin (section 6).

## 5. Déroulement

Chaque ligne donne la commande, ce que vous devez voir, et ce que signifie un écart. Utilisez
quatre terminaux. Les numéros renvoient aux étapes du guide principal.

**Réglages de la répétition (différents du jour du terrain, pour que tout tienne en 25 minutes) :**
intervalle de relève de **10 s** (`--interval 10`), points créés avec
`"expected_interval_seconds":10`, coupures de **60 s** chacune, 3 minutes de relève normale avant
la première coupure et 1 minute entre deux. Passerelle : `127.0.0.1`, port `5020`.

| N° | Terminal | Commande | Attendu | Si ce n'est pas le cas |
| --- | --- | --- | --- | --- |
| 1 | A | `cd infra && docker compose up -d --pull never db keycloak` | Les deux services passent à « Started ». **`--pull never` interdit tout téléchargement** : sans l'image locale, la commande échoue tout de suite. | Message « pull access denied » ou « not found » : une image manque (section 3, point 3). |
| 2 | A | `docker compose ps` (attendre 1 à 2 minutes) | `db` en `healthy`, `keycloak` en `running`. | Keycloak redémarre en boucle : `docker compose logs keycloak \| tail -50` et notez toute adresse externe citée. |
| 3 | B | `cd services/api && alembic upgrade head` | Se termine sans erreur. | |
| 4 | B | `uvicorn app.main:app --no-access-log` | « Application startup complete ». | |
| 5 | C | `cd apps/web && npm run dev` | La console répond sur `http://localhost:3000`. | Erreur de police ou de ressource externe : notez-la, c'est précisément ce que cet essai cherche. |
| 6 | D | `curl -s http://localhost:8000/health` | Réponse `ok`. | |
| 7 | D | `cd services/api && PYTHONPATH=. python scripts/modbus_simulator.py 5020` | Affiche 231,4 V, 2,37 A, 548 W, 50 Hz, 1284,6 kWh. **Laisser tourner.** | |
| 8 | A | **3.1 Jeton** (guide) | `/me` répond, avec un `tenant_id`. Notez-le : `<TENANT_ID>`. | 401 : Keycloak n'est pas prêt ou le royaume `paios` est absent. |
| 9 | Navigateur | **3.2 Site et équipement** dans la console | Connexion réussie sur la console, site et équipement créés. Notez `<ID_EQUIPEMENT>`. | Page blanche ou chargement sans fin : ouvrez la console du navigateur et notez les requêtes en erreur. |
| 10 | A | **3.3 Les deux points**, avec `"expected_interval_seconds":10` | Deux `id`, puis les deux validations répondent. Unités : `W` et `kW.h`. | `MEASUREMENT_UNIT_*` ou `UNIT_UNKNOWN` : l'unité saisie est fausse (section 5 du guide, limite 9). |
| 11 | A | **3.4 Identité de l'appareil Edge** | `generate_device_key.py` crée la clé, `POST /devices` confirme. | |
| 12 | Navigateur | **3.5 Connexion Modbus** : passerelle `127.0.0.1`, port `5020`, `active_power` et `total_active_energy`, puis « Activer » | Version créée en brouillon puis activée. | `MODBUS_UNIT_CONVERSION_REQUIRED` : un point est en `kW` au lieu de `W` ; créez-en un nouveau. |
| 13 | Autre | `date -u +%Y-%m-%dT%H:%M:%SZ` | C'est `<DEBUT>`. | |
| 14 | D | **Étape 4**, démon avec `--interval 10` | Premier tour : `relève effectuée`, `'inserted': 2`, `'rejected': 0`. | `rejected` supérieur à 0 : lisez le motif dans le journal. |
| 15 | | Attendre **3 minutes** | Un tour toutes les 10 s, aucune erreur. | |
| 16 | Navigateur | **Étape 5**, écrans `/edge` et `/telemetrie` | Appareil en ligne, tampon à 0, deux points avec leur dernière valeur. | |
| 17 | Autre | **7.1 Coupure de l'API de 60 s** : noter `<API_DEBUT>`, Ctrl+C sur `uvicorn`, attendre 60 s, relancer `uvicorn`, noter `<API_FIN>` dès que `/health` répond | Le démon continue et journalise « mise(s) en tampon local ». Au retour de l'API, le journal indique le renvoi. | Le démon s'arrête ou ne relève plus : c'est le défaut corrigé le 21/10/2026, à signaler. |
| 18 | | Attendre **1 minute** | Retour à la normale. | |
| 19 | D (simulateur) | **7.2 Coupure de la passerelle de 60 s** : noter `<GW_DEBUT>`, Ctrl+C sur le simulateur, attendre 60 s, le relancer (étape 7), noter `<GW_FIN>` | Le démon journalise « lecture impossible » sans s'arrêter. Environ 30 s après le début, la donnée est signalée périmée à l'écran avec sa dernière valeur et sa date ; elle est rétablie au retour des relevés. | Aucune alerte de péremption : notez-le, le vérificateur ne peut pas le voir. |
| 20 | | Attendre **1 minute** | | |
| 21 | | **7.3 Arrêt du démon de 60 s** : noter `<DEMON_DEBUT>`, Ctrl+C, attendre 60 s, relancer la même commande, noter `<DEMON_FIN>` | Reprise sans intervention, sans doublon. | |
| 22 | | Attendre **2 minutes**, noter `<FIN>`, Ctrl+C sur le démon | | |
| 23 | B | **Étape 8** : `sdm120_verify.py` avec `--interval 10` et les trois `--outage` | Un constat par contrôle, la liste des trous, et le verdict **Incomplet (code 3)**, seul T7 non évalué. | Voir la section 2. |

Pour l'étape 8, la commande exacte est celle du guide, en remplaçant `--interval 60` par
`--interval 10`. Les heures s'écrivent avec fuseau (`2026-10-21T09:10:00Z`).

Remarque sur `--direct-json` : la lecture directe du compteur (étape 2 du guide) n'a pas de
sens avec le simulateur. Lancez-la quand même une fois pour vérifier que la commande se déroule
sans réseau : `PYTHONPATH=. python scripts/sdm120_preflight.py --host 127.0.0.1 --port 5020
--json-out ~/sdm120-lecture-directe.json`. Les contrôles dépendant de l'afficheur restent
« non évalués », et c'est normal.

## 6. Après l'essai

1. Arrêtez les services : Ctrl+C dans les terminaux, puis `cd infra && docker compose down`.
2. Rallumez le réseau.
3. Recopiez dans la fiche (section 7) les heures notées, le verdict et le code de sortie. Gardez
   le rapport JSON (`~/sdm120-rapport.json`) : il ne contient que des codes et des nombres.
4. Faites-moi parvenir la fiche remplie et le rapport. Tout écart noté en section 7 est un défaut
   à corriger **avant** d'aller sur site.

## 7. Fiche de résultats (à copier et remplir)

| Élément | Valeur |
| --- | --- |
| Date, heure (UTC) du début | |
| Système (Windows, macOS, Linux) et version de Docker | |
| Identifiant et date de l'image Keycloak (section 3, point 4) | |
| Réseau coupé prouvé (les trois commandes de la section 4 ont échoué) | oui / non |
| `docker compose up -d --pull never` réussi | oui / non |
| Console web utilisable sans réseau | oui / non (ressource externe notée : ) |
| Premier tour du démon : `inserted` / `rejected` | / |
| Coupure de l'API : mesures en tampon, puis renvoyées | oui / non |
| Coupure de la passerelle : donnée signalée périmée, puis rétablie | oui / non |
| Arrêt du démon : reprise sans doublon | oui / non |
| Verdict du vérificateur et code de sortie | |
| Contrôle en échec autre que T7 (nom et motif) | |
| Étapes qui ont échoué, et ce qu'elles semblent demander d'Internet | |

Tant que cette fiche n'est pas remplie, ce document reste « non validé ».
