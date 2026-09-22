# Vision cible : Physical Asset Intelligence & Automation OS

Formulée par Mohamed le 22 septembre 2026, en complément du cahier des charges
(`Cahier_des_charges_Physical_Asset_Intelligence_OS_v1.1.docx`). Reprise ici mot pour
mot comme document de référence ; voir l'ADR 004 pour l'audit du code existant et la
feuille de route de mise en œuvre qui en découle.

---

Je veux faire évoluer le projet existant sans repartir de zéro.

La vision cible est un Physical Asset Intelligence & Automation OS : une plateforme SaaS
universelle capable de superviser, maintenir, optimiser, automatiser et, lorsque c'est
autorisé et sûr, commander à distance des équipements physiques.

Le système ne doit pas être limité à l'industrie. Il doit pouvoir couvrir :

- bâtiments tertiaires et GTB/GTC ;
- bâtiments publics ;
- logements et résidences ;
- industrie ;
- énergie ;
- eau et infrastructures ;
- data centers ;
- équipements techniques distribués.

À partir du code existant, conserve ce qui est correctement conçu et fais évoluer
progressivement l'architecture pour intégrer les briques suivantes :

1. **Universal Asset Model + Digital Twins**
   Organisation → Portfolio → Site → Facility → Building/Plant/Infrastructure → Zone →
   System → Equipment → Component → Sensor/Actuator.
2. **GTB/GTC native**
   Plages horaires, calendriers, jours fériés, consignes, modes
   Occupied/Unoccupied/Night/Holiday, exceptions, priorités et overrides temporaires.
3. **Automation & Control Engine**
   Automatisations basées sur horaires, états, capteurs, événements, occupation,
   énergie et politiques métier.
4. **Commande distante sécurisée**
   Possibilité d'envoyer des commandes aux équipements compatibles avec autorisations
   fines, validation des politiques de sécurité, traçabilité, accusé de réception et
   vérification de l'état réel après commande.
5. **Edge Runtime**
   Exécution locale, cache, store-and-forward, fonctionnement hors connexion et
   synchronisation avec le cloud.
6. **Connector/Protocol Layer**
   Architecture extensible pour BACnet, KNX, Modbus, MQTT, OPC UA et API constructeurs.
   Aucun constructeur ne doit être codé en dur dans le cœur de la plateforme.
7. **Universal Semantic Layer**
   Normalisation des équipements, points, unités et relations, avec possibilité de
   mapping vers des standards/ontologies comme Brick, Project Haystack, AAS et
   BIM/IFC lorsque pertinent.
8. **Semantic Discovery / Auto-Mapping**
   Assistance pour identifier et mapper automatiquement les points et équipements
   découverts. Toute utilisation pour le contrôle doit être validée avant activation.
9. **Maintenance / GMAO**
   Alarmes, incidents, ordres de travail, interventions, techniciens, pièces,
   historique et maintenance préventive/prédictive.
10. **Energy & Sustainability**
    Mesure et optimisation des consommations, coûts, puissance, énergie et indicateurs
    environnementaux.
11. **AI / ML**
    Détection d'anomalies, prédiction de défaillances, diagnostic assisté,
    optimisation et analyse de flotte. Ne pas utiliser un LLM comme contrôleur direct
    d'un équipement physique.
12. **Simulation Engine**
    Lorsque pertinent, permettre de simuler l'impact d'une stratégie ou modification
    avant son application.
13. **Fleet Intelligence**
    Analyse multi-sites et comparaison de cohortes d'équipements compatibles.
14. **Zero-Trust / Safety**
    RBAC/ABAC, isolation multi-tenant, audit immuable, commandes authentifiées/signées,
    gestion des secrets et séparation stricte entre observation, recommandation,
    automatisation et contrôle physique.

## Principe fondamental de commande

Observe → Understand → Decide → Simulate si nécessaire → Authorize → Execute → Verify →
Learn

Les actions physiques critiques ne doivent jamais dépendre directement d'une décision
libre d'un LLM. Les limites de sûreté, interlocks locaux et protections matérielles
doivent rester prioritaires.

## Consignes de mise en œuvre

Ne pas réécrire tout le projet simplement pour correspondre à cette architecture.

Commencer par auditer le code actuel et classer chaque partie en :
KEEP / REFACTOR / REPLACE / ADD.

Proposer un plan de migration progressif qui conserve au maximum le travail déjà
réalisé.

L'objectif à long terme est une plateforme mondiale, multi-tenant, multi-site,
multi-protocole, multi-constructeur et extensible par Domain Packs et Connector SDK.

Avant toute modification majeure du code, expliquer :

1. ce qui existe déjà ;
2. ce qui manque ;
3. ce qui doit être refactorisé ;
4. les dépendances entre les nouvelles briques ;
5. l'ordre de développement recommandé ;
6. les migrations de base de données nécessaires ;
7. les risques de régression ;
8. les tests nécessaires.

Ne pas supprimer ni remplacer une fonctionnalité existante sans justification
technique et sans vérifier ses dépendances.
