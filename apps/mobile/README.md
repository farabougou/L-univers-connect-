# Application technicien (mobile)

Application React Native avec Expo (voir la section 4 de `CLAUDE.md` pour le
choix de cette pile technique).

Cette première version fait une seule chose : se connecter via Keycloak (le
même flux sécurisé "Authorization Code + PKCE" que promis dans
`infra/README.md`) et afficher l'utilisateur, le tenant et les rôles renvoyés
par l'API (`GET /me`). C'est la preuve que le téléphone peut parler à toute la
chaîne (Keycloak + API) avant d'ajouter l'écran hors ligne, les rondes et les
photos.

## Démarrer en local

Prérequis : `infra` (Keycloak) et `services/api` doivent déjà tourner (voir
le README à la racine du dépôt), et un téléphone avec l'application **Expo
Go** installée (App Store / Play Store), sur le **même réseau Wi-Fi** que
l'ordinateur.

1. Installer les dépendances :

   ```bash
   cd apps/mobile
   npm install
   ```

2. Copier `.env.example` en `.env` et remplacer `192.168.1.42` par l'adresse
   IP de l'ordinateur sur le réseau local (voir les commentaires dans le
   fichier ; `localhost` ne fonctionne pas depuis un téléphone physique).

3. Démarrer le serveur de développement :

   ```bash
   npm start
   ```

   Un QR code s'affiche dans le terminal : le scanner avec l'appareil photo du
   téléphone (iOS) ou depuis l'application Expo Go (Android) ouvre
   l'application.

4. Dans l'application, appuyer sur "Se connecter" : l'écran de connexion
   Keycloak s'ouvre, se connecter avec `demo.technicien` / `demo-dev-only`
   (voir `infra/README.md`). De retour dans l'application, l'utilisateur, le
   tenant et les rôles doivent s'afficher.

## Vérifier que ça fonctionne

- "Se connecter" ouvre bien l'écran Keycloak (pas une erreur réseau).
- Après connexion, l'écran affiche `demo.technicien`, le tenant de démo et le
  rôle `technicien`.
- "Se déconnecter" revient à l'écran de connexion.

Si la connexion Keycloak échoue immédiatement, vérifier d'abord l'adresse IP
dans `.env`, puis que Keycloak comme l'API sont bien accessibles depuis un
navigateur du téléphone à `http://<IP-ordinateur>:8080` et `:8000`.

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
