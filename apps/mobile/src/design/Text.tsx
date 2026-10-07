import { Text as RNText, type TextProps } from "react-native";

import { colors } from "./colors";

/**
 * Texte par défaut en clair sur fond sombre (thème navy, 06/10/2026) :
 * `Text` de React Native n'hérite la couleur que d'un `Text` parent, jamais
 * d'un `View` — sans ce composant, tout texte sans couleur explicite reste
 * noir sur fond sombre et devient illisible. Un style passé en `style`
 * (ex. une couleur atténuée) continue de primer : appliqué après ce défaut.
 */
export function Text({ style, ...rest }: TextProps) {
  return <RNText {...rest} style={[{ color: colors.textPrimary }, style]} />;
}
