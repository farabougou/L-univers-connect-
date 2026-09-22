import { Suspense } from "react";

import { LoginError } from "./LoginError";

export default function LoginPage() {
  return (
    <main style={{ maxWidth: 420, margin: "80px auto", textAlign: "center" }}>
      <h1>Physical Asset Intelligence OS</h1>
      <p>Console responsable d&apos;exploitation</p>
      <Suspense>
        <LoginError />
      </Suspense>
      <a
        href="/api/auth/login"
        style={{
          display: "inline-block",
          marginTop: 24,
          padding: "10px 24px",
          background: "#2563eb",
          color: "white",
          borderRadius: 8,
          textDecoration: "none",
        }}
      >
        Se connecter
      </a>
    </main>
  );
}
