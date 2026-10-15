"""Český rybářský svaz – revíry všech územních svazů (Čechy).

Cíl: číslo, název, typ (P/MP), popis hranic, výměra, GPS, hospodařící MO,
bližší podmínky a údaje o zarybnění.

Kandidátní zdroje (ověřit, až bude síťový přístup):
  - www.rybsvaz.cz – celosvazový přehled revírů
  - weby územních svazů a jejich „Soupis revírů“ (PDF), např.
    rybsvaz-ms.cz/katalog-obrazku/clanek-637/Soupis_mimopstruhovych_reviru_2024.pdf
"""
NAZEV = "ČRS"
DRUH = "reviry"


def fetch():
    raise NotImplementedError("Scraper ČRS ještě není napsaný – čeká na ověření struktury webu.")
