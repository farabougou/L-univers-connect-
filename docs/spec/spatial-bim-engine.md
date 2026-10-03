# Ajout au cahier des charges : Spatial & BIM Engine

Formulé par Mohamed le 23 septembre 2026, en complément du cahier des charges
(`Cahier_des_charges_Physical_Asset_Intelligence_OS_v1.1.docx`) et de la vision cible
(`vision-cible-physical-asset-intelligence-automation-os.md`). Repris ici mot pour mot
comme document de référence ; voir l'ADR 011 pour l'audit du code existant et la
conception qui en découle.

---

Cette exigence complète l'architecture actuelle ; elle ne doit pas provoquer une
réécriture du projet.

Je veux que la plateforme puisse représenter spatialement les bâtiments et relier cette
représentation au Universal Asset Model et aux Digital Twins.

À prévoir dans l'architecture :

## 1. Spatial Model

La hiérarchie doit pouvoir représenter :

Portfolio → Site → Building → Floor → Zone/Room → System → Equipment → Component →
Sensor/Actuator

Un équipement doit pouvoir être associé précisément à son emplacement.

## 2. BIM / IFC

Prévoir l'import et l'exploitation de modèles BIM/IFC lorsque le client en possède.

Le système doit pouvoir progressivement extraire et mapper les éléments pertinents vers
notre Asset Graph/Digital Twin.

## 3. Plans 2D

Les bâtiments sans BIM doivent pouvoir importer des plans PDF/image et, lorsque
pertinent, d'autres formats compatibles.

Prévoir un Floor Plan Viewer/Editor permettant de définir ou corriger :

- étages ;
- zones ;
- pièces ;
- emplacements des équipements ;
- capteurs ;
- actionneurs ;
- compteurs ;
- alarmes/points techniques.

## 4. Aucun plan obligatoire

Un bâtiment sans BIM et sans plan doit quand même pouvoir utiliser la plateforme.

L'utilisateur/intégrateur doit pouvoir construire manuellement :

Building → Floor → Zone/Room → Equipment

Le plan est donc une couche supplémentaire du Digital Twin, pas une dépendance
obligatoire.

## 5. Plan interactif

À terme, le plan doit devenir une véritable interface opérationnelle.

Exemple :

Plan → pièce → équipement → Digital Twin → données temps réel → historique → alarmes →
maintenance → énergie → commandes autorisées

Depuis le plan, un utilisateur autorisé doit pouvoir sélectionner une zone ou un
équipement et accéder à son état et aux actions disponibles.

## 6. Temps réel

Prévoir la possibilité d'afficher sur le plan :

- température ;
- qualité de l'air ;
- occupation lorsque cela est approprié et respectueux de la vie privée ;
- consommation ;
- éclairage ;
- HVAC/CVC ;
- alarmes ;
- état des équipements ;
- maintenance ;
- autres données issues des Digital Twins.

## 7. 2D puis 3D

Ne pas rendre la 3D obligatoire pour le lancement.

Concevoir correctement le modèle spatial dès maintenant afin de pouvoir ajouter ensuite
une visualisation BIM/3D sans devoir modifier le modèle fondamental.

Priorité recommandée :

Spatial Data Model → Floor Plan 2D → Asset Mapping → Real-Time Overlay → BIM/IFC avancé
→ 3D

## 8. Lien architectural fondamental

Je veux conserver cette relation :

Spatial Model ↔ Asset Graph ↔ Digital Twin ↔ Telemetry ↔ Automation/Control

Le plan ne doit jamais constituer une base de données séparée contenant sa propre
version des équipements.

Un équipement doit conserver un identifiant universel unique et le plan ne fait que
référencer cet actif.

## 9. Import assisté par IA

Prévoir à terme une assistance permettant d'analyser un plan ou un modèle BIM pour
proposer automatiquement pièces, zones et équipements.

Toute détection automatique doit rester vérifiable/corrigeable par l'utilisateur avant
d'être considérée comme fiable, particulièrement lorsqu'elle peut influencer une
automatisation ou une commande physique.

## 10. Sécurité

L'affichage d'un équipement sur un plan ne donne jamais automatiquement le droit de le
commander.

Les actions restent soumises au système RBAC/ABAC, aux politiques de sécurité, au
tenant concerné et aux règles du Control Engine.

Avant de développer cette partie, vérifie ce qui existe déjà dans le projet et applique
notre règle :

KEEP / REFACTOR / REPLACE / ADD

Ne crée pas un second modèle d'actifs uniquement pour le BIM ou les plans. Tout doit
rester relié au Universal Asset Core existant.
