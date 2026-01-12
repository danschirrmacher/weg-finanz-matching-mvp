
# WEG-Finanzierungs-Matching – MVP (scoring_v1)

## Start (lokal)
```bash
pip install streamlit
streamlit run app.py
```

## Projektstruktur
- `app.py` – Streamlit-UI (deutsch)
- `matching.py` – KO-Filter, Scoring-Engine, Ranking
- `products.json` – Produktdaten (Single Source of Truth)

## Testfälle (integriert)
In der App im Abschnitt "🧪 Testfälle ausführen" sichtbar.

## Prinzipien
- Datengetrieben, keine Logik im UI
- KO vor Scoring, KO-Produkte werden nicht gerankt
- Profile ändern nur Gewichtung (STANDARD, FÖRDERFOKUS, GROSSE_WEG)
- Score wird auf 0–100 normiert (scoring_v1)
- Governance: Änderungen nur über Versionierung & Testfälle
