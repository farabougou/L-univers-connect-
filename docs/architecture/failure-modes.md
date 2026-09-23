# Modes de défaillance — document vivant

> ADR 012, étape F6. Pour chaque composant **existant** : ce qui peut tomber en
> panne, ce que l'on voit, ce que fait le système aujourd'hui, et comment on
> reprend. À mettre à jour à chaque jalon (M1 à M5) et à chaque nouveau composant.
>
> Statuts : ✅ maîtrisé (comportement voulu et testé) · ⚠️ risque ouvert (connu,
> correction proposée) · ⏳ DEFER (prévu dans l'architecture, développé plus tard).
>
> Dernière mise à jour : 23 septembre 2026 (fin de F6).

## Principes transverses

1. **Fermer par défaut.** En cas de doute (tenant absent, jeton invalide,
   donnée douteuse), le système refuse ou ne fait rien, plutôt que de montrer ou
   déduire quelque chose de faux.
2. **Reprendre sans doublon.** Tout ce qui peut être renvoyé (mesures, envois
   mobiles) doit pouvoir l'être sans créer de doublon.
3. **Tracer sans exposer.** Chaque requête a un identifiant (`X-Request-ID`),
   renvoyé à l'appelant et présent dans chaque ligne de log JSON. Les logs ne
   contiennent ni jeton, ni identifiant de personne, ni chemin brut, ni message
   d'erreur (voir `services/api/app/observability.py`).
4. **Aucune commande d'équipement.** Aucune panne ne peut déclencher une action
   sur un équipement : le produit est en lecture seule (règle non négociable 1).

## Comment enquêter sur une panne

1. Demander à la personne l'identifiant affiché ou reçu (`request_id` dans une
   réponse 500, en-tête `X-Request-ID` sinon).
2. Filtrer les logs de l'API sur ce `request_id` : on obtient la route (modèle,
   pas le chemin brut), le statut, la durée, le tenant et, en cas d'erreur non
   gérée, le type d'erreur et les emplacements dans le code (`frames`).
3. L'API doit être démarrée avec `--no-access-log` : le log d'accès intégré à
   uvicorn écrit le chemin brut (codes d'étiquette, paramètres) ; notre
   middleware le remplace.

## 1. Base de données PostgreSQL

| Défaillance | Effet visible | Comportement actuel | Reprise | Statut |
|---|---|---|---|---|
| Base arrêtée ou injoignable | Réponses 500 ; `/health/db` répond 503 | Erreur non gérée journalisée (`http.unhandled_error`, type `OperationalError`) ; rien n'est écrit à moitié (une transaction par requête) | Redémarrer la base ; les clients renvoient (mobile : file d'attente ; Edge : renvoi idempotent) | ✅ |
| Contexte tenant absent sur une connexion | La requête ne voit **aucune** ligne | Politique RLS `NULLIF(current_setting(...), '')::uuid` → aucune ligne visible ni modifiable | Aucune : c'est l'effet voulu | ✅ testé pour chaque table |
| Toutes les connexions occupées | Requêtes lentes puis 500 après 30 s | Pool SQLAlchemy par défaut (5 + 10 en débordement) | Réduire les requêtes lentes ; dimensionner le pool par variable d'environnement | ⚠️ taille du pool non configurable aujourd'hui |
| Migration interrompue | Déploiement bloqué | Chaque migration Alembic est transactionnelle ; les retours arrière refusent de s'exécuter s'il existe des données métier | Corriger puis relancer ; jamais de migration destructive sans sauvegarde vérifiée (règle 6) | ✅ |
| Perte de la base | Perte de données | Sauvegardes : à mettre en place avec l'hébergement (M1) | Restauration testée | ⚠️ à faire avant le premier client |

## 2. Authentification (Keycloak / OIDC)

| Défaillance | Effet visible | Comportement actuel | Reprise | Statut |
|---|---|---|---|---|
| Keycloak injoignable, clés jamais chargées | 503 « fournisseur d'authentification indisponible » | Aucun jeton accepté sans vérification de signature | Automatique au retour de Keycloak | ✅ |
| Keycloak injoignable, clés en cache | Aucun effet pendant 5 min | Les clés publiques restent en cache 5 minutes | Automatique | ✅ |
| Rotation des clés de signature | 401 pendant au plus 5 minutes pour les jetons signés par la nouvelle clé | Cache non rafraîchi sur clé inconnue | Attendre l'expiration du cache | ⚠️ proposer : recharger le cache une fois quand le `kid` est inconnu |
| Jeton expiré pendant un travail hors ligne | Synchronisation mobile refusée (401) | Les envois restent dans la file locale | Reconnexion, puis synchronisation | ✅ |

## 3. Stockage des photos (compatible S3)

| Défaillance | Effet visible | Comportement actuel | Reprise | Statut |
|---|---|---|---|---|
| Stockage injoignable | L'envoi de la photo échoue côté mobile | L'intervention est créée, la photo reste en file locale | Nouvel essai à la prochaine synchronisation | ✅ |
| URL d'envoi expirée | Envoi refusé par le stockage | Une nouvelle URL est demandée à chaque essai | Automatique | ✅ |
| Photo renvoyée après une confirmation perdue | Aucun pour l'utilisateur | La première photo confirmée est gardée ; le second fichier reste dans le stockage sans lien en base | — | ⚠️ fichiers orphelins ; ⏳ nettoyage périodique des objets sans référence (tâche de fond) |
| Clé de stockage d'un autre client ou d'une autre intervention | 422 | Refusée : la clé doit être dans le dossier `tenant/intervention/` de la requête (faille corrigée le 23 septembre 2026 : avant, connaître une clé suffisait pour obtenir un lien de téléchargement) | — | ✅ testé |
| Photo supprimée du téléphone avant l'envoi | La ligne échoue à chaque synchronisation | Aucune file des envois rejetés | Intervention manuelle | ⚠️ ⏳ file des envois rejetés (M3) |

## 4. API (processus FastAPI)

| Défaillance | Effet visible | Comportement actuel | Reprise | Statut |
|---|---|---|---|---|
| Erreur de programmation sur une route | 500 au format RFC 9457, code `INTERNAL_ERROR`, message traduit contenant la référence (`request_id`) | Journalisée avec type et emplacements, **sans** le message (il peut contenir des valeurs métier) | Corriger ; retrouver le cas grâce au `request_id` | ✅ testé (F6) |
| Processus arrêté | Connexion refusée | L'hébergeur redémarre le conteneur | Automatique | ✅ (à vérifier au déploiement M1) |
| Catalogue de messages absent au déploiement | Messages remplacés par leur code ; les codes restent exacts | Le dossier `shared/i18n` doit être livré avec l'API (ou désigné par `I18N_DIR`) | Livrer le dossier | ⚠️ à vérifier au premier déploiement (M1) |
| En-tête `X-Request-ID` malveillant | Aucun | Remplacé s'il n'est pas court et sans caractère spécial : impossible d'injecter du texte dans les logs | — | ✅ testé |

## 5. Télémétrie (mesures)

| Défaillance | Effet visible | Comportement actuel | Reprise | Statut |
|---|---|---|---|---|
| Même relevé envoyé deux fois | Aucun | Clé primaire (point, date) : doublon exact accepté sans effet (200) | — | ✅ testé |
| Même date, valeur différente | 409 | Rien n'est écrasé (règle 3) | Enquêter sur la source | ✅ testé |
| Horloge du capteur ou de l'Edge en avance | Relevé marqué `clock_suspect` | Accepté mais signalé ; un constat de qualité est ouvert, les règles ne s'appliquent pas à ce relevé | Régler l'horloge | ✅ |
| Relevé très en retard (> 24 h) | Relevé marqué `late_arrival` | Accepté et signalé | — | ✅ |
| Capteur figé ou muet | Score de confiance bas | En dessous de 50/100, les règles d'alarme ne s'appliquent pas (pas de fausse alarme sur une donnée douteuse) | Vérifier le capteur | ✅ |
| Erreur pendant l'évaluation des règles | Le relevé est refusé (500) | Choix délibéré : mesure et règles dans la même transaction, jamais « enregistré à moitié » ; le contenu des règles est validé à leur création | L'émetteur renvoie (idempotent) après correction | ⚠️ une règle défaillante bloque l'ingestion de ses points ; ⏳ évaluation en tâche de fond (M3) |
| Relevé impossible à enregistrer (point inconnu, unité fausse) | 404 / 422 | Refusé, rien n'est gardé | — | ⏳ file des messages rejetés (M3) |

## 6. Règles, constats, alarmes

| Défaillance | Effet visible | Comportement actuel | Reprise | Statut |
|---|---|---|---|---|
| Même anomalie répétée | Un seul constat, compteur d'occurrences | Clé de déduplication + index unique partiel | — | ✅ testé |
| Configuration de règle erronée activée | Alarmes absentes ou fausses | Versionnée : on restaure la version précédente (nouvelle version, rien d'écrasé), raison obligatoire | Restaurer | ✅ |
| Fuseau horaire d'un état attendu mal saisi | Refus à la saisie | Fuseaux IANA validés ; base `tzdata` figée dans les dépendances | — | ✅ testé (heure d'été / d'hiver) |

## 7. Journal d'audit

| Défaillance | Effet visible | Comportement actuel | Reprise | Statut |
|---|---|---|---|---|
| Deux actions sensibles simultanées | Aucun | Verrou consultatif par tenant : la chaîne reste linéaire | — | ✅ verrou en place ; ⚠️ pas encore de test de concurrence |
| Modification ou suppression d'une entrée | Chaîne rompue | Écriture seule côté application ; `verify_chain_integrity` détecte la rupture | Enquête de sécurité | ⚠️ vérification non planifiée aujourd'hui ; ⏳ tâche de fond périodique + ancrage externe (ADR 008) |

## 8. Application technicien (mobile, hors ligne)

| Défaillance | Effet visible | Comportement actuel | Reprise | Statut |
|---|---|---|---|---|
| Pas de réseau pendant l'intervention | Aucun | Saisie dans SQLite ; envoi au retour du réseau | Automatique | ✅ |
| Réseau coupé entre deux étapes d'envoi | Aucun | Chaque étape est notée localement ; la reprise ne recommence pas une étape confirmée | Automatique | ✅ testé |
| Réponse du serveur perdue après création | Aucun | Chaque envoi porte l'identifiant local (`client_ref`, unique par tenant en base) : un renvoi identique rend l'intervention ou la photo déjà créée (200), un contenu différent est refusé (409) | Automatique | ✅ testé (corrigé le 23 septembre 2026, migration `c0b50f293eec`) |
| Passeport consulté sans réseau | Message « le passeport se consulte en ligne » | Le passeport n'est pas mis en cache (données vivantes : alarmes, mesures) | Réessayer avec du réseau | ✅ testé |
| Étiquette révoquée scannée | Message « scannez la nouvelle étiquette » (410) | Un code révoqué n'est jamais réattribué | Poser la nouvelle étiquette | ✅ testé |

## 9. Application web

| Défaillance | Effet visible | Comportement actuel | Reprise | Statut |
|---|---|---|---|---|
| API indisponible | Page d'erreur | Aucune donnée mise en cache côté navigateur | Réessayer | ✅ |
| Session expirée | Retour à la connexion | Jetons dans un cookie httpOnly, illisibles par le JavaScript de la page | Se reconnecter | ✅ |

## Hors périmètre de ce document aujourd'hui

- Agent Edge, lien MQTT, identité des appareils : M3-M4 (le document sera complété
  quand ces composants existeront).
- Métriques, traces OpenTelemetry, chaîne des causes : ⏳ M3-M4 (ADR 012, point 21).
