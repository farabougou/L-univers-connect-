# ADR 018 — Synchronisation incrémentale du mobile pour les connexions faibles

## Statut

Acceptée (21 octobre 2026), dans le cadre de la consolidation V5. Ne modifie aucune
règle non négociable. Complète l'ADR 010 (mode hors ligne, envoi des interventions).

## Contexte

L'application mobile télécharge à chaque ouverture de l'écran Maintenance toute la liste
des interventions du client, et à chaque synchronisation toute la liste des équipements.
Mesuré le 21/10/2026 sur 100 000 interventions réalistes : **52,1 Mo bruts (3,44 Mo
compressés), 10 s côté serveur**. Sur une connexion faible, c'est inutilisable, et une
coupure en cours de route perd tout le travail.

## Décision

1. **Flux de changements par curseur**, côté serveur (`app/sync_feed.py`,
   `app/routers/sync.py`) : `GET /sync/interventions` et `GET /sync/functional-locations`
   rendent les lignes après un point de reprise, par pages (200 par défaut, 500 au plus), dans
   l'ordre `(date, identifiant)`. Ajout pur : aucune route existante n'est modifiée.
2. **Stockage local sur le téléphone** (`localSchema.ts` étape 5, `syncStore.ts`) : l'historique
   des interventions est gardé localement et lu page par page ; un point de reprise est
   conservé par flux. L'écran Maintenance lit le local (immédiat, utilisable hors ligne).
3. **Une page et son curseur sont enregistrés dans une seule transaction locale**
   (`syncFeed.ts`) : un arrêt brutal ne laisse jamais un curseur en avance sur les lignes.
4. **Fenêtre de 30 jours au premier parcours** (`since`) : un nouvel appareil ne télécharge
   pas des années d'historique. L'écran l'indique (« Historique limité aux 30 derniers
   jours »).
5. **Compression gzip** des réponses de 1 Kio et plus, lorsque le client l'accepte.

## Garanties

- **Pas de doublon** : l'identifiant départage les lignes de même date côté serveur ; côté
  téléphone, chaque ligne est insérée ou mise à jour par identifiant (`ON CONFLICT`).
- **Pas de perte à l'intérieur d'un parcours** ; **reprise** exactement après la dernière
  page appliquée.
- **Écritures tardives** : une ligne datée T peut devenir visible après qu'un client a dépassé
  T. En fin de parcours, le curseur remis est reculé de `OVERLAP` (5 min) ; le parcours suivant
  relit cette fenêtre, sans doublon grâce à l'identifiant.
- **Modifications** : une intervention n'est jamais modifiée par l'application (aucun
  `UPDATE` dans le code) ; un équipement l'est (archivage, désarchivage, espace), d'où la colonne
  `functional_locations.updated_at` tenue par un déclencheur, et le champ `archived` du flux.
- **« Suppressions »** : la plateforme n'efface rien (règle non négociable 3). Un équipement
  archivé est livré avec `archived = true` et retiré de la liste locale ; désarchivé, il revient.
- **Curseur refusé** (`400 SYNC_CURSOR_INVALID`, par exemple base du serveur restaurée) : le
  téléphone repart du début, sans doublon.
- **Travail borné par synchronisation** (40 pages de 100) et **délai maximal de 20 s par
  requête** : une requête qui ne répond jamais ne bloque pas toute la synchronisation.

## Limite assumée

Une transaction qui resterait ouverte plus de 5 minutes avant de se valider pourrait voir sa
ligne manquée. Aucune requête de l'application ne dure ce temps (une création d'intervention
est une seule requête de quelques millisecondes). La borne est fixée par un test
(`test_limite_assumee_...`) pour qu'elle ne change pas sans décision.

## Alternatives écartées

- **Pagination par décalage (`offset`)** : une ligne qui arrive pendant le défilement décale la
  page suivante (ligne sautée ou répétée). Gardée pour les listes web, où elle est sans risque.
- **Curseur fondé sur les identifiants de transaction PostgreSQL** (garantie exacte, sans
  fenêtre) : colonne supplémentaire sur chaque table suivie et dépendance à un détail interne
  de PostgreSQL ; disproportionné au regard de la borne ci-dessus. À reconsidérer si une
  table du flux reçoit des écritures longues.
- **Table de pierres tombales** : inutile tant que rien n'est supprimé physiquement.
- **Plafonner d'office `/interventions`** : aurait masqué des lignes sans prévenir (voir
  `app/pagination.py`).

## Hors périmètre (DEFER, avec raison)

- **Écran Alertes (mobile)** : non paginé. Le tri par gravité se fait sur le téléphone ; une
  page partielle pourrait cacher une alarme critique. À reprendre quand l'API saura trier par
  gravité côté serveur.
- **Pages web « Ordres de travail » et « Accueil »** : elles calculent des agrégats (pannes
  répétées, clôtures récentes, compteurs) sur les listes complètes. Les paginer changerait le
  sens de ces chiffres ; il faut d'abord des agrégats côté serveur (nouvelle fonctionnalité).
- **Écran Actifs (mobile)** : liste d'équipements bornée et lente à changer ; l'état de chaque
  équipement exige le réseau de toute façon.

## Mesures (machine de développement, 100 000 interventions, voir la matrice)

| | Octets bruts | Octets compressés |
| --- | --- | --- |
| Avant : `GET /interventions` | 52,1 Mo | 3,44 Mo |
| Premier parcours (30 jours, 2 879 lignes, 29 pages) | 0,91 Mo | 0,10 Mo |
| Une page de 100 lignes | 31,6 Ko | 3,4 Ko |
| Synchronisation courante, rien de nouveau | n.d. | 0,1 Ko |
| Synchronisation courante, 5 nouvelles interventions | n.d. | 0,4 Ko |
