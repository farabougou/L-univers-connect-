# OPERAT / Éco Énergie Tertiaire

## Référence officielle

- Plateforme : OPERAT (ADEME) — <https://operat.ademe.fr/>
- Cadre légal : arrêté du 10 avril 2020 relatif aux obligations d'actions de
  réduction de la consommation d'énergie finale dans des bâtiments à usage
  tertiaire (« décret tertiaire »), publié sur Légifrance.
- L'ADEME est officiellement chargée de l'exploitation de la plateforme
  OPERAT (collecte des consommations, calcul des objectifs et des
  attestations).

## Ce que la réglementation demande

Chaque bâtiment ou partie de bâtiment à usage tertiaire de plus de 1 000 m²
doit déclarer chaque année, sur OPERAT : ses consommations d'énergie par
vecteur (électricité, gaz, réseau de chaleur, autre), sa surface, sa
catégorie d'activité et une année de référence, pour suivre sa trajectoire
vers les objectifs de réduction (-40 % en 2030, -50 % en 2040, -60 % en
2050 par rapport à l'année de référence). Une attestation annuelle est
générée par la plateforme une fois la déclaration complète.

## Ce qu'ENORYX doit prévoir

Consommations, années de référence, objectifs, attestations, imports/exports
et un futur adaptateur OPERAT — sans attendre un accès officiel à l'API
(aucun identifiant fourni à ce jour, et l'API publique n'est pas garantie
stable).

## État réel du code (02/10/2026)

**Déjà fait, indépendamment d'OPERAT** : le moteur interne de normalisation
énergétique (`app/energy/`) — agrégation d'un compteur, référence
énergétique versionnée, normalisation par degrés-jours, comparaison entre
deux périodes. Volontairement imperméable à toute réglementation (directive
de Mohamed, 24/09/2026) : OPERAT lira ses résultats, ne les modifiera
jamais.

**Construit aujourd'hui (02/10/2026)**, au-dessus de ce moteur :

- **Modèle de données** : `operat_declarations` (migration `ada08b67a28c`)
  — une déclaration par site et par année de référence (surface, catégorie
  d'activité, consommations par vecteur), isolée par tenant (RLS), gelée
  une fois transmise.
- **Workflow** : brouillon → prêt → transmis (`app/regulatory/operat.py`).
  Une déclaration ne peut devenir « prête » que si l'essentiel est renseigné
  (surface, catégorie, au moins une consommation) — jamais une déclaration
  vide.
- **Interface utile dès aujourd'hui, sans API officielle** :
  `export_operat_summary` produit les chiffres à saisir manuellement sur le
  portail OPERAT, dans l'ordre où il les demande ; `record_manual_submission`
  enregistre qu'une personne a bien transmis la déclaration sur le portail
  (date, nom, référence) — un vrai geste de traçabilité, pas un simulateur.
- **Adaptateur abstrait** : `OperatApiAdapter` (interface) et
  `NotConfiguredOperatApiAdapter` (seule implémentation) — un appel à
  `submit()` échoue explicitement (`OPERAT_API_NOT_CONFIGURED`) plutôt que
  de prétendre avoir transmis quoi que ce soit.

**`DEFERRED_EXTERNAL_INTEGRATION`** : la transmission programmatique à
OPERAT (si l'ADEME ouvre un jour une API documentée et que la plateforme
obtient des identifiants). Le jour venu, une nouvelle classe implémentant
`OperatApiAdapter` remplace `NotConfiguredOperatApiAdapter`, sans toucher au
modèle de données ni au workflow.

**Pas encore fait, à faire dans un prochain incrément (pas bloqué par
l'absence d'API)** : écran web/mobile pour remplir une déclaration,
endpoints API (`POST /operat/declarations`, etc.), remplissage automatique
des consommations depuis les résultats normalisés existants plutôt qu'une
saisie manuelle.
