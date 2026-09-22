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
Plateforme mondiale de gestion et d'intelligence des actifs physiques (multi-clients, edge-first). Vision complète : docs/spec/Cahier_des_charges_Physical_Asset_Intelligence_OS_v1.1.docx. Le cahier a une Partie I (vision v1.0) et une Partie II (décisions d'ingénierie v1.1, sections 25 à 39). En cas de conflit, la Partie II et la section 36 (plan MVP) priment pour le démarrage.
Premier produit (wedge) : maintenance et suivi des installations CVC, froid et chaud du tertiaire (PAC, groupes froids, dry coolers, CTA, pompes, sous-stations de réseaux urbains).
Ordre de construction : registre d'actifs + application technicien hors ligne (M1), puis squelette de bout en bout (M2), puis télémétrie en lecture seule (M3), puis Edge durci (M4), puis énergie et conformité (M5).
3. Règles non négociables
	1.	Aucune commande vers un équipement. Le produit est en lecture seule (niveau C0). Aucun code qui écrit vers un équipement, aucun modèle de langage qui commande quoi que ce soit.
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
