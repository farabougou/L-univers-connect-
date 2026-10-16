# Directive transversale — langage produit, terminologie et UX writing professionnel

Formulée par Mohamed le 23 septembre 2026, en complément du cahier des charges, de la
vision cible (ADR 004), de l'exigence Spatial & BIM Engine (ADR 011) et de
l'Architecture Addendum V2 (ADR 012). Reprise ici mot pour mot comme document de
référence ; voir l'ADR 013 pour l'audit du code existant, l'impact architectural et le
plan de migration qui en découlent, et `docs/product/glossaire.md` pour le référentiel
terminologique.

---

NOUVELLE DIRECTIVE TRANSVERSALE — PRODUCT LANGUAGE, TERMINOLOGY & PROFESSIONAL UX WRITING
Cette directive complète toutes les exigences précédentes et doit désormais être appliquée à l’ensemble du projet.
Je veux que la qualité du langage du produit soit considérée comme une composante de l’architecture produit, et non comme une simple correction esthétique effectuée à la fin.
Le logiciel est destiné à des environnements professionnels : entreprises, bâtiments tertiaires, industries, infrastructures, énergie, établissements publics, hôtels, résidences, exploitants, techniciens, responsables de maintenance, gestionnaires de patrimoine, intégrateurs et décideurs.
Par conséquent, tous les textes visibles par les utilisateurs doivent utiliser un langage :

* professionnel ;
* précis ;
* respectueux ;
* clair ;
* grammaticalement correct ;
* sans fautes d’orthographe ;
* sans expressions familières ;
* sans jargon inutile ;
* cohérent dans toute la plateforme.

1. Créer un Product Language & Terminology System
Prévoir un référentiel terminologique centralisé pour l’ensemble du produit.
Ce référentiel devra définir les termes officiels utilisés dans :

* l’application Web ;
* les applications mobiles ;
* les notifications ;
* les alarmes ;
* les rapports ;
* les tableaux de bord ;
* la documentation ;
* l’aide utilisateur ;
* les e-mails ;
* les exports ;
* les API lorsque pertinent ;
* les outils destinés aux intégrateurs.

Un même concept ne doit pas changer de nom selon l’écran.
Par exemple, déterminer précisément l’usage de termes comme :
Site
Bâtiment
Installation
Établissement
Zone
Espace
Local
Système
Équipement
Actif
Composant
Capteur
Actionneur
Point
Événement
Alerte
Alarme
Défaut
Incident
Intervention
Ordre de travail
Commande
Consigne
Automatisation
Scénario
Digital Twin / Jumeau numérique.
Les choix terminologiques doivent être documentés.
2. Distinguer les états techniques
Ne jamais utiliser comme synonymes des états qui ont des significations différentes.
Par exemple :
En fonctionnement
L’équipement fonctionne actuellement.
Arrêté
L’équipement est volontairement ou normalement à l’arrêt.
Désactivé
Son fonctionnement a été explicitement désactivé.
Hors ligne
La plateforme ne dispose actuellement plus de connexion avec l’équipement ou sa source de données.
Injoignable
Une tentative de communication a échoué.
En défaut
L’équipement ou le système signale un défaut.
État inconnu
Les informations disponibles ne permettent pas de déterminer son état.
Ces distinctions doivent exister dans le modèle de domaine et pas uniquement dans l’interface.
3. Taxonomie des événements et niveaux de gravité
Définir clairement les catégories telles que :
Information
Avertissement
Alarme
Défaut
Incident
Action requise
Critique
Ne pas employer automatiquement « critique » pour attirer l’attention.
La gravité doit correspondre à une classification définie et exploitable par le système.
Séparer lorsque nécessaire :
`Event Type`
de :
`Severity`
de :
`Operational Status`
de :
`Acknowledgement Status`.
4. Messages professionnels
Éviter les formulations familières, vagues ou peu professionnelles.
Éviter par exemple :
« La machine a un problème. »
Préférer :
« Une anomalie de fonctionnement a été détectée sur l’équipement. »
Éviter :
« La clim ne répond plus. »
Préférer :
« Le système de climatisation ne répond actuellement plus aux requêtes de communication. »
Éviter :
« Ça n’a pas marché. »
Préférer :
« La commande n’a pas pu être exécutée. »
Le message doit, lorsque les informations sont disponibles, préciser :
ce qui s’est produit → sur quel actif → quand → impact éventuel → état actuel → action recommandée.
5. Ne jamais inventer une certitude
Le langage doit refléter le niveau réel de connaissance du système.
Différencier notamment :
« Défaut confirmé »
« Anomalie détectée »
« Cause probable »
« Hypothèse de diagnostic »
« Prédiction »
« Recommandation »
« Résultat de simulation »
« Information non disponible »
Une estimation IA ne doit jamais être formulée comme un fait confirmé.
6. Terminologie des commandes physiques
Pour toute action physique, utiliser un vocabulaire particulièrement précis.
Différencier :
`Requested / Demandé`
`Authorized / Autorisé`
`Sent / Envoyé`
`Acknowledged / Acquitté`
`Executed / Exécuté`
`Verified / Vérifié`
`Failed / Échec`
`Rejected / Refusé`
`Expired / Expiré`
`Cancelled / Annulé`
Une commande « envoyée » ne doit jamais être affichée comme « exécutée » tant que cela n’a pas été vérifié.
Cette terminologie doit être cohérente avec notre modèle :
Desired State ↔ Actual State
et avec :
Authorize → Execute → Verify.
7. UX Writing pour les actions sensibles
Les confirmations doivent décrire précisément l’action demandée.
Éviter :
« Êtes-vous sûr ? »
Préférer une formulation contextuelle telle que :
« Confirmer l’arrêt de l’équipement sélectionné ? »
Lorsque pertinent, afficher :

* l’équipement concerné ;
* le site ;
* l’action ;
* l’état actuel ;
* l’état demandé ;
* les conséquences connues ;
* les permissions ;
* l’auteur de l’action.

Les opérations présentant des conséquences importantes doivent utiliser des confirmations adaptées à leur niveau de risque.
8. Langage différent selon le profil utilisateur
Le système doit pouvoir présenter les informations avec un niveau de technicité approprié.
Exemples de profils :

* propriétaire ;
* gestionnaire ;
* responsable technique ;
* opérateur ;
* technicien ;
* mainteneur ;
* intégrateur ;
* administrateur ;
* ingénieur.

Un ingénieur peut avoir besoin de :
`BACnet Object`
`Telemetry`
`FDD`
`Command Arbitration`
`Connector Health`
alors qu’un gestionnaire doit obtenir une présentation métier compréhensible.
Ne pas supprimer l’information technique : adapter sa présentation.
9. Internationalisation dès l’architecture
Préparer correctement l’i18n.
Ne pas écrire les textes directement en dur dans les composants lorsque cela peut être évité.
Prévoir :

* translation keys ;
* locales ;
* formats de dates ;
* formats d’heures ;
* fuseaux horaires ;
* séparateurs numériques ;
* unités ;
* devises ;
* pluriels ;
* textes dynamiques ;
* formats régionaux.

Le français et l’anglais doivent être correctement supportables dès l’architecture, puis d’autres langues pourront être ajoutées.
10. Unités et grandeurs physiques
Créer une gestion cohérente des unités.
Ne pas traiter :
°C
°F
kW
kWh
MW
bar
Pa
L/min
m³/h
ppm
%
comme de simples chaînes de caractères arbitraires.
Les données doivent conserver leur grandeur physique, unité source et transformations lorsque nécessaire.
L’affichage pourra être adapté aux préférences/régions sans modifier la valeur de référence.
11. Séparer les identifiants techniques des noms visibles
Un actif doit pouvoir posséder notamment :

* immutable internal ID ;
* external/vendor ID ;
* asset code ;
* serial number ;
* display name ;
* localized label ;
* description.

Ne jamais utiliser un nom affiché à l’utilisateur comme identifiant technique fondamental.
12. Nomenclature des équipements
Prévoir un mécanisme permettant de normaliser différentes appellations constructeurs vers notre modèle universel.
Exemple conceptuel :
différents fabricants peuvent utiliser plusieurs appellations pour représenter le même type fonctionnel d’équipement.
Notre couche sémantique doit pouvoir conserver :
nom constructeur + nom normalisé + type universel + alias éventuels.
Cela facilitera :

* recherche ;
* analytics ;
* Fleet Intelligence ;
* maintenance ;
* IA ;
* interopérabilité.

13. Messages d’erreur
Les erreurs destinées aux utilisateurs ne doivent pas exposer inutilement :

* stack traces ;
* exceptions internes ;
* secrets ;
* identifiants sensibles ;
* informations d’infrastructure.

Séparer :
Technical Error
et :
User-Facing Error.
Le message utilisateur doit être compréhensible et, lorsque possible, indiquer une action utile.
14. Codes et traçabilité
Pour les événements importants, prévoir des codes stables indépendants du texte traduit.
Exemple conceptuel :
`COMMAND_TIMEOUT`
peut être affiché en français comme :
« La commande n’a pas été confirmée dans le délai prévu. »
et en anglais comme :
« The command was not confirmed within the expected time. »
Les règles métier doivent dépendre du code, pas de la phrase traduite.
15. IA et génération de texte
Toute IA générant des explications destinées aux clients doit respecter :

* terminologie officielle ;
* niveau de confiance ;
* langue sélectionnée ;
* profil utilisateur ;
* unités ;
* contexte du tenant ;
* règles de sécurité ;
* distinction entre faits et hypothèses.

Une sortie IA ne doit pas contourner la terminologie métier définie par la plateforme.
16. Documentation
Le même glossaire doit être utilisé dans :
Produit ↔ Documentation ↔ API ↔ Support ↔ Formation ↔ Commercial
Éviter qu’une fonctionnalité porte un nom dans l’application et un autre dans la documentation.
17. Qualité rédactionnelle
Avant mise en production d’une fonctionnalité visible par les utilisateurs, vérifier :

* orthographe ;
* grammaire ;
* terminologie ;
* ponctuation ;
* cohérence ;
* clarté ;
* niveau de langage ;
* traduction ;
* accessibilité ;
* absence d’ambiguïté.

Les textes temporaires ou approximatifs utilisés pendant le développement ne doivent pas devenir accidentellement les textes définitifs du produit.
18. Architecture
Avant d’ajouter une nouvelle infrastructure uniquement pour cette directive, auditer ce qui existe déjà :
KEEP / REFACTOR / REPLACE / ADD / DEFER
Ne pas surarchitecturer.
En revanche, les décisions structurantes concernant :

* i18n ;
* codes d’état ;
* severity ;
* unités ;
* identifiants ;
* taxonomie des actifs ;
* messages de commandes ;
* terminologie métier

doivent être conçues correctement suffisamment tôt, car elles deviennent coûteuses à corriger lorsque le produit grandit.
PRINCIPE FINAL
Je veux que la plateforme donne l’impression d’un logiciel conçu pour des professionnels de l’exploitation technique, de l’industrie, de l’énergie et du bâtiment.
Le vocabulaire doit inspirer :
précision, maîtrise, fiabilité et sérieux.
Éviter le ton familier, les formulations approximatives, les anglicismes inutiles et les messages alarmistes.
Lorsque le terme anglais constitue un standard technique reconnu, il peut être conservé ou accompagné de sa traduction.
La qualité du langage fait désormais partie des critères d’acceptation des fonctionnalités du produit.
