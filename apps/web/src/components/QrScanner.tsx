"use client";

import { useEffect, useRef } from "react";
import jsQR from "jsqr";

import { QR_PREFIX } from "@/lib/tagLookup";

/**
 * Scan QR par la caméra du navigateur (console web, 07/10/2026 : demandé
 * par Mohamed, jusqu'ici réservé à l'application mobile — ADR 014 §11
 * restait sur « le web génère/imprime l'étiquette, le mobile la scanne »,
 * décision assouplie explicitement ici). Safari iOS ne supporte pas l'API
 * native `BarcodeDetector` : décodage par `jsqr`, bibliothèque pure
 * JavaScript sans dépendance native, pas d'appel à un service tiers — même
 * principe que `renderTagQr` (génération locale, voir src/lib/tagQr.ts).
 *
 * Ignore tout QR qui n'est pas une étiquette de la plateforme (préfixe
 * `paios:tag:`) : une personne qui scanne un QR quelconque par erreur ne
 * doit pas voir une erreur technique, seulement rien ne se passer.
 */
export function QrScanner({
  onDecode,
  onError,
}: {
  onDecode: (payload: string) => void;
  onError: (reason: "denied" | "unsupported") => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        onError("unsupported");
        return;
      }
      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
        });
      } catch {
        onError("denied");
        return;
      }
      if (cancelled) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) return;
      video.srcObject = stream;
      await video.play();

      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d", { willReadFrequently: true });

      function tick() {
        if (cancelled || !video || !context) return;
        if (video.readyState === video.HAVE_ENOUGH_DATA) {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          context.drawImage(video, 0, 0, canvas.width, canvas.height);
          const frame = context.getImageData(0, 0, canvas.width, canvas.height);
          const result = jsQR(frame.data, frame.width, frame.height);
          if (result?.data.startsWith(QR_PREFIX)) {
            onDecode(result.data);
            return;
          }
        }
        frameRef.current = requestAnimationFrame(tick);
      }
      frameRef.current = requestAnimationFrame(tick);
    }

    start();

    return () => {
      cancelled = true;
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- démarre une seule fois, onDecode/onError restent stables côté appelant.
  }, []);

  return (
    <video
      ref={videoRef}
      playsInline
      muted
      style={{ width: "100%", maxWidth: 360, borderRadius: 8 }}
    />
  );
}
