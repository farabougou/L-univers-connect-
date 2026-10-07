"use client";

import { useRef, useState } from "react";

import { QrScanner } from "@/components/QrScanner";
import { colors, submitStyle } from "@/lib/formStyles";

/**
 * Bascule scan/annuler autour de QrScanner.tsx, et soumet le code décodé au
 * même formulaire (même action serveur) que la saisie manuelle de
 * /app/passeport/page.tsx — une seule résolution d'étiquette, jamais deux
 * chemins séparés.
 */
export function ScannerPanel({
  action,
  scanLabel,
  cancelLabel,
  hintLabel,
  deniedMessage,
  unsupportedMessage,
}: {
  action: (formData: FormData) => void | Promise<void>;
  scanLabel: string;
  cancelLabel: string;
  hintLabel: string;
  deniedMessage: string;
  unsupportedMessage: string;
}) {
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const codeRef = useRef<HTMLInputElement>(null);

  function handleDecode(payload: string) {
    setScanning(false);
    if (codeRef.current) codeRef.current.value = payload;
    formRef.current?.requestSubmit();
  }

  function handleError(reason: "denied" | "unsupported") {
    setScanning(false);
    setError(reason === "denied" ? deniedMessage : unsupportedMessage);
  }

  return (
    <div style={{ marginTop: 16 }}>
      {!scanning && (
        <button
          type="button"
          style={submitStyle}
          onClick={() => {
            setError(null);
            setScanning(true);
          }}
        >
          {scanLabel}
        </button>
      )}
      {scanning && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-start" }}>
          <QrScanner onDecode={handleDecode} onError={handleError} />
          <p style={{ color: colors.textMuted }}>{hintLabel}</p>
          <button type="button" onClick={() => setScanning(false)}>
            {cancelLabel}
          </button>
        </div>
      )}
      {error && <p style={{ color: colors.danger, marginTop: 8 }}>{error}</p>}
      <form ref={formRef} action={action} style={{ display: "none" }}>
        <input ref={codeRef} name="code" type="hidden" />
      </form>
    </div>
  );
}
