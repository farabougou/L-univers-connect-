"""Génère la paire de clés d'un appareil Edge (modèle cible, voir
app/devices.py) : la clé privée reste sur cet appareil, seule la clé
publique affichée est à transmettre.

La clé privée n'est jamais envoyée où que ce soit par ce script : il ne
fait qu'écrire un fichier local et afficher la clé publique correspondante.
Réglez ensuite vous-même les permissions du fichier de clé privée (600) et
transmettez la clé publique affichée à un responsable d'exploitation ou un
administrateur, qui l'enregistre avec POST /devices (nouvel appareil) ou
POST /devices/{id}/public-key (migration ou rotation d'un appareil
existant) — jamais l'appareil lui-même qui ne peut pas s'auto-enregistrer.

Usage :
    python scripts/generate_device_key.py --out cle-privee.pem
"""

import argparse
import stat
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out", type=Path, required=True, help="Fichier où écrire la clé privée (PEM)"
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )

    args.out.write_bytes(private_pem)
    args.out.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600 : lecture/écriture du propriétaire seul

    print(f"Clé privée écrite dans {args.out} (permissions restreintes au propriétaire).")
    print("Ne la transmettez jamais. Clé publique à enregistrer côté plateforme :\n")
    print(public_pem.decode())


if __name__ == "__main__":
    main()
