# Application technicien (mobile)

Application React Native avec Expo (voir la section 4 de `CLAUDE.md` pour le
choix de cette pile technique).

Cette première version fait une seule chose : se connecter via Keycloak (le
même flux sécurisé "Authorization Code + PKCE" que promis dans
`infra/README.md`) et afficher l'utilisateur, le tenant et les rôles renvoyés
par l'API (`GET /me`). C'est la preuve que le téléphone peut parler à toute la
chaîne (Keycloak + API) avant d'ajouter le mode hors ligne, les rondes et les
photos.

## Démarrer en local

Prérequis : `infra` (Keycloak) et `services/api` doivent déjà tourner (voir
le README à la racine du dépôt), et un téléphone avec l'application **Expo
Go** installée (App Store / Play Store), sur le **même réseau Wi-Fi** que
l'ordinateur. Un compte Expo gratuit (https://expo.dev/signup) est aussi
nécessaire, Expo l'exige désormais pour ouvrir un projet dans Expo Go.

Un téléphone physique ne peut pas joindre `localhost` : partout ci-dessous,
`<IP-ordinateur>` désigne l'adresse IP de l'ordinateur sur le réseau local
(Windows : `ipconfig`, ligne "Adresse IPv4" de la carte Wi-Fi).

1. Démarrer l'API en écoutant sur toutes les interfaces réseau, pas seulement
   `localhost` (depuis `services/api`, environnement virtuel activé) :

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --reload --no-access-log
   ```

2. Dans `services/api/.env`, faire pointer `OIDC_ISSUER` vers l'adresse IP de
   l'ordinateur, pas `localhost` : le jeton que le téléphone obtient auprès de
   Keycloak porte cette adresse comme émetteur, et l'API rejette (401) tout
   jeton dont l'émetteur ne correspond pas exactement à `OIDC_ISSUER`.

   ```
   OIDC_ISSUER=http://<IP-ordinateur>:8080/realms/paios
   ```

   Redémarrer l'API après ce changement.

3. Dans la console d'administration Keycloak (`http://localhost:8080/admin`,
   `admin` / `admin_dev_password`), realm **paios** → **Clients** →
   **paios-api** → onglet **Access settings** → **Valid redirect URIs** :
   ajouter une ligne (en plus du `*` déjà présent, que les versions récentes
   de Keycloak n'honorent plus seul) :

   ```
   exp://<IP-ordinateur>:8081/*
   ```

4. Installer les dépendances de l'application mobile :

   ```bash
   cd apps/mobile
   npm install
   ```

5. Copier `.env.example` en `.env` et remplacer `192.168.1.42` par l'adresse
   IP de l'ordinateur (voir les commentaires dans le fichier).

6. Démarrer le serveur de développement :

   ```bash
   npm start
   ```

   Un QR code s'affiche dans le terminal : le scanner avec l'appareil photo du
   téléphone (iOS) ou depuis l'application Expo Go (Android) ouvre
   l'application. Si Expo Go demande une connexion, se connecter avec le même
   compte Expo que celui utilisé sur l'ordinateur (`npx expo login`).

7. Dans l'application, appuyer sur "Se connecter" : l'écran de connexion
   Keycloak s'ouvre, se connecter avec `demo.technicien` / `demo-dev-only`
   (voir `infra/README.md`). De retour dans l'application, l'utilisateur, le
   tenant et les rôles doivent s'afficher.

## Vérifier que ça fonctionne

- "Se connecter" ouvre bien l'écran Keycloak (pas une erreur réseau).
- Après connexion, l'écran affiche `demo.technicien`, le tenant de démo et le
  rôle `technicien`, sans message d'erreur API.
- "Se déconnecter" revient à l'écran de connexion.

## Vérification de type et de qualité

```bash
npm run typecheck
npx expo-doctor
```

## Structure

```
app/            écrans (routage par fichier, voir Expo Router)
src/lib/        code partagé (authentification, configuration)
```
