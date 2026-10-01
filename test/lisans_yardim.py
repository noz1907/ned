# -*- coding: utf-8 -*-
"""GUI testleri için geçici lisans: geçici anahtar çifti, TAM lisans,
LOCALAPPDATA geçici klasör. pf3_gui import edilmeden ÖNCE çağrılır
(Uygulama.__init__ lisansı okur); __new__ ile kurulan nesnelere
`u.lisans = gecici_lisans()` verilir."""
import json
import os
import sys
import tempfile

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)


def gecici_lisans(paket="TAM"):
    tmp = tempfile.mkdtemp(prefix="pi3d_lisans_gui_")
    os.environ["LOCALAPPDATA"] = tmp
    os.environ.pop("PROGRAMDATA", None)
    import pf17_lisans as L
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    priv = Ed25519PrivateKey.generate()
    L.PUBLIC_KEY_HEX = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    ad, moduller = L.PAKETLER[paket]
    lic = {"type": "DENEME" if paket == "DENEME" else "LISANSLI", "customer": "TEST",
           "machine_id": L.makine_kimligi(), "product": "Pi3D", "license_tier": ad,
           "moduller": list(moduller), "features": ["base"], "issued": "2026-10-01"}
    if paket == "DENEME":
        lic["trial_data"] = L.DENEME_DATA
    lic["signature"] = priv.sign(L.canonical_payload(lic)).hex()
    os.makedirs(os.path.join(tmp, "Pi3D"), exist_ok=True)
    with open(os.path.join(tmp, "Pi3D", "pi3d.lic"), "w", encoding="utf-8") as f:
        json.dump(lic, f)
    return L.yukle()
