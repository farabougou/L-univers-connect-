# Dossier réglementaire ENORYX

Index des références officielles utilisées comme sources de conception pour
Physical Asset Intelligence OS (ENORYX), demandé par Mohamed le 02/10/2026.
Chaque fichier cite sa source officielle, le cadre légal applicable, ce que
la plateforme doit prévoir, et l'état réel du code au moment de l'écriture
— jamais une conformité, une certification ou une validation qui n'a pas
été réellement obtenue.

## Règle impérative (directive du 02/10/2026)

Aucune absence de compte, client, matériel, identifiant API ou information
administrative ne doit bloquer V1, V2, V3 ou V4. Quand une intégration
réelle est impossible aujourd'hui, la plateforme construit quand même :

1. **le modèle de données** (une table ou une extension d'un modèle existant) ;
2. **le workflow** (les états réels par lesquels passe l'objet métier) ;
3. **l'interface** (ce qu'une personne peut faire dès aujourd'hui, sans l'intégration manquante) ;
4. **l'adaptateur abstrait** (une interface programmatique définie, une seule implémentation aujourd'hui, qui échoue explicitement plutôt que de prétendre réussir).

Puis le point qui reste réellement hors de portée — un compte, un jeton,
une spécification officielle non publiée — est étiqueté :

- **`DEFERRED_EXTERNAL_INTEGRATION`** : l'intégration dépend d'un système
  tiers (compte, API, jeton) non accessible aujourd'hui. Le modèle de
  données et le flux fonctionnent déjà sans elle.
- **`TO_FINALIZE`** : le contenu dépend d'une décision commerciale,
  juridique ou organisationnelle propre à l'entreprise qui exploite la
  plateforme (raison sociale, tarifs, juridiction…), pas d'un système
  externe. Un gabarit existe, à compléter et faire valider avant usage réel.

Ces étiquettes ne sont jamais un prétexte pour ne rien construire : voir
chaque fiche ci-dessous pour ce qui est réellement livré dès aujourd'hui.

## Sommaire

| Domaine | Référence officielle | Fiche | État |
|---|---|---|---|
| OPERAT / Éco Énergie Tertiaire | ADEME, arrêté du 10 avril 2020 | [01](01-operat-eco-energie-tertiaire.md) | Modèle + workflow + interface construits (02/10/2026) ; transmission automatique `DEFERRED_EXTERNAL_INTEGRATION` |
| BACS / GTB | Articles R175-1 à R175-6 du code de la construction | [02](02-bacs-gtb.md) | Déjà couvert par l'architecture existante (append-only, historique illimité) ; audit documenté, pas de nouveau code nécessaire |
| Trackdéchets / BSFF | API Trackdéchets (GraphQL) | [03](03-trackdechets-bsff.md) | Adaptateur abstrait construit (02/10/2026) ; consultation réelle `DEFERRED_EXTERNAL_INTEGRATION` |
| RGPD / CNIL | Registre des traitements (CNIL) | [04](04-rgpd-cnil.md) | Registre des traitements rédigé (02/10/2026) ; coordonnées réelles de l'exploitant `TO_FINALIZE` |
| Cybersécurité OT/GTB | ANSSI, cybersécurité des systèmes industriels | [05](05-anssi-cybersecurite-ot.md) | Audit de l'architecture Edge/OT existante contre les mesures ANSSI |
| Préparation commerciale | — | [06-commercial/](06-commercial/) | Gabarits `TO_FINALIZE` (CGV B2B, SLA, DPA, licence, mentions légales) |

Ce dossier est un document vivant : à mettre à jour à chaque fois qu'une
intégration externe listée ici devient réellement accessible (compte,
identifiants, spécification officielle), en remplaçant l'étiquette
`DEFERRED_EXTERNAL_INTEGRATION` par l'implémentation réelle plutôt qu'en la
supprimant silencieusement.
