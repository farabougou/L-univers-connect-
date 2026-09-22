# ADR 001 — Modèle sémantique des actifs

## Statut

Acceptée (22 septembre 2026).

## Contexte

Le cahier des charges (Partie I) vise un modèle d'actifs universel, valable pour tout
équipement physique, dans tout secteur. Écrire ce modèle universel avant d'avoir vu des
cas réels serait se tromper : la Partie II (section 25.1) le identifie comme le premier
risque structurant du projet. Le wedge de démarrage (maintenance CVC, froid et chaud du
tertiaire) donne un terrain concret pour construire un premier modèle, à généraliser
seulement après trois cas réels distincts (règle des trois, section 26.1).

Deux problèmes concrets doivent être résolus dès le premier objet métier (prévu à
l'étape M1, registre d'actifs) :

1. **Identité d'un actif dans le temps.** Remplacer un compresseur en panne ne doit pas
   faire perdre l'historique de sa position dans l'installation, ni celui du
   compresseur remplacé.
2. **Vocabulaire des points de mesure et des équipements.** Inventer une taxonomie
   maison coûte cher à maintenir et isole le projet des outils et intégrateurs du
   secteur du bâtiment.

## Décision

**Modèle d'identité à trois niveaux**, repris du cahier (section 27) :

- `ProductModel` : la référence catalogue d'un équipement (ex. « PAC modèle X du
  fabricant Y »), indépendante de tout exemplaire physique.
- `PhysicalUnit` : un exemplaire physique précis, identifié par son numéro de série.
- `FunctionalLocation` : une position dans la hiérarchie de l'installation (ex.
  « sous-station nord, circuit 2 »), qui peut changer d'occupant (`PhysicalUnit`) au
  fil du temps sans perdre son propre historique.

**Sémantique : adopter un standard existant plutôt qu'en inventer un.** Le vocabulaire
des équipements, points de mesure et relations s'appuie sur **Brick Schema**, avec
import/export **Project Haystack** et **IFC** pour la structure du bâtiment quand elle
est disponible. Aucune taxonomie propriétaire n'est créée pour les concepts déjà
couverts par ces standards.

**Bitemporalité.** Chaque enregistrement portant un état métier distingue le temps de
validité (quand un fait était vrai dans la réalité) du temps de saisie (quand la
plateforme l'a su). Corriger une erreur de saisie passée ne doit jamais détruire ce qui
était connu à l'époque : c'est une exigence d'audit et de reproductibilité, cohérente
avec le journal d'audit chaîné (ADR non numéroté, étape 0.5) qui trace déjà qui savait
quoi et quand au niveau des actions, pas encore au niveau des données métier.

**Séquencement.** Ces trois niveaux d'identité, la sémantique Brick et la bitemporalité
ne sont implémentés qu'à partir de l'étape M1 (registre d'actifs), une fois un premier
cas réel disponible. Cette ADR fixe le cap avant l'écriture du code, pour éviter un
modèle ad hoc à l'étape M1 qu'il faudrait ensuite migrer.

## Conséquences

- Le schéma de données de M1 aura donc trois tables (ou plus) liées entre elles au lieu
  d'une seule table « équipements », dès le premier commit du registre d'actifs.
- Les migrations Alembic de M1 devront prévoir les colonnes bitemporelles
  (`valid_from`/`valid_to` et `recorded_from`/`recorded_to`, ou équivalent) dès la
  première table métier de M1, pas ajoutées après coup.
- Le noyau du modèle reste générique dans ses principes (trois niveaux d'identité,
  bitemporalité), mais ses champs spécifiques ne sont généralisés à d'autres domaines
  (froid, énergie, eau...) qu'après trois cas réels distincts, conformément à la
  stratégie produit du cahier des charges.
- Toute extension future du vocabulaire d'actifs doit d'abord chercher une
  correspondance dans Brick Schema avant de créer un champ ou une relation maison.
