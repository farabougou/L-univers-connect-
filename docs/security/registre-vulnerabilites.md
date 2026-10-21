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
| API (Python) | 3 | 3 | 0 (aucune version corrigée n'existe) | 3, dont 1 neutralisé par un test |
| Web | 5 | 5 | 0 (aucune version corrigée n'existe) | 5, outils de développement seulement |
| Mobile | 30 | 29 | 1 paquet (`vite`, outil de test) | 29, dont 1 présent dans l'application |

Aucune vulnérabilité critique. Aucune n'est exploitable sur le serveur de production dans
l'état actuel du code.

## API (Python) — `pip-audit`

| Avis | Paquet | Gravité | Exposition | Correction |
| --- | --- | --- | --- | --- |
| CVE-2026-85394 / PYSEC-2026-4298 | `python-jose` 3.5.0 | Non fournie par l'outil. L'avis décrit la falsification de jetons : impact élevé s'il était exploitable. | **Production, mais non exploitable chez nous** (voir ci-dessous). | Aucune version corrigée publiée. |
| CVE-2024-23342 / PYSEC-2026-1325 | `ecdsa` 0.19.2 (dépendance de `python-jose`) | Non fournie par l'outil. Attaque par mesure du temps de **signature** ECDSA. | **Aucune** : le module n'est pas chargé. | Aucune : le mainteneur considère ces attaques hors périmètre. |

(`ecdsa` est listé deux fois par l'outil, pour la même fiche : un seul avis.)

**`python-jose` — pourquoi ce n'est pas exploitable chez nous.** L'avis suppose qu'on laisse
le jeton choisir son algorithme de vérification. Notre code le fixe toujours
(`app/auth.py`) : `algorithms=["RS256"]` pour le fournisseur d'identité, `algorithms=["HS256"]`
avec un **secret** (jamais une clé publique) pour les jetons d'appareil. Preuve par l'attaque :
`tests/test_token_algorithm_confusion.py` forge un jeton HS256 signé avec la clé publique
sous quatre formes (PEM, DER SPKI, DER PKCS#1, module JWK), un jeton sans signature, et
croise les deux chemins (un jeton d'appareil n'ouvre pas le chemin OIDC et inversement) : tout
est refusé, avec un jeton légitime comme témoin.

**`ecdsa` — pourquoi aucune exposition.** `python-jose[cryptography]` délègue toutes les
opérations à la bibliothèque `cryptography` (vérifié : `ecdsa` n'est pas importé à
l'exécution). Nous ne signons de toute façon aucun jeton ECDSA côté serveur : les
assertions d'appareil sont seulement **vérifiées** (`app/devices.py`), et l'attaque vise la
signature.

**Décision proposée, non exécutée** (changement de dépendance dans le noyau
d'authentification, à valider par Mohamed, voir `CLAUDE.md` section 1) : remplacer
`python-jose` par `PyJWT` + `cryptography`. Cela supprime les trois avis d'un coup,
`python-jose` n'étant plus maintenu. Périmètre : `app/auth.py` et
`tests/jwt_helpers.py` ; les tests d'authentification et de sécurité machine existants servent
de filet. Estimation : une demi-journée.

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
