import { useEffect, useRef, useState } from "react";
import * as AuthSession from "expo-auth-session";
import * as SecureStore from "expo-secure-store";
import * as WebBrowser from "expo-web-browser";

import { config } from "./config";

/** Clé du catalogue d'interface affichée en cas d'échec de connexion. */
export const SIGN_IN_FAILED = "mobile.home.sign_in_failed";

// Nécessaire pour que la fenêtre de connexion se referme correctement après
// le retour de Keycloak vers l'application (voir la doc expo-web-browser).
WebBrowser.maybeCompleteAuthSession();

const TOKENS_STORE_KEY = "paios_tokens";

// Endpoints standards OpenID Connect exposés par tout serveur Keycloak, pour
// le realm "paios" (voir docs/adr/002-authentification.md). Pas de découverte
// automatique ici : ça évite un aller-retour réseau de plus au démarrage.
function discovery(): AuthSession.DiscoveryDocument {
  return {
    authorizationEndpoint: `${config.oidcIssuer}/protocol/openid-connect/auth`,
    tokenEndpoint: `${config.oidcIssuer}/protocol/openid-connect/token`,
  };
}

async function loadStoredTokens(): Promise<AuthSession.TokenResponse | null> {
  const raw = await SecureStore.getItemAsync(TOKENS_STORE_KEY);
  if (!raw) return null;
  try {
    return new AuthSession.TokenResponse(JSON.parse(raw));
  } catch {
    return null;
  }
}

async function persistTokens(tokenResponse: AuthSession.TokenResponse): Promise<void> {
  await SecureStore.setItemAsync(
    TOKENS_STORE_KEY,
    JSON.stringify(tokenResponse.getRequestConfig()),
  );
}

/**
 * Connexion via le flux standard "Authorization Code + PKCE" (voir
 * infra/README.md) : jamais de mot de passe saisi dans l'application elle-même,
 * tout se passe dans l'écran sécurisé de Keycloak.
 */
export function useAuth() {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const tokenResponseRef = useRef<AuthSession.TokenResponse | null>(null);

  // Sans argument, Expo choisit automatiquement la bonne adresse de retour :
  // une adresse de test dans Expo Go (utilisé maintenant), une adresse
  // "paios://" dans l'application finale une fois publiée. Fixer un schéma en
  // dur ici casserait les tests avec Expo Go.
  const redirectUri = AuthSession.makeRedirectUri();

  const [request, response, promptAsync] = AuthSession.useAuthRequest(
    {
      clientId: config.oidcClientId,
      redirectUri,
      scopes: ["openid", "profile"],
      responseType: AuthSession.ResponseType.Code,
      usePKCE: true,
    },
    discovery(),
  );

  // Au démarrage, réutilise un jeton déjà obtenu précédemment plutôt que de
  // redemander une connexion à chaque ouverture de l'application.
  useEffect(() => {
    loadStoredTokens().then((tokenResponse) => {
      tokenResponseRef.current = tokenResponse;
      setAccessToken(tokenResponse?.accessToken ?? null);
      setIsLoading(false);
    });
  }, []);

  useEffect(() => {
    if (response?.type === "success" && request?.codeVerifier) {
      const { code } = response.params;
      AuthSession.exchangeCodeAsync(
        {
          clientId: config.oidcClientId,
          code,
          redirectUri,
          extraParams: { code_verifier: request.codeVerifier },
        },
        discovery(),
      )
        .then(async (tokenResponse) => {
          tokenResponseRef.current = tokenResponse;
          await persistTokens(tokenResponse);
          setAccessToken(tokenResponse.accessToken);
        })
        // Le détail technique ne s'affiche jamais : l'écran montre un message
        // du catalogue (ADR 013, point 13).
        .catch(() => setError(SIGN_IN_FAILED));
    } else if (response?.type === "error") {
      setError(SIGN_IN_FAILED);
    }
  }, [response, request, redirectUri]);

  /**
   * Renvoie un jeton garanti valide, en le rafraîchissant silencieusement si
   * besoin. Sans ça, la session expirerait au bout de quelques minutes
   * (durée de vie par défaut d'un jeton Keycloak) en pleine intervention sur
   * le terrain — toujours appeler ceci juste avant un appel à l'API plutôt
   * que d'utiliser `accessToken` directement.
   */
  async function getAccessToken(): Promise<string | null> {
    const tokenResponse = tokenResponseRef.current;
    if (!tokenResponse) {
      return null;
    }
    if (!tokenResponse.shouldRefresh()) {
      return tokenResponse.accessToken;
    }
    try {
      await tokenResponse.refreshAsync({ clientId: config.oidcClientId }, discovery());
      await persistTokens(tokenResponse);
      setAccessToken(tokenResponse.accessToken);
      return tokenResponse.accessToken;
    } catch {
      // Le jeton de rafraîchissement lui-même a expiré ou a été révoqué :
      // il n'y a pas d'autre choix que de redemander une connexion.
      tokenResponseRef.current = null;
      await SecureStore.deleteItemAsync(TOKENS_STORE_KEY);
      setAccessToken(null);
      return null;
    }
  }

  async function signOut() {
    tokenResponseRef.current = null;
    await SecureStore.deleteItemAsync(TOKENS_STORE_KEY);
    setAccessToken(null);
  }

  return {
    accessToken,
    isLoading,
    error,
    canSignIn: Boolean(request),
    signIn: () => promptAsync(),
    signOut,
    getAccessToken,
  };
}
