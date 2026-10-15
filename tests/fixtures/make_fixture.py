"""Vymyšlená testová data pro ověření UI (nejde o skutečné revíry)."""
import json, sys
from datetime import date, timedelta
from pathlib import Path

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
d = lambda n: (date.today() - timedelta(days=n)).isoformat()
reviry = [
    {"id": "999001", "cislo": "999 001", "nazev": "Testovací řeka 1", "svaz": "TEST", "typ": "mimopstruhovy",
     "tok": "Testovací řeka", "popis": "Fiktivní popis hranic revíru.", "gps": [{"lat": 50.08, "lon": 14.42}, {"lat": 50.10, "lon": 14.45}]},
    {"id": "999002", "cislo": "999 002", "nazev": "Testovací potok 1 P", "svaz": "TEST", "typ": "pstruhovy",
     "tok": "Testovací potok", "gps": [{"lat": 50.2, "lon": 14.6}]},
]
json.dump({"reviry": reviry}, open(out / "reviry.json", "w"), ensure_ascii=False)
json.dump({"vysazeni": {"999001": [{"druh": "kapr", "datum": d(30), "mnozstvi": 500, "jednotka": "kg", "vek": "K3"}]}}, open(out / "vysazeni.json", "w"), ensure_ascii=False)
json.dump({"ulovky": {"999001": [
    {"datum": d(5), "druh": "štika obecná", "delka_cm": 72, "nastraha": "wobler", "zdroj": "test"},
    {"datum": d(9), "druh": "kapr", "delka_cm": 61, "nastraha": "boilies", "zdroj": "test"},
    {"datum": d(12), "druh": "kapr", "delka_cm": 55, "nastraha": "kukuřice", "zdroj": "test"},
    {"datum": d(200), "druh": "candát", "delka_cm": 50, "zdroj": "test"}]}}, open(out / "ulovky.json", "w"), ensure_ascii=False)
json.dump({"stanice": [{"id": "T1", "nazev": "Testov", "tok": "Testovací řeka", "lat": 50.09, "lon": 14.43, "stav_cm": 120, "prutok_m3s": 35.2, "trend": "klesá", "spa": 0}]},
          open(out / "voda.json", "w"), ensure_ascii=False)
json.dump({"generated": date.today().isoformat()}, open(out / "meta.json", "w"))
