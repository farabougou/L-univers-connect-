# ADR 020 — Unités déclarées : l'API refuse un désaccord et ne convertit jamais

## Statut

Acceptée (21 octobre 2026, décision de Mohamed). Ne modifie aucune règle non négociable. Complète
l'ADR 012 §2.7 (vocabulaire des points et des unités).

## Contexte

Le vocabulaire accepte `W` et `kW` pour un capteur de puissance, mais rien ne comparait l'unité
d'un point à celle de la source. Un registre SDM120 répond en watts : relié à un point déclaré en
`kW`, il aurait été enregistré tel quel, facteur 1000, sans erreur. Seul un drapeau `out_of_range`
l'aurait signalé *après coup* (et seulement si une plage était définie).

## Décision

1. **L'émetteur déclare l'unité de ses valeurs** (champ optionnel `unit`, code UCUM) sur
   `POST /measurements`, `/measurements/batch` et `/edge/measurements`. Si elle diffère de celle
   du point, la mesure est **refusée, jamais stockée, jamais convertie** :
   - `MEASUREMENT_UNIT_CONVERSION_REQUIRED` : même grandeur, liée par un simple facteur ; le
     facteur est donné (W vers kW : `0.001`) ;
   - `MEASUREMENT_UNIT_MISMATCH` : autre grandeur, ou conversion qui n'est pas un facteur (°C et K) ;
   - `MEASUREMENT_UNIT_NOT_EXPECTED` : unité déclarée pour un point qui n'en a pas ;
   - `UNIT_UNKNOWN` : hors vocabulaire (UCUM est sensible à la casse : `kw` et `kWh` sont refusés).
   Le refus ne dépend jamais de la valeur : `0.5` ou `99.9` (dans la plage d'un point en kW) sont
   refusés comme `548`.
2. **La conversion est volontaire**, chez l'émetteur : il convertit puis déclare l'unité du point.
   La plateforme ne le fait pas à sa place, car une conversion automatique cacherait précisément
   l'erreur qu'on cherche à rendre visible.
3. **À la création d'une connexion Modbus**, l'unité du registre est comparée à celle du point
   (`MODBUS_UNIT_CONVERSION_REQUIRED`, `MODBUS_UNIT_MISMATCH`, `MODBUS_UNIT_NOT_EXPECTED`,
   `MODBUS_REGISTER_UNIT_UNKNOWN`) : le refus précède la première mesure.
4. **Le démon Modbus déclare l'unité du registre**, la garde dans le tampon hors ligne (une mesure
   renvoyée après une coupure garde son unité) et **journalise chaque refus en erreur**, au lieu de
   présenter une relève partiellement refusée comme réussie.
5. **L'import d'historique** (`scripts/replay_import.py`) accepte `--unit COLONNE=UCUM` ; sans
   déclaration, l'import continue mais l'absence de vérification est écrite à l'écran.

## Conséquences

- Les mesures historiques sont contrôlées comme les mesures en direct (même fonction), et un point
  validé ne peut plus changer d'unité (déjà garanti en base) : l'unité d'un historique ne bouge pas.
- `SDM120_POINTS` exprime désormais l'énergie en `kW.h` (code UCUM du vocabulaire) et non `kWh`.
- Champ additif et facultatif : aucun émetteur existant n'est cassé.

## Limites assumées

- **Un émetteur qui ne déclare pas d'unité n'est pas contrôlé** : les démons BACnet, OPC UA et MQTT
  n'envoient pas encore la leur (BACnet et OPC UA connaissent l'unité de leurs objets ; MQTT non).
  À traiter avec la tâche V5.1. Rendre la déclaration obligatoire casserait les émetteurs actuels.
- Les unités du vocabulaire sont peu nombreuses (pas de tension, de courant ni de fréquence).

## Alternatives écartées

- **Convertir automatiquement W vers kW** : exactement le comportement dangereux décrit plus haut.
- **Rendre `unit` obligatoire** : casse tous les émetteurs actuels ; à reconsidérer une fois les
  quatre démons migrés.
- **Se fier à la plage `min_value`/`max_value`** : une valeur « plausible » dans la mauvaise unité
  (0,5 W lu comme 0,5 kW) passe, et la plage est facultative.
