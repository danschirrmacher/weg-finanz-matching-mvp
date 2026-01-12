# coding: utf-8
"""
scoring_v1 – WEG-Finanzierungs-Matching (MVP)

Prinzipien:
- Datengetrieben, KO vor Scoring, Scoring ≠ Filter
- Profile ändern nur Gewichtungen (keine Regeln)
- Score nach Gewichtung immer auf 0–100 normieren
"""
from typing import Dict, Any, List, Optional, Tuple

# Basiskriterien (Max-Punkte je Kriterium – Summe 100)
BASE_MAX = {
    "keineHaftung": 25,
    "keineGrundschuld": 25,
    "enthaeftung": 10,
    "foerderung": 10,
    "kfw": 5,
    "laufzeit": 10,
    "kontokosten": 5,
    "verwendungFlex": 5,
    "bundesweit": 5,
}

# Profil-Gewichtungen (Multiplikatoren auf Kriteriumspunkte)
PROFILE_WEIGHTS = {
    "STANDARD": {},  # unverändert
    # FÖRDERFOKUS: Förderung +15, Kontokosten +10, Laufzeit -10
    "FOERDERFOKUS": {"foerderung": 1.15, "kontokosten": 1.10, "laufzeit": 0.90},
    # GROSSE_WEG: Laufzeit +15, Förderung -10, Kosten -5 (Kosten=Kontokosten)
    "GROSSE_WEG": {"laufzeit": 1.15, "foerderung": 0.90, "kontokosten": 0.95},
}

CLUSTERS = [
    (75, "EMPFOHLEN"),
    (50, "GEEIGNET"),
    (0,  "EINGESCHRÄNKT"),
]

HIGHLIGHT_LABELS = {
    "keineHaftung": "keine Haftung",
    "keineGrundschuld": "keine Grundschuld",
    "enthaeftung": "Enthaftung möglich",
    "foerderung": "Förderung möglich",
    "kfw": "KfW möglich",
    "laufzeit": "Laufzeit ≥ 10 Jahre",
    "kontokosten": "Kontokosten ≤ 3 €",
    "verwendungFlex": "flexible Verwendung",
    "bundesweit": "bundesweit",
}


def _norm_profile_name(profile: str) -> str:
    if not profile:
        return "STANDARD"
    p = profile.upper().strip()
    p = (p
         .replace("Ö", "OE")
         .replace("Ä", "AE")
         .replace("Ü", "UE")
         .replace("ß", "SS"))
    if p == "FÖRDERFOKUS" or p == "FOERDERFOKUS":
        return "FOERDERFOKUS"
    if p == "GROSSE_WEG" or p == "GROSSE WEG":
        return "GROSSE_WEG"
    return "STANDARD"


def volumen_pro_et(user_input: Dict[str, Any]) -> float:
    we = max(1, int(user_input.get("anzahlWE", 1)))
    return float(user_input.get("gesamtvolumen", 0)) / we


def ko_reason(product: Dict[str, Any], user_input: Dict[str, Any]) -> Optional[str]:
    # Ableitungen
    v_pro_et = volumen_pro_et(user_input)

    # 1) Region
    if user_input.get("region") not in product.get("region", []):
        return "region_nicht_enthalten"

    # 2) Laufzeit verfügbar
    if user_input.get("laufzeit") not in product.get("laufzeiten", []):
        return "laufzeit_nicht_verfuegbar"

    # 3) Gesamtvolumen min/max
    gv = float(user_input.get("gesamtvolumen", 0))
    if gv < float(product.get("minGesamtvolumen", 0)):
        return "gesamtvolumen_unter_min"
    max_gv = product.get("maxGesamtvolumen")
    if max_gv is not None and gv > float(max_gv):
        return "gesamtvolumen_ueber_max"

    # 4) Volumen je ET min/max
    if v_pro_et < float(product.get("minVolumenET", 0)):
        return "volumenProET_unter_min"
    if float(product.get("maxVolumenET", 1e12)) is not None and v_pro_et > float(product.get("maxVolumenET", 1e12)):
        return "volumenProET_ueber_max"

    # 5) Verwendung erlaubt
    verwendung = user_input.get("verwendung")
    erlaubte = product.get("verwendung", [])
    if verwendung not in erlaubte and "egal" not in erlaubte:
        return "verwendung_nicht_erlaubt"

    # 6) KO Flags: Grundschuld / pers. Haftung
    if product.get("grundschuld", False):
        return "grundschuld_erforderlich"
    if product.get("persHaftung", False):
        return "persoenliche_haftung_erforderlich"

    return None


def _criterion_points(product: Dict[str, Any], user_input: Dict[str, Any]) -> List[Tuple[str, float]]:
    """Gibt Basispunkte je Kriterium (0 bis Max) zurück."""
    pts = []
    pts.append(("keineHaftung", 25.0 if not product.get("persHaftung", False) else 0.0))
    pts.append(("keineGrundschuld", 25.0 if not product.get("grundschuld", False) else 0.0))
    pts.append(("enthaeftung", 10.0 if product.get("enthaeftung", False) else 0.0))
    pts.append(("foerderung", 10.0 if product.get("foerderungMoeglich", False) else 0.0))
    pts.append(("kfw", 5.0 if product.get("kfwMoeglich", False) else 0.0))
    pts.append(("laufzeit", 10.0 if int(user_input.get("laufzeit", 0)) >= 10 else 0.0))
    pts.append(("kontokosten", 5.0 if float(product.get("kontokostenPM", 999)) <= 3.0 else 0.0))
    erlaubte = product.get("verwendung", [])
    pts.append(("verwendungFlex", 5.0 if "egal" in erlaubte else 0.0))
    pts.append(("bundesweit", 5.0 if "DE" in product.get("region", []) else 0.0))
    return pts


def _weighted_and_norm(points: List[Tuple[str, float]], profile: str) -> Tuple[float, List[Tuple[str, float, float]], float]:
    """
    Wendet Profil-Gewichtungen an und normiert auf 0–100.
    Rückgabe: (score_norm, [(key, base, weighted)], denom)
    """
    prof = _norm_profile_name(profile)
    weights = PROFILE_WEIGHTS.get(prof, {})

    # Denominator: gewichtete Maxima (unabhängig vom einzelnen Produkt)
    denom = 0.0
    for key, mx in BASE_MAX.items():
        w = weights.get(key, 1.0)
        denom += mx * w
    if denom <= 0:
        denom = 100.0

    weighted = []
    total_w = 0.0
    for key, base in points:
        w = weights.get(key, 1.0)
        val = base * w
        weighted.append((key, base, val))
        total_w += val

    score = (total_w / denom) * 100.0
    score = max(0.0, min(100.0, score))
    return score, weighted, denom


def _cluster(score: float) -> str:
    for thr, name in CLUSTERS:
        if score >= thr:
            return name
    return CLUSTERS[-1][1]


def rank_products(products: List[Dict[str, Any]], user_input: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Filtert via KO, scored und liefert sortierte Ergebnisobjekte."""
    results = []
    for p in products:
        reason = ko_reason(p, user_input)
        if reason:
            continue
        pts = _criterion_points(p, user_input)
        score, weighted, _den = _weighted_and_norm(pts, user_input.get("profil", "STANDARD"))
        breakdown = []
        for key, base, wv in weighted:
            breakdown.append({"key": key, "punkte": int(round(wv))})
        results.append({
            "produktId": p.get("id"),
            "anbieter": p.get("anbieter"),
            "produkt": p.get("produkt"),
            "score": round(float(score)),
            "cluster": _cluster(score),
            "breakdown": breakdown,
            "_raw": p,
        })
    results.sort(key=lambda x: (-x["score"], x.get("anbieter", ""), x.get("produkt", "")))
    return results


def visible_and_ko(products: List[Dict[str, Any]], user_input: Dict[str, Any]):
    visible = []
    ko_map = {}
    for p in products:
        r = ko_reason(p, user_input)
        if r:
            ko_map[p.get("id")] = r
        else:
            visible.append(p.get("id"))
    return visible, ko_map
