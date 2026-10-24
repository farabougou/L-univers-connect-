import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Image de production autonome (voir apps/web/Dockerfile) : ne copie que
  // les fichiers réellement nécessaires à l'exécution, sans node_modules
  // complet ni code source.
  output: "standalone",
};

export default nextConfig;
