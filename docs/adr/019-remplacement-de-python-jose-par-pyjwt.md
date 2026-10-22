# ADR 019 — Remplacement de python-jose par PyJWT

## Statut

Acceptée (21 octobre 2026, décision de Mohamed). Réalisée sur la branche
`claude/pyjwt-migration`. Ne modifie aucune règle non négociable ; touche le noyau
d'authentification (`CLAUDE.md` section 1 : changement de dépendance majeur, approuvé
explicitement).

## Contexte

`python-jose` n'est plus maintenu et porte trois avis (PYSEC-2026-4298, PYSEC-2026-1325 ×2, ce
dernier via `ecdsa`) sans correctif publié. Le registre des vulnérabilités
(`docs/security/registre-vulnerabilites.md`) montrait qu'aucun n'était exploitable chez nous,
mais il n'y avait aucune version à attendre.

## Décision

Remplacer par `PyJWT[crypto]` 2.15.1 (publiée le 28/09/2026, aucune vulnérabilité connue) et
épingler `cryptography` 50.0.1 (importée directement par `app/devices.py`, jusque-là
transitive). Périmètre : `app/auth.py`, `app/devices.py`, `app/connectors/edge_client.py` et les
tests ; aucune route ni aucun contrat d'API ne change.

Méthode : un **banc de comparaison** de 49 jetons forgés à la main (indépendamment des deux
bibliothèques) a été soumis à l'ancien code (`python-jose` 3.5.0, dans un environnement séparé) et
au nouveau. 45 décisions identiques. Les 4 écarts sont des durcissements assumés (jeton sans
`exp`, `kid` inconnu), figés dans `tests/test_token_verification.py`.

## Ce que la comparaison a révélé (et qui aurait cassé la production)

1. **Les jetons réels de Keycloak n'ont pas de revendication `aud`.** PyJWT, contrairement à
   `python-jose`, exige `aud` dès qu'une audience est attendue : avec la configuration par défaut,
   toute connexion aurait échoué. L'audience reste donc contrôlée seulement si elle est présente
   (comportement conservé, testé), et le trou sous-jacent est consigné au registre avec la
   correction recommandée (mapper d'audience dans le royaume).
2. PyJWT compare `iat` à l'heure courante par défaut ; `python-jose` n'en contrôlait que le format.
   Deux machines (Keycloak, API) ont presque toujours quelques secondes d'écart : le contrôle de
   l'heure d'émission est désactivé, le format reste contrôlé.
3. Un JWKS de forme étrange peut faire lever une erreur brute (`KeyError`) à l'intérieur de PyJWT :
   elle est convertie en refus 401, jamais en erreur 500.

## Preuves

- `pip-audit` sur la résolution complète de `requirements.txt` : 3 vulnérabilités dans 2 paquets
  avant, aucune après.
- Tous les tests de sécurité d'authentification, de jetons d'appareil, de preuves signées, de
  confusion d'algorithme et d'isolation des clients passent (voir le rapport de lot).

## Alternatives écartées

- **Authlib / joserfc** : plus de surface (OAuth complet) pour un besoin limité à vérifier des
  jetons.
- **Écrire la vérification avec `cryptography` seule** : réimplémenter une partie de la norme JOSE
  dans le noyau d'authentification est exactement ce qu'on cherche à éviter.
- **Garder `python-jose` et attendre un correctif** : aucun n'est annoncé.
