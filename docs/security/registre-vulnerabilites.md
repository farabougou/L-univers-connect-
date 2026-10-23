# Registre des vulnérabilités de dépendances

Établi le 21/10/2026 à partir de `npm audit` (web, mobile) et `pip-audit` (API), sur le
commit qui porte ce fichier. À refaire à chaque jalon : les chiffres changent avec les bases
d'avis, pas seulement avec notre code.

Lecture : « gravité » est celle de l'outil d'audit. « Exposition » dit où le code vulnérable
s'exécute réellement : sur le serveur ou l'appareil d'un client (production), ou
seulement sur le poste de développement et dans la CI. « Correction » dit s'il existe une
version corrigée **compatible** avec notre projet, pas seulement une version annoncée par
l'outil (l'option `npm audit fix --force` propose souvent une rétrogradation de version
majeure, qui n'est pas une correction).

## Synthèse

| Composant | Avant | Après | Corrigé | Reporté (justifié ci-dessous) |
| --- | --- | --- | --- | --- |
| API (Python) | 3 | **0** | 3, par remplacement de `python-jose` par PyJWT (21/10/2026, ADR 019) | 0 |
| Web | 5 | 5 | 0 (aucune version corrigée n'existe) | 5, outils de développement seulement |
| Mobile | 30 | 29 | 1 paquet (`vite`, outil de test) | 29, dont 1 présent dans l'application |

Aucune vulnérabilité critique. Aucune n'est exploitable sur le serveur de production dans
l'état actuel du code.

## Revue du 23/10/2026 (deux jours plus tard)

Mêmes outils, même lecture. Les bases d'avis ont bougé : un avis est apparu côté API, d'autres
ont disparu côté JavaScript.

| Composant | 21/10 | 23/10 | Ce qui a changé |
| --- | --- | --- | --- |
| API (Python) | 0 | **0** après correction | 11 avis sur `pypdf` 6.19.0 apparus entre-temps, **corrigés** en passant à `pypdf` 6.21.2 (même version majeure, `requirements.txt`). Exposition faible : `pypdf` ne lit que le formulaire CERFA vierge livré avec l'application (`app/fgas_pdf.py`), jamais un PDF envoyé par une personne. `pip-audit` sur `requirements.txt` et `requirements-dev.txt` : aucune vulnérabilité connue ; les 20 tests du PDF et de son API passent |
| Web | 5 | 3 (**0 en production**) | Les 5 paquets de la chaîne `braces` ne figurent plus dans l'audit. Trois avis nouveaux, tous des outils de développement : `vitest` et `@vitest/mocker` (moyenne : enregistrement de simulacres non authentifié, chemin Windows), `zod` (haute : épuisement de mémoire sur de grandes collections ; absent de `npm audit --omit=dev`) |
| Mobile | 29 | 13 (11 en production seule) | `braces` ne figure plus dans l'audit. Nouveaux : `zod` (haute, via `@expo/cli` : outillage de construction, pas l'application) ; `vitest` et `@vitest/mocker` (outils de test, comme sur le web). Les autres (`@expo/cli`, `node-forge`, `uuid` via `xcode`, `expo`, `expo-router`, `query-string`, `decode-uri-component`) sont ceux du 21/10 ; le seul présent dans l'application reste `decode-uri-component`, décrit plus bas |

**Pas de correction JavaScript dans cette revue, volontairement.** Pour `vitest` et `zod`, `npm audit`
annonce un correctif simple, mais sa simulation (`npm audit fix --dry-run`) réécrit le fichier de
verrouillage de façon massive (des dizaines de binaires d'autres systèmes d'exploitation ajoutés) :
une modification impossible à relire dans une revue, pour un risque limité aux postes de
développement et à la CI. À faire dans une étape dédiée, sur une branche à part, avec la suite de
tests et un essai de construction. Les propositions pour Expo (`expo@44.0.6`,
`expo-router@58.0.25`) restent rejetées : ce sont des rétrogradations ou des sauts de version
majeure.

**À décider par Mohamed : `main` ne contient presque rien.** La branche `main` du dépôt ne porte
que `CLAUDE.md` et le cahier des charges ; tout le code et l'historique vivent sur la branche de
travail (déployée par Railway) et la demande de fusion n° 1. Rien n'est perdu, mais le dépôt n'a
qu'un seul exemplaire du code à jour : fusionner la demande n° 1 dans `main` quand Mohamed le
décidera.

## API (Python) — `pip-audit`

**Résolu le 21/10/2026** par le remplacement de `python-jose` par PyJWT (décision de Mohamed,
ADR 019, branche `claude/pyjwt-migration`). Preuve : `pip-audit` sur la résolution complète de
`requirements.txt` :

| | Avant (`python-jose` 3.5.0) | Après (`PyJWT[crypto]` 2.15.1) |
| --- | --- | --- |
| Résultat | 3 vulnérabilités dans 2 paquets : `python-jose` PYSEC-2026-4298 ; `ecdsa` PYSEC-2026-1325 (listé deux fois) | **Aucune vulnérabilité connue** |
| Paquets retirés | — | `python-jose`, `ecdsa`, `rsa` (dépendances de `python-jose`) |

Historique de l'analyse (conservé, car il justifie le choix) : l'avis CVE-2026-85394 /
PYSEC-2026-4298 supposait qu'on laisse le jeton choisir son algorithme de vérification.
Notre code le fixait déjà (`algorithms=["RS256"]`, `["HS256"]`), et
`tests/test_token_algorithm_confusion.py` le prouve par l'attaque (clé publique sous quatre formes
utilisée comme secret HMAC, jeton sans signature, croisement des deux chemins). `ecdsa` n'était
jamais chargé à l'exécution. Le risque était donc surtout celui d'une bibliothèque non maintenue,
sans correctif à attendre.

### Audience — constat à décider (non corrigé)

Les jetons réels de Keycloak **n'ont aucune revendication `aud`** : constaté le 21/10/2026 sur
le staging (`aud` absent, `azp` = `paios-api`, revendications `iss`, `exp`, `iat`, `sub`,
`tenant_id`, `realm_access`…). `python-jose` ne contrôlait l'audience que si elle était présente ;
la connexion fonctionnait donc, mais **le contrôle d'audience de l'API (`OIDC_AUDIENCE`) n'était
en réalité jamais effectif** pour les jetons Keycloak. PyJWT, lui, exige `aud` dès qu'une audience
est attendue : une migration naïve aurait mis toute l'authentification en échec (401 partout). La
sémantique d'avant est donc conservée à l'identique (`app/auth.py::_check_audience`, testée).

Conséquence : un jeton émis par un autre client du même royaume est accepté par l'API tant que
`aud` est absent. Correction recommandée, en deux temps (décision de Mohamed) : (1) ajouter dans le
royaume un mapper d'audience (`oidc-audience-mapper`, `included.client.audience = paios-api`) au
client `paios-api` ; (2) une fois le staging vérifié, exiger `aud` (option PyJWT `require`). Tant
qu'un jeton sans `aud` doit rester valable, ne pas exiger `aud`.

### Différences de comportement assumées (banc de comparaison de 49 jetons, 45 identiques)

| Cas | Avant | Après | Pourquoi |
| --- | --- | --- | --- |
| Jeton sans `exp` (OIDC ou appareil) | accepté | **refusé** | un jeton qui n'expire jamais ; aucun jeton légitime n'en est dépourvu |
| `kid` inconnu du JWKS, ou désignant une clé de chiffrement | accepté (essayait toutes les clés) | **refusé** | le `kid` désigne la clé ; une signature valide d'une clé de confiance reste exigée |

Tout le reste est identique : algorithmes (RS256 fixé ; HS256 pour les jetons d'appareil ; ES256
pour les preuves), émetteur, expiration, `nbf`, audience quand elle est présente, format de
`iat` (jamais comparé à l'horloge, pour tolérer l'écart entre machines), codes d'erreur (401
`TOKEN_INVALID` / `DEVICE_TOKEN_INVALID`, 503 fournisseur indisponible). Tests :
`tests/test_token_verification.py` (58 avec `test_token_algorithm_confusion.py`).

**Point d'exploitation** : PyJWT émet un avertissement quand un secret HMAC fait moins de 32
octets (RFC 7518 §3.2). Le secret `DEVICE_TOKEN_SECRET` de staging est masqué pour moi : s'il est
plus court, les journaux afficheront `InsecureKeyLengthWarning` sans aucun refus. Utiliser un
secret d'au moins 32 octets aléatoires.

## Web (`apps/web`) — `npm audit`, 5 paquets

| Paquet | Gravité | Exposition | Correction |
| --- | --- | --- | --- |
| `braces` ≤ 3.0.3 (GHSA-vfj7-8cjw-p6xm) | Haute (épuisement de la pile par motifs imbriqués) | **Développement et CI uniquement** : chaîne `eslint-config-next` → `@next/eslint-plugin-next` → `fast-glob` → `micromatch` → `braces`. Jamais dans le build servi : l'image de production ne copie que la sortie `standalone` de Next.js (`apps/web/Dockerfile`), pas les outils de lint. Les motifs analysés sont ceux de notre propre configuration, pas une entrée externe. | **Aucune** : 3.0.3 est la dernière version publiée et elle est dans la plage affectée. |
| `micromatch`, `fast-glob`, `@next/eslint-plugin-next`, `eslint-config-next` | Haute (propagée depuis `braces`) | Idem. | Idem. `npm audit fix --force` propose `eslint-config-next@14.2.35` : c'est une **rétrogradation** de Next 16 vers 14, qui ne corrige rien. Rejetée. |

À surveiller : une version de `braces` supérieure à 3.0.3. Dès qu'elle existe, `npm update
braces` suffit (aucun changement de code).

## Mobile (`apps/mobile`) — `npm audit`, 29 paquets après correction

Les 29 paquets viennent de 4 avis racines (les autres paquets ne font que les propager).

| Avis racine | Gravité | Exposition | Correction |
| --- | --- | --- | --- |
| `vite` 8.3.0–8.3.2, via `launch-editor` (GHSA-587h-7wmj-h5pm, GHSA-698v-4r3x-3vcv, GHSA-r825-w8mm-5pxw) | Haute et moyenne | Développement : dépendance de test (`vitest`). Jamais dans l'application. | **Corrigé** : `vite` 8.3.5 (dépendance de développement explicite). Types et 121 tests mobiles vérifiés. |
| `braces` ≤ 3.0.3 (GHSA-vfj7-8cjw-p6xm) | Haute | Développement : outils Expo, Metro et Jest. Pas dans l'application livrée. | Aucune version corrigée (voir web). |
| `node-forge` ≤ 1.4.0 (GHSA-86w9-cpqp-85rv) | Haute (vérification de signature RSA PKCS#1 v1.5 trop permissive) | Développement : `@expo/code-signing-certificates` ← `@expo/cli` (signature des mises à jour EAS). Pas dans l'application. Aucune configuration de mises à jour EAS ni de signature de code dans `app.json` (vérifié). | Aucune : 1.4.0 est la dernière version et elle est dans la plage affectée. |
| `uuid` < 11.1.1 (GHSA-w5hq-g745-h8pq) | Moyenne (v3, v5, v6 avec un tampon fourni) | Développement : `xcode` 3.0.1 (préparation du projet iOS). `xcode` n'appelle que `uuid.v4()` sans tampon (vérifié dans son code) : l'avis n'est pas déclenchable. | Une surcharge de version est possible mais non testable ici sans compiler le projet iOS ; le risque que l'on évite est nul. Reporté. |
| `decode-uri-component` ≤ 0.4.2 (GHSA-vcc3-ghjq-m6fr) | Moyenne (déni de service par décodage exponentiel d'une chaîne mal formée) | **Dans l'application** : `expo-router` → `query-string` 7.1.3 → `decode-uri-component` 0.2.2, qui analyse les paramètres d'une adresse (lien profond). Une personne devrait ouvrir un lien piégé : l'effet est un gel de l'application sur son propre téléphone, sans fuite ni accès aux données. | Une version non affectée existe (0.5.0) mais elle est en **module ES seul**, alors que `query-string` 7.1.3 la charge avec `require` : la forcer risque de casser le routage de l'application et ne peut pas être vérifiée sans appareil. Reporté jusqu'à la mise à jour d'`expo-router`/`query-string`. |

Mesure en attendant : aucune. Le risque est un gel local déclenché par la personne
elle-même ; il est inférieur au risque de casser la navigation.

**Mise à jour d'Expo.** Les propositions de `npm audit` (`expo@44.0.6`, `react-native@0.72.17`,
`expo-router@58.0.24`) sont des rétrogradations ou des sauts de version sans lien avec les
avis : elles sont toutes rejetées. La vraie sortie est une montée de version d'Expo, à
planifier avec un essai sur téléphone.

## Conditions de réouverture

- Une version corrigée de `braces`, `node-forge` ou `python-jose` est publiée.
- `expo-router` ou `query-string` publie une version qui n'utilise plus `decode-uri-component` 0.2.x.
- Un avis passe de « développement » à « production » (par exemple si l'on embarque `eslint`
  dans une image de production).
- Mohamed décide de remplacer `python-jose` par `PyJWT`.
