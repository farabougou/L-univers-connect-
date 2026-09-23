# Glossaire officiel du produit

> Référentiel terminologique unique (ADR 013). Il fait foi pour l'application web,
> l'application mobile, les notifications, les rapports, la documentation, l'API, le
> support, la formation et les supports commerciaux. Un concept = un terme officiel par
> langue. Toute nouvelle fonctionnalité visible utilise ces termes ; un terme absent est
> ajouté ici **avant** d'apparaître à l'écran.
>
> Statut : **projet** (23 septembre 2026). Les lignes « À valider » attendent la
> décision de Mohamed. Les définitions citant une norme sont à vérifier sur le texte de
> la norme lors de son acquisition.
>
> Colonnes : terme officiel (FR / EN) · code dans le modèle ou l'API · définition ·
> à ne pas employer pour ce sens · référence.

## 1. Organisation et espace

| Français | English | Code | Définition | À éviter | Référence |
|---|---|---|---|---|---|
| Client | Customer | `tenant` | Organisation cliente de la plateforme. Ses données sont isolées de celles des autres clients. | Locataire (ambigu en immobilier), établissement | — |
| Portefeuille | Portfolio | — (DEFER) | Ensemble des sites d'un client. | Parc (réservé à la flotte d'équipements) | ISO 55000 |
| Site | Site | `site` | Lieu géographique exploité, à une adresse, regroupant un ou plusieurs bâtiments. | Établissement, installation | ISO 41001 |
| Bâtiment | Building | `space_type = building` | Construction située sur un site. | Immeuble (sauf dans un nom propre) | IFC `IfcBuilding` |
| Niveau | Floor | `space_type = floor` | Étage d'un bâtiment. | Plancher | IFC `IfcBuildingStorey`, Brick `Floor` |
| Espace | Space | `space` | Terme général pour tout élément de la hiérarchie spatiale (bâtiment, niveau, zone, pièce, espace extérieur). **À valider** | Local employé comme terme général | IFC `IfcSpace`, Brick `Space` |
| Pièce | Room | `space_type = room` | Volume délimité d'un niveau (bureau, salle, local). | — | IFC `IfcSpace`, Brick `Room` |
| Espace extérieur | Outdoor area | `space_type = outdoor_area` | Surface extérieure d'un site (toiture-terrasse, parking). | — | Brick `Outdoor_Area` |
| Local technique | Plant room | à ajouter (`room` + usage) | Pièce réservée aux équipements techniques. **À valider** | Chaufferie ou sous-station comme terme générique | — |
| Zone | Zone | `space_type = zone` ; relation `servedBy` | Subdivision d'un bâtiment ou d'un niveau (plateau ouvert, zone CVC couvrant plusieurs pièces). Une pièce peut aussi être desservie par une zone sans en faire partie. | Secteur, partie | IFC `IfcZone`, Brick `Zone` |

## 2. Actifs et équipements

| Français | English | Code | Définition | À éviter | Référence |
|---|---|---|---|---|---|
| Actif | Asset | — | Terme générique pour tout bien géré par la plateforme. Employé dans la documentation et l'API, rarement à l'écran du technicien. | Bien, matériel | ISO 55000 |
| Équipement | Equipment | `functional_location` | Position technique stable remplissant une fonction (« CTA-02 — Bureaux R+1 »). Garde son historique quand l'appareil est remplacé. **À valider** (alternative : « Poste technique », convention SAP) | Machine, appareil, position | ISO 14224, ISO 81346 |
| Exemplaire | Unit | `physical_unit` | Appareil physique identifié par son numéro de série, installé à un équipement puis éventuellement déposé. **À valider** | Matériel, machine | ISO 14224 |
| Modèle | Product model | `product_model` | Produit d'un fabricant : fabricant + référence commerciale. | Type, gamme | — |
| Type d'équipement | Equipment type | `equipment_type` (étape L5) | Catégorie universelle normalisée (pompe à chaleur, groupe froid, centrale de traitement d'air…), indépendante de l'appellation du fabricant. | Catégorie libre | Brick (classes `Equipment`) |
| Désignation constructeur | Manufacturer designation | `manufacturer_designation` (L5) | Nom donné par le fabricant, conservé tel quel. | — | — |
| Composant | Component | relation `hasPart` | Élément d'un équipement pouvant être maintenu séparément (compresseur, ventilateur, vanne). | Pièce (réservé aux pièces de rechange) | ISO 14224 (élément maintenable) |
| Pièce de rechange | Spare part | `parts` (clôture) | Pièce consommée lors d'une intervention. | — | — |
| Système | System | — (DEFER) | Ensemble d'équipements assurant ensemble une fonction (réseau d'eau glacée, ventilation d'un plateau). | Installation | Brick `System` |
| Installation | — | — | **Non employé comme concept** : ambigu (un système ou l'action d'installer). Le verbe « installer » et l'état « Installé » restent employés pour un exemplaire. **À valider** | — | — |
| Établissement | — | — | **Non employé comme concept** du modèle ; peut apparaître dans un nom de site. | — | — |
| Jumeau numérique | Digital twin | — | Représentation numérique vivante d'un site et de ses équipements, construite à partir du registre, du graphe, de la télémétrie et de l'historique. Pas une base séparée. | Maquette (réservé au BIM) | ADR 004, ADR 011 |
| Étiquette | Tag | `asset_tag` | QR, NFC ou code-barres collé sur un équipement, contenant un code opaque. | QR code comme terme générique | — |
| Passeport | Asset passport | `passport` | Fiche de synthèse d'un équipement, calculée selon les droits de la personne. | Fiche équipement | Règlement ESPR (passeport produit) |
| Code d'inventaire | Asset code | `asset_code` (L5) | Code interne du client pour un exemplaire. | Référence (réservé au modèle) | — |

## 3. Cycle de vie d'un exemplaire

| Français | English | Code | Définition |
|---|---|---|---|
| Prévu | Planned | `planned` | Achat envisagé. |
| En approvisionnement | On order | `ordered` | Achat en cours. **Remplace « Commandé »** pour éviter la confusion avec une commande d'équipement. |
| En stock | In stock | `in_stock` | Disponible, non installé. |
| Installé | Installed | `installed` | Monté à un équipement, pas encore réceptionné. |
| Réceptionné | Commissioned | `commissioned` | Mise en service réalisée et acceptée. |
| En service | In service | `in_service` | En exploitation normale. |
| Hors service | Out of service | `out_of_service` | Retiré temporairement de l'exploitation. |
| Déposé | Removed | `removed` | Démonté de son équipement. |
| Réformé | Decommissioned | `decommissioned` | Retiré définitivement de l'exploitation. |
| Éliminé | Disposed | `disposed` | Sorti du patrimoine (recyclage, destruction). |

## 4. Données et télémétrie

| Français | English | Code | Définition | À éviter | Référence |
|---|---|---|---|---|---|
| Point | Point | `point` | Donnée élémentaire d'un équipement ou d'un espace : mesure, état, consigne, compteur, alarme. | Variable, tag (réservé à l'étiquette), donnée | Brick `Point`, BACnet object |
| Capteur | Sensor | `point_class` de mesure | Dispositif physique qui mesure une grandeur. Un capteur alimente un ou plusieurs points. | Sonde comme terme général (« sonde de température » reste correct) | Brick `Sensor` |
| Actionneur | Actuator | — | Dispositif qui agit physiquement (vanne motorisée, variateur). Représenté, jamais commandé (règle 1). | — | Brick |
| Consigne | Setpoint | `point_class` de consigne | Valeur visée par la régulation. Lue seulement (niveau C0). | Réglage, paramètre | Brick `Setpoint` |
| Mesure | Measurement | `measurement` (`origin = measured`) | Valeur d'un point à un instant, acquise automatiquement. | Donnée brute | — |
| Relevé manuel | Manual reading | `origin = manual` | Valeur saisie par une personne. | — | — |
| Valeur estimée / calculée / simulée | Estimated / derived / simulated value | `origin` | Valeur qui n'est pas une mesure ; toujours affichée comme telle. | Présenter comme une mesure | — |
| Qualité de la donnée | Data quality | `quality_flags` | Indicateurs attachés à une valeur (horloge suspecte, arrivée tardive, hors plage, point non validé). | — | — |
| Score de confiance | Trust score | `trust` | Note de 0 à 100 de la fiabilité récente d'un point. | Fiabilité (sans chiffre) | — |
| Unité | Unit | code UCUM | Unité de la valeur de référence, toujours liée à une grandeur physique. | Texte libre | UCUM |

## 5. États d'un équipement (deux axes distincts)

| Français | English | Code | Définition |
|---|---|---|---|
| En fonctionnement | Running | `running` | L'équipement fonctionne actuellement (point d'état récent et validé). |
| Arrêté | Stopped | `stopped` | À l'arrêt de façon volontaire ou normale. |
| Désactivé | Disabled | `disabled` | Fonctionnement explicitement interdit (autorisation de marche retirée). |
| En défaut | Fault | `fault` | L'équipement ou une règle signale un défaut. |
| État inconnu | Unknown | `unknown` | Les informations disponibles ne permettent pas de déterminer l'état. |
| En ligne | Online | `online` | Données reçues dans le délai attendu. |
| Hors ligne | Offline | `offline` | Aucune donnée reçue dans le délai attendu ; le dernier état connu est affiché avec sa date. |
| Injoignable | Unreachable | `unreachable` | Une tentative de communication a échoué (signalée par l'Edge, à partir de M3). |

## 6. Signalements

| Français | English | Code | Définition | Référence |
|---|---|---|---|---|
| Événement | Event | — | Tout fait daté enregistré par la plateforme (journal). Terme générique. | — |
| Constat | Finding | `finding` | Résultat d'une analyse (règle, contrôle de qualité, modèle) portant sur un point ou un équipement. | — |
| Anomalie | Anomaly | `event_type = anomaly` | Écart par rapport au comportement attendu, non encore qualifié. | — |
| Défaut | Fault | `event_type = fault` | État d'un équipement qui ne remplit pas, ou plus correctement, sa fonction. « Panne » n'est pas employé comme statut : le système ne peut pas l'affirmer sans vérification. | NF EN 13306 (panne) |
| Défaillance | Failure | — | Événement de perte d'aptitude à remplir une fonction (utilisé dans les statistiques de fiabilité). | NF EN 13306 |
| Alarme | Alarm | `event_type = alarm` | Signalement demandant une réponse d'un opérateur. | ISA-18.2 / IEC 62682 |
| Alerte | Alert | — | Signalement qui informe sans exiger de réponse immédiate. | ISA-18.2 |
| Incident | Incident | `event_type = incident` | Événement ayant eu un effet réel sur le service, les occupants, la sécurité ou la conformité, qualifié par une personne. | — |
| Action requise | Action required | `action_required` | Indicateur : une personne doit agir. Ce n'est pas une gravité. | — |
| Acquitter | Acknowledge | `ack_state` | Indiquer qu'on a pris connaissance d'un signalement. N'implique pas qu'il soit résolu. | ISA-18.2 |
| Retour à la normale | Return to normal | `condition_state = cleared` | La condition qui a déclenché le signalement n'existe plus. | ISA-18.2 |
| Faux positif | False positive | `handling_status = false_positive` | Signalement reconnu comme injustifié après examen. | — |

Gravités : voir ADR 013, section 4.3 (Information, Avertissement, Majeur, Critique).
Niveaux de certitude : voir ADR 013, section 4.4 (Anomalie détectée, Défaut confirmé,
Cause probable, Hypothèse de diagnostic, Prédiction, Recommandation, Résultat de
simulation, Information non disponible).

## 7. Maintenance

| Français | English | Code | Définition | À éviter | Référence |
|---|---|---|---|---|---|
| Ordre de travail | Work order | `work_order` | Demande planifiée et autorisée de travaux. Abréviation admise : OT. | Ticket, tâche | NF EN 13306 |
| Intervention | Intervention | `intervention` | Travail réalisé sur site par un technicien, avec son compte rendu. | Visite (sauf ronde) | — |
| Ronde | Inspection round | `intervention_type = ronde` | Contrôle de routine décrit par une liste de vérifications. | Tournée | — |
| Clôture | Closure | `intervention_closure` | Compte rendu structuré et définitif d'une intervention (symptôme, cause, action, pièces, vérification). | — | ISO 14224 |
| Symptôme / Cause / Action | Symptom / Cause / Action | codes de clôture | Codifications fermées de la clôture. | Texte libre | ISO 14224 |

## 8. Commandes et automatisation (vocabulaire réservé — aucune fonction active, règle 1)

| Français | English | Code | Définition |
|---|---|---|---|
| Commande | Command | `command` | Ordre envoyé à un équipement. **Inexistant aujourd'hui (niveau C0).** Ne jamais employer pour un achat. |
| Demandée | Requested | `requested` | Une personne ou une règle a demandé l'action. |
| Autorisée | Authorized | `authorized` | Les permissions et politiques ont validé la demande. |
| Envoyée | Sent | `sent` | Transmise vers l'équipement ; **pas** exécutée. |
| Reçue par l'équipement | Acknowledged | `acknowledged` | L'équipement a accusé réception. (Pas « acquittée », réservé aux alarmes.) |
| Exécutée | Executed | `executed` | L'équipement déclare l'avoir appliquée. |
| Vérifiée | Verified | `verified` | L'état réel mesuré correspond à l'état demandé. |
| En échec / Refusée / Expirée / Annulée | Failed / Rejected / Expired / Cancelled | `failed`, `rejected`, `expired`, `cancelled` | Issues sans exécution vérifiée. |
| État souhaité / État réel | Desired state / Actual state | `desired_state` | Attente déclarée / état mesuré. Déjà utilisé en lecture seule (F4). |
| Automatisation | Automation | — | Enchaînement automatique d'actions. DEFER. |
| Scénario | Scenario | — | Simulation « et si » ; ses résultats ne sont jamais des mesures. DEFER. |

## 9. Règles d'écriture

1. **Vouvoiement** dans toute l'interface ; phrases complètes ; pas d'émoji.
2. Structure d'un message, quand les informations existent : ce qui s'est produit → sur
   quel équipement → quand → effet éventuel → état actuel → action recommandée.
3. **Ne jamais affirmer plus que ce que le système sait** : employer le niveau de
   certitude ; « hors ligne » affiche le dernier état connu et sa date.
4. Confirmations d'actions sensibles : décrire l'action exacte, l'équipement, le site,
   l'état actuel et demandé, les conséquences connues. Jamais « Êtes-vous sûr ? ».
5. Erreurs : ce qui n'a pas pu être fait et ce que la personne peut faire ; jamais de
   détail technique ; l'identifiant de requête pour le support.
6. Termes anglais standard conservés quand ils sont la norme du métier (BACnet, Modbus,
   FDD, Brick), accompagnés d'une explication à la première occurrence.
7. Pas de ton alarmiste : la gravité est portée par le code de gravité, pas par les mots.

| À éviter | À employer |
|---|---|
| La machine a un problème. | Une anomalie de fonctionnement a été détectée sur l'équipement CTA-02. |
| La clim ne répond plus. | L'équipement CLIM-R+3 ne répond plus aux requêtes de communication depuis 14 h 05. |
| Ça n'a pas marché. | L'enregistrement de l'intervention n'a pas pu être effectué. Réessayez ; si le problème persiste, communiquez la référence 7f3a… au support. |
| Êtes-vous sûr ? | Confirmer la réforme de l'exemplaire SN-4521 (PAC-01, site Lyon Part-Dieu) ? Il ne pourra plus être installé. |
| Prends une photo avant d'enregistrer. | Une photo est requise avant l'enregistrement de l'intervention. |
