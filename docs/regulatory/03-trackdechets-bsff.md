# Trackdéchets / BSFF (bordereau de suivi de fluides frigorigènes)

## Référence officielle

- Documentation officielle : API Trackdéchets — <https://doc.trackdechets.beta.gouv.fr/>
- L'API officielle est en **GraphQL** (pas de REST public documenté).
- Trackdéchets est le registre national de traçabilité des déchets dangereux
  de l'État (beta.gouv.fr), qui porte notamment le BSFF (bordereau de suivi
  de fluides frigorigènes) exigé lors de la récupération de fluides
  frigorigènes fluorés.

## Ce qu'ENORYX doit prévoir

Un adaptateur futur pour le BSFF et la traçabilité des fluides — sans
compte Trackdéchets ni jeton d'API aujourd'hui.

## État réel du code (02/10/2026)

**Déjà fait** : la fiche d'intervention F-Gas (CERFA 15497*04,
`app/fgas.py`, fourni par Mohamed le 02/10/2026) enregistre déjà le numéro
de BSFF saisi par l'opérateur (`bsff_number`, texte libre) et
l'identification du ou des contenants (`container_identification`) — exactement
ce que le CERFA papier demande, sans dépendre de Trackdéchets.

**Construit aujourd'hui (02/10/2026)** : `app/connectors/trackdechets.py` —

- **Interface abstraite** : `TrackDechetsClient` (`get_bsff(bsff_id) ->
  BsffRecord | None`), dans le même style que les autres connecteurs
  protocolaires du dépôt (Modbus, BACnet, OPC UA, MQTT) : jamais d'appel
  réseau dans le noyau métier, toujours derrière un adaptateur remplaçable.
- **Seule implémentation aujourd'hui** : `NotConfiguredTrackDechetsClient`,
  qui échoue explicitement (`TRACKDECHETS_API_NOT_CONFIGURED`) plutôt que de
  prétendre avoir consulté un bordereau.
- Les champs de `BsffRecord` sont volontairement minimaux (`id`, `status`,
  `raw`) : faute d'accès à l'API réelle, aucune correspondance de champ
  Trackdéchets n'a été vérifiée — inventer un schéma détaillé aurait été
  pire que de ne pas en avoir.

**`DEFERRED_EXTERNAL_INTEGRATION`** : la consultation réelle d'un BSFF
(vérifier qu'un numéro saisi par un opérateur correspond bien à un
bordereau existant et à son statut). Nécessite un compte Trackdéchets, un
jeton API et la lecture du schéma GraphQL officiel avant tout
développement — aucune correspondance de champ ne doit être devinée.

**Pas encore fait, à faire quand l'accès API existera** : implémentation
GraphQL réelle de `TrackDechetsClient`, bouton de vérification sur l'écran
de saisie de la fiche F-Gas (à construire).
