Physical Asset Intelligence OS — instructions pour Claude Code
1. Comment travailler avec moi
	•	Je m'appelle Mohamed. Je suis technicien CVC (tertiaire) et développeur débutant.
	•	Réponds toujours en français.
	•	Une seule étape concrète à la fois. Ne m'empile pas plusieurs tâches. Termine l'étape, montre comment la vérifier, puis attends mon accord avant la suivante.
	•	Explique le « pourquoi » de chaque choix en 2 ou 3 phrases simples, sans jargon inutile.
	•	Quand tu modifies un fichier, montre-moi le fichier complet corrigé, pas un extrait à insérer à la main.
	•	Si un blocage persiste après 2 tentatives, change d'approche tout de suite (solution de contournement, autre piste ou questions ciblées) au lieu de t'acharner.
	•	Vise des solutions robustes et durables. Pas de raccourcis « suffisants pour l'instant » sur la sécurité, l'isolation des clients ou l'historique des données.
	•	Avant toute action risquée (suppression, migration destructive, changement de dépendances majeur), explique-moi et demande mon accord.
2. Le produit en bref
Plateforme mondiale de gestion et d'intelligence des actifs physiques (multi-clients, edge-first). Vision complète : docs/spec/Cahier_des_charges_Physical_Asset_Intelligence_OS_v1.1.docx. Le cahier a une Partie I (vision v1.0) et une Partie II (décisions d'ingénierie v1.1, sections 25 à 39). En cas de conflit, la Partie II et la section 36 (plan MVP) priment pour le démarrage. Ajouts au cahier : docs/spec/vision-cible-physical-asset-intelligence-automation-os.md (ADR 004), docs/spec/spatial-bim-engine.md (ADR 011), docs/spec/architecture-addendum-v2.md (ADR 012, plan de migration F1 à F6) et docs/spec/product-language-directive.md (ADR 013, plan L1 à L6).
Premier produit (wedge) : maintenance et suivi des installations CVC, froid et chaud du tertiaire (PAC, groupes froids, dry coolers, CTA, pompes, sous-stations de réseaux urbains).
Ordre de construction : registre d'actifs + application technicien hors ligne (M1), puis squelette de bout en bout (M2), puis télémétrie en lecture seule (M3), puis Edge durci (M4), puis énergie et conformité (M5).
3. Règles non négociables
	1.	Aucune commande vers un équipement. Le produit est en lecture seule (niveau C0). Aucun code qui écrit vers un équipement, aucun modèle de langage qui commande quoi que ce soit.
		◦	Exception strictement limitée (décision explicite de Mohamed, 24/09/2026) : une commande peut être envoyée à un appareil explicitement simulé (device_type "simulated_relay" dans app/connectors/device_mapping.py), pour valider de bout en bout le pipeline logiciel de commande (autorisation → Desired State → Edge → exécution → Actual State → vérification → audit). Cette exception ne s'applique JAMAIS à un appareil réel, y compris le compteur SDM120 qui reste un capteur de mesure non pilotable — app/connectors/modbus.py reste sans aucune fonction d'écriture ; la seule fonction d'écriture du dépôt vit dans app/connectors/simulated_actuator.py et n'est appelée que pour ce device_type. Étendre cette exception à un appareil physique, même de test, exige une nouvelle décision explicite séparée, écrite ici.
	2.	Isolation des clients (tenants). Chaque table métier a un tenant_id. Isolation par PostgreSQL Row Level Security dès la première table. Chaque nouvelle table vient avec un test qui prouve qu'un autre tenant ne voit rien.
	3.	Rien n'est écrasé. Les modifications de l'état d'un actif créent une nouvelle révision (voir sections 3.1, 27.1 et 27.2 du cahier). Trois niveaux d'identité : ProductModel, PhysicalUnit, FunctionalLocation.
	4.	Audit. Toute action sensible écrit une entrée dans un journal append-only chaîné par hachage.
	5.	Pas de secret dans le dépôt. Variables d'environnement et .env.example seulement. Jamais de clé, mot de passe ou jeton commité.
	6.	Migrations en trois temps (élargir, migrer, contracter). Pas de migration destructive sans sauvegarde vérifiée et retour arrière.
	7.	Tests d'abord pour tout ce qui touche la sécurité, l'isolation, le temps et les unités.
	8.	Pas de dépendance à un constructeur dans le noyau. Toujours derrière un adaptateur.
	9.	Aucune donnée personnelle réelle dans les tests ou les exemples.
4. Pile technique du MVP
	•	Backend : Python 3.12, FastAPI, SQLAlchemy 2, Alembic, pytest, ruff.
	•	Base : PostgreSQL 16 (l'extension TimescaleDB s'ajoutera à l'étape M3).
	•	Web : Next.js + TypeScript (à partir de M1). Mobile : React Native avec Expo (à partir de M1).
	•	Développement local : Docker Compose.
	•	Hébergement du MVP : Railway (abonnement déjà payé). Le code doit rester portable (Docker, aucune dépendance propriétaire à Railway dans le code métier) pour pouvoir migrer vers un hébergeur européen si un client l'exige. Ne déploie rien avant l'étape M1 et sans mon accord.
	•	Comptes Apple Developer et Google Play déjà actifs (pour distribuer l'application technicien plus tard).
	•	Intégration continue : GitHub Actions.
	•	Hors périmètre pendant 12 mois : Kubernetes, Kafka, multi-région, marketplace de connecteurs, ML supervisé, logement, commandes actives.
5. Structure du dépôt
6. Feature Benchmark Matrix — référence mondiale sans réécriture (directive du 23 septembre 2026)
La cible reste le Physical Asset Intelligence & Automation OS : GTB/GTC + GMAO + EMS/énergie + IoT/Edge + Digital Twins + automatisation + contrôle distant sécurisé + maintenance prédictive + IA/ML + simulation + ESG + Fleet Intelligence + Web/mobile + API/connecteurs + multi-tenant + sécurité Zero Trust. Le noyau doit rester universel et pouvoir évoluer vers bâtiments, résidentiel, industrie, énergie, eau et infrastructures.
Principe de contrôle pour toute capacité d'action sur un équipement, aujourd'hui et demain : Observe → Understand → Decide → Simulate si nécessaire → Authorize → Execute → Verify → Learn. Un LLM ne pilote jamais directement un équipement physique critique ; toute commande passe par permissions, politiques de sécurité, limites déterministes et protections locales (ceci ne modifie pas la règle non négociable 1 : voir ADR 004).
Document vivant : docs/spec/feature-benchmark-matrix.md compare en continu notre plateforme aux solutions du marché (Idealys, UBBEE/IOTEVA, Smart & Connective, MaintForge, Schneider Electric, Siemens, Honeywell, Johnson Controls et autres acteurs pertinents). Colonnes obligatoires : Feature | Notre statut | Concurrent(s) | Standard | Priorité | Architecture concernée | Décision | Justification.
Pour chaque fonctionnalité importante identifiée chez un concurrent, appliquer ce processus dans l'ordre : (1) vérifier si elle existe déjà dans notre code, (2) si oui, évaluer si l'implémentation est assez robuste/sécurisée/extensible sinon REFACTOR, (3) si elle manque, déterminer si elle apporte une vraie valeur à notre vision, (4) si pertinente, l'ajouter à la roadmap et la concevoir proprement dans l'architecture existante, (5) si notre approche est meilleure ou volontairement différente, la garder et documenter pourquoi, (6) ne jamais ajouter une fonctionnalité uniquement pour augmenter leur nombre.
Toute évolution du code existant reçoit une étiquette explicite KEEP / REFACTOR / REPLACE / ADD / DEFER (DEFER : prévu dans l'architecture maintenant, développé plus tard). Interdiction de recommencer le projet depuis zéro. Architecture : monolithe modulaire (une API, un processus de tâches de fond du même code, l'agent Edge sur site) ; un module ne devient un service séparé que si la charge, la sécurité ou l'organisation le justifient. Avant toute modification majeure, produire d'abord l'impact architectural et le plan de migration. L'objectif n'est pas d'avoir toutes les fonctionnalités immédiatement : c'est de construire une architecture qui permet d'en ajouter progressivement sans jamais devoir réécrire la plateforme.
Si une décision technique actuelle risque de bloquer une capacité future importante, le signaler avant de coder (section dédiée dans le document ci-dessus, tenue à jour).
Mettre à jour ce document à chaque jalon (M1 à M5) et à chaque fonctionnalité concurrente significative identifiée.
7. Langage produit, terminologie et internationalisation (directive du 23 septembre 2026)
La qualité du langage est un critère d'acceptation de toute fonctionnalité visible, au même titre que les tests. Texte de référence : docs/spec/product-language-directive.md ; décisions : ADR 013 ; référentiel : docs/product/glossaire.md.
	•	Un concept = un terme officiel par langue, pris dans le glossaire. Un terme absent y est ajouté avant d'apparaître à l'écran, dans l'API ou la documentation.
	•	Le système enregistre et transmet des codes stables + paramètres, jamais des phrases générées ; la phrase est produite à l'affichage, dans la langue de la personne. Les règles métier et les tests dépendent du code, pas du texte.
	•	Aucun texte visible écrit en dur dans un composant quand un catalogue existe ; toute clé existe en français et en anglais.
	•	Vouvoiement, phrases complètes, pas d'émoji, pas de familiarité, pas de ton alarmiste ; « critique » uniquement selon la définition de gravité.
	•	Ne jamais affirmer plus que ce que le système sait : niveau de certitude affiché ; « hors ligne » montre le dernier état connu et sa date ; une valeur estimée ou simulée n'est jamais présentée comme mesurée.
	•	Erreurs visibles : ce qui n'a pas pu être fait et l'action possible, sans détail technique, avec l'identifiant de requête.
	•	Avant de livrer un texte visible : orthographe, grammaire, ponctuation, terminologie, cohérence, clarté, traduction, accessibilité, absence d'ambiguïté.
