# ADR 010 — Stockage hors ligne de l'application technicien

## Statut

Acceptée (22 septembre 2026).

## Contexte

Mohamed a été explicite dès la conception de l'application technicien (M1.3) :
certains sites n'ont littéralement aucun réseau, et une photo doit toujours être prise
avant toute intervention ou ronde, quel que soit le type. L'application doit donc
pouvoir créer une intervention et sa photo entièrement hors ligne, puis les envoyer
à l'API dès que le réseau revient — sans jamais perdre ce qui a été fait sur le
terrain.

Il existe plusieurs familles de solutions pour ça côté React Native/Expo :

1. **Un moteur de synchronisation réactif complet** (WatermelonDB, RxDB, PowerSync) :
   base locale qui reflète en continu l'état du serveur, avec gestion intégrée des
   conflits entre écritures concurrentes. Puissant, mais WatermelonDB exige un build
   natif (incompatible avec les tests rapides sous Expo Go déjà pénibles à mettre en
   place), et sa gestion de conflits résout un problème — plusieurs personnes modifiant
   la même fiche en même temps — que ce produit n'a pas encore : un technicien
   travaille seul sur ses propres interventions.
2. **Une simple file d'attente locale ("outbox")** : les créations faites hors ligne
   sont stockées dans une base SQLite locale, puis rejouées vers l'API dans l'ordre
   dès que le réseau est disponible. Pas de lecture hors ligne des données déjà sur le
   serveur, seulement l'envoi de ce qui vient d'être créé.

## Décision

**La file d'attente locale ("outbox") est retenue**, via `expo-sqlite` (déjà inclus
dans Expo, fonctionne dans Expo Go sans build natif dédié).

- Chaque intervention créée hors ligne est stockée localement avec un identifiant
  local, sa photo (copiée immédiatement dans le stockage permanent de l'application,
  jamais laissée dans un cache temporaire qui pourrait être vidé par le système), et
  son état de synchronisation.
- La synchronisation se déclenche automatiquement dès que le réseau redevient
  disponible (détecté via `@react-native-community/netinfo`), et peut aussi être
  lancée manuellement.
- Chaque étape de l'envoi (créer l'intervention, puis envoyer sa photo) met à jour la
  ligne locale au fur et à mesure : si l'envoi s'interrompt en cours de route, reprendre
  plus tard ne recrée jamais une intervention en double.
- Une fois entièrement envoyée, la ligne locale est supprimée : ce n'est qu'une file
  d'attente temporaire, pas un historique (l'historique complet vit côté serveur, voir
  la règle non négociable 3).

**Pas de moteur de résolution de conflits pour l'instant** (règle des trois) : tant
qu'un seul technicien crée ses propres interventions hors ligne, il n'y a rien à
réconcilier. Si un vrai besoin de collaboration multi-technicien sur la même fiche
apparaît, cette ADR sera révisée pour introduire une vraie stratégie de fusion.

## Conséquences

- Nouvelle table locale (téléphone uniquement, jamais côté serveur)
  `pending_interventions`, invisible en dehors de l'application.
- Les rondes et interventions déjà créées côté serveur ne sont pas mises en cache
  localement pour consultation hors ligne : ce n'est pas le besoin exprimé (créer,
  pas relire), et l'ajouter maintenant serait prématuré.
- Si Keycloak ou l'API changent d'adresse réseau après une longue période hors ligne,
  la synchronisation échoue proprement (la ligne reste en attente, rien n'est perdu)
  jusqu'à ce que le technicien soit de nouveau sur un réseau qui les joint.
