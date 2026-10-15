"""Kritéria hledání a místa, ke kterým se počítá dojezd.

Tvrdá kritéria (co nesplní, do aplikace vůbec nepřijde) jsou tady.
Měkká kritéria (váhy skóre) se nastavují přímo v aplikaci.
"""

MAX_CENA = 15_000_000
MIN_POKOJE = 4               # dispozice 4+kk a víc; neznámý počet pokojů se nevyřazuje
MIN_POZEMEK = 250            # m²; zahrada pro psy a děti
MAX_VZDUSNE_KM = 35          # od těžiště rodiny (Rosice–Střelice–Oslavany)
VYRADIT_RADOVE = True        # „nechceme řadovky“ (vč. krajních řadových)

RODINA = [
    # (klíč, popisek, lat, lon)
    ("rosice", "Brácha – Rosice", 49.1823, 16.3878),
    ("strelice", "Děda – Střelice", 49.1525, 16.4995),
    ("padochov", "Rodiče – Padochov", 49.1366, 16.3478),
]
HRANICE = ("hranice", "Hranice na Moravě", 49.5478, 17.7346)
BRNO_CENTRUM = ("brno", "Brno – centrum", 49.1951, 16.6068)

# Exity D1 v okolí Brna (orientační souřadnice nájezdů)
D1_EXITY = [
    ("162 Velká Bíteš", 49.2875, 16.2296),
    ("168 Devět křížů", 49.2573, 16.3004),
    ("178 Ostrovačice", 49.2093, 16.4140),
    ("182 Kývalka", 49.1953, 16.4517),
    ("190 Brno-západ", 49.1797, 16.5508),
    ("194 Brno-centrum", 49.1692, 16.5856),
    ("196 Brno-jih", 49.1603, 16.6266),
    ("201 Brno-Slatina", 49.1666, 16.6914),
    ("203 Brno-východ", 49.1762, 16.7210),
    ("210 Holubice", 49.1967, 16.8123),
]

# Oblast mapy lesů a reliéfu (musí pokrýt MAX_VZDUSNE_KM kolem rodiny)
GEO_BBOX = (49.00, 15.95, 49.45, 17.00)  # lat_min, lon_min, lat_max, lon_max

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
