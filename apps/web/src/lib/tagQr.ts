import QRCode from "qrcode";

/**
 * QR d'une étiquette, généré localement (jamais via un service tiers) : le
 * contenu d'un QR imprimé et collé sur un équipement ne doit dépendre
 * d'aucune disponibilité externe.
 */
export function renderTagQr(payload: string): Promise<string> {
  return QRCode.toString(payload, { type: "svg", margin: 1, width: 220 });
}
