# coding: utf-8
import json
import streamlit as st
from typing import List, Dict, Any

from matching import rank_products, visible_and_ko, HIGHLIGHT_LABELS

st.set_page_config(page_title="WEfiMa (MVP)", layout="wide")
st.title("🏢 WEG-FiMa (MVP) V1.0")
st.caption("scoring_v1 · datengetrieben · K.O. vor Scoring · Profile verändern Gewichtungen")

@st.cache_data
def load_products() -> List[Dict[str, Any]]:
    with open("products.json", "r", encoding="utf-8") as f:
        return json.load(f)

products = load_products()

if "compare" not in st.session_state:
    st.session_state.compare = set()

with st.form("eingabe"):
    st.subheader("Eingabe")
    col1, col2, col3 = st.columns(3)
    with col1:
        region = st.selectbox("Region", options=["DE", "BY", "NRW"], index=0)
        laufzeit = st.selectbox("Laufzeit (Jahre)", options=[10, 15], index=0)
    with col2:
        anzahl_we = st.number_input("Wohneinheiten (WE)", min_value=1, step=1, value=12)
        verwendung = st.selectbox("Maßnahme", options=["sanierung", "modernisierung"], index=0)
    with col3:
        gesamtvolumen = st.number_input("Gesamtvolumen (€)", min_value=0, step=1000, value=300000)
        profil = st.radio(
            "Profil",
            options=["STANDARD", "FÖRDERFOKUS", "GROSSE_WEG"],
            index=0,
            horizontal=False,
        )

    submitted = st.form_submit_button("Produkte anzeigen")

if submitted:
    user_input = {
        "region": region,
        "anzahlWE": int(anzahl_we),
        "gesamtvolumen": float(gesamtvolumen),
        "verwendung": verwendung,
        "laufzeit": int(laufzeit),
        "profil": profil,
    }

    st.write(":blue[volumenProET] = ", int(user_input["gesamtvolumen"] / max(1, user_input["anzahlWE"])) , "€")

    results = rank_products(products, user_input)

    clusters = {
        "EMPFOHLEN": [r for r in results if r["cluster"] == "EMPFOHLEN"],
        "GEEIGNET": [r for r in results if r["cluster"] == "GEEIGNET"],
        "EINGESCHRÄNKT": [r for r in results if r["cluster"] == "EINGESCHRÄNKT"],
    }

    def render_card(res):
        p = res["_raw"]
        with st.container(border=True):
            left, mid, right = st.columns([4,2,2])
            with left:
                st.markdown(f"**{res.get('anbieter','')} – {res.get('produkt','')}**")
                st.caption(f"ID: `{res.get('produktId')}`")
            with mid:
                st.metric("Score", f"{int(res['score'])} / 100")
            with right:
                sel = st.checkbox("Vergleichen", key=f"cmp_{res['produktId']}", value=(res['produktId'] in st.session_state.compare))
                if sel:
                    st.session_state.compare.add(res['produktId'])
                else:
                    st.session_state.compare.discard(res['produktId'])

            positives = [b for b in sorted(res["breakdown"], key=lambda x: -x["punkte"]) if b["punkte"] > 0]
            highlights = []
            for b in positives:
                label = HIGHLIGHT_LABELS.get(b["key"], b["key"])
                if label not in highlights:
                    highlights.append(label)
                if len(highlights) >= 3:
                    break
            if highlights:
                st.write("**Highlights:** ", " · ".join([f"– {h}" for h in highlights]))

            with st.expander("Details ▾"):
                st.caption(f"Score-Erklärung (Profil: {profil})")
                for b in res["breakdown"]:
                    key = b["key"]
                    label = HIGHLIGHT_LABELS.get(key, key)
                    chk = "✔" if b["punkte"] > 0 else "–"
                    sign = "+" if b["punkte"] > 0 else ""
                    st.write(f"{chk} {label:<28}  {sign}{b['punkte']}")
                st.markdown("---")
                st.write("**Gesamt:** ", f"{int(res['score'])}")

                if p.get("anforderungen"):
                    st.subheader("Anforderungen")
                    for a in p.get("anforderungen", []):
                        st.write("• ", a)
                if p.get("zusatzinfos"):
                    st.subheader("Zusatzinfos")
                    st.write(p.get("zusatzinfos"))

    for cname in ["EMPFOHLEN", "GEEIGNET", "EINGESCHRÄNKT"]:
        if clusters[cname]:
            st.markdown(f"### {'⭐ ' if cname=='EMPFOHLEN' else ''}{cname}")
            for res in clusters[cname]:
                render_card(res)

    if st.session_state.compare:
        sel_ids = list(st.session_state.compare)[:3]
        st.markdown("### Vergleich (max. 3 Produkte)")
        sel_results = [r for r in results if r["produktId"] in sel_ids]
        if sel_results:
            def yesno(b: bool) -> str:
                return "ja" if b else "nein"
            rows = []
            rows.append(["Score"] + [str(int(r["score"])) for r in sel_results])
            rows.append(["Haftung (pers.)"] + [yesno(r["_raw"].get("persHaftung", False)) for r in sel_results])
            rows.append(["Grundschuld"] + [yesno(r["_raw"].get("grundschuld", False)) for r in sel_results])
            rows.append(["Förderung"] + [yesno(r["_raw"].get("foerderungMoeglich", False)) for r in sel_results])
            rows.append(["Laufzeit"] + [f"{user_input['laufzeit']} J" for _ in sel_results])
            rows.append(["Kosten (Konto)"] + [f"{r['_raw'].get('kontokostenPM','–')} €" for r in sel_results])
            st.table(rows)

    with st.expander("🧪 Testfälle ausführen"):
        u1 = {"region": "DE", "anzahlWE": 12, "gesamtvolumen": 300000, "verwendung": "sanierung", "laufzeit": 10, "profil": "STANDARD"}
        vis1, ko1 = visible_and_ko(products, u1)
        st.write("Fall 1 – sichtbar:", vis1)
        st.write("Fall 1 – KO-Gründe:", ko1)

        u2 = {"region": "DE", "anzahlWE": 6, "gesamtvolumen": 40000, "verwendung": "sanierung", "laufzeit": 10, "profil": "STANDARD"}
        vis2, ko2 = visible_and_ko(products, u2)
        st.write("Fall 2 – sichtbar:", vis2)
        st.write("Fall 2 – KO-Gründe:", ko2)

        u3a = {"region": "DE", "anzahlWE": 12, "gesamtvolumen": 300000, "verwendung": "sanierung", "laufzeit": 10, "profil": "STANDARD"}
        u3b = {**u3a, "profil": "FÖRDERFOKUS"}
        r_std = rank_products(products, u3a)
        r_ff  = rank_products(products, u3b)
        st.write("Fall 3 – Ranking STANDARD:", [ (r['produktId'], r['score']) for r in r_std ])
        st.write("Fall 3 – Ranking FÖRDERFOKUS:", [ (r['produktId'], r['score']) for r in r_ff ])
