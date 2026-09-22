# Application web

Console web (Next.js) pour les responsables d'exploitation et administrateurs :
consultation du registre d'actifs, à terme planification des ordres de travail et
suivi des alarmes. L'application technicien reste mobile (`apps/mobile`), cette
console est pour ceux qui pilotent plusieurs sites depuis un bureau.

Se connecte via Keycloak avec le même flux "Authorization Code + PKCE" que
l'application mobile (voir `infra/README.md` et ADR 002), géré ici entièrement côté
serveur Next.js : le jeton d'accès n'est jamais exposé au JavaScript du navigateur
(cookie `httpOnly`).

## Démarrer en local

Prérequis : `infra` (Keycloak) et `services/api` doivent déjà tourner (voir le
README à la racine du dépôt).

1. Installer les dépendances :

   ```bash
   cd apps/web
   npm install
   ```

2. Copier `.env.example` en `.env` (les valeurs par défaut conviennent pour du
   développement local ; contrairement à l'application mobile, aucune adresse IP
   n'est nécessaire ici, le navigateur tourne sur le même ordinateur).

3. Démarrer le serveur de développement :

   ```bash
   npm run dev
   ```

4. Ouvrir http://localhost:3000, cliquer "Se connecter", se connecter avec
   `demo.admin` / `demo-dev-only` (voir `infra/README.md`).

## Vérifier que ça fonctionne

- "Se connecter" ouvre bien l'écran de connexion Keycloak.
- Après connexion, la page affiche l'utilisateur, ses rôles, et la liste des
  positions fonctionnelles enregistrées.
- "Se déconnecter" revient à l'écran de connexion.

## Vérification de type et de qualité

```bash
npm run typecheck
npm run lint
npm run build
```
