import { useEffect, useState } from "react";
import * as AuthSession from "expo-auth-session";
import * as SecureStore from "expo-secure-store";
import * as WebBrowser from "expo-web-browser";

import { config } from "./config";

// Nécessaire pour que la fenêtre de connexion se referme correctement après
// le retour de Keycloak vers l'application (voir la doc expo-web-browser).
WebBrowser.maybeCompleteAuthSession();

const ACCESS_TOKEN_KEY = "paios_access_token";

// Endpoints standards OpenID Connect exposés par tout serveur Keycloak, pour
// le realm "paios" (voir docs/adr/002-authentification.md). Pas de découverte
// automatique ici : ça évite un aller-retour réseau de plus au démarrage.
function discovery(): AuthSession.DiscoveryDocument {
  return {
    authorizationEndpoint: `${config.oidcIssuer}/protocol/openid-connect/auth`,
    tokenEndpoint: `${config.oidcIssuer}/protocol/openid-connect/token`,
  };
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

  const redirectUri = AuthSession.makeRedirectUri({ scheme: "paios" });

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
    SecureStore.getItemAsync(ACCESS_TOKEN_KEY)
      .then(setAccessToken)
      .finally(() => setIsLoading(false));
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
        .then((tokenResponse) => {
          setAccessToken(tokenResponse.accessToken);
          return SecureStore.setItemAsync(ACCESS_TOKEN_KEY, tokenResponse.accessToken);
        })
        .catch((exchangeError: Error) => setError(exchangeError.message));
    } else if (response?.type === "error") {
      setError(response.error?.message ?? "connexion refusée");
    }
  }, [response, request, redirectUri]);

  async function signOut() {
    await SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY);
    setAccessToken(null);
  }

  return {
    accessToken,
    isLoading,
    error,
    canSignIn: Boolean(request),
    signIn: () => promptAsync(),
    signOut,
  };
}
