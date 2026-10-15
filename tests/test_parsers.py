"""Testy parserů na ukázkách skutečných textů ze zdrojových webů."""
from scraper.build import Parovac
from scraper.geo import tok_z_nazvu
from scraper.sources.crs import gps_z_popisu
from scraper.sources.ulovky_fora import _ulovky_ze_zapisu, druhy_v_textu
from scraper.sources.vysazeni import _rozpis


def test_druhy_v_textu():
    assert druhy_v_textu("Se štikama to dnes neklaplo, ale tenhle fešák") == ["štika"]
    assert druhy_v_textu("Lov na method Federer kapři kolem 50.cm") == ["kapr"]
    assert druhy_v_textu("Kaprařina na Labi") == []
    assert druhy_v_textu("povedlo se několik tloušťů a okoun") == ["jelec tloušť", "okoun"]
    assert druhy_v_textu("líni brali ráno") == ["lín"]
    assert druhy_v_textu("linie břehu") == []
    assert druhy_v_textu("750 kg tržního Pstruha duhového a 300 kg Sivena") == ["pstruh duhový", "siven"]


def test_zapis_mrk_strukturovana_pole():
    u = _ulovky_ze_zapisu("2026-10-02", "Dyje 15", "103 cm krokodýl štika potěšil. způsob:  přívlač nej. nástraha:  Guma",
                          "https://x", "mrk.cz")
    assert len(u) == 1
    assert u[0]["druh"] == "štika" and u[0]["delka_cm"] == 103
    assert u[0]["nastraha"] == "guma" and u[0]["metoda"] == "přívlač"


def test_gps_z_popisu():
    pts = gps_z_popisu('GPS Z: 49°25‘56.3“N, 17°20‘08.8“E, K: 49°26‘57.105“N, 17°26‘17.462“E')
    assert len(pts) == 2
    assert abs(pts[0]["lat"] - 49.43231) < 1e-4 and abs(pts[0]["lon"] - 17.33578) < 1e-4


def test_tok_z_nazvu():
    assert tok_z_nazvu("BEČVA 2 A") == "Bečva"
    assert tok_z_nazvu("LABE 9") == "Labe"
    assert tok_z_nazvu("TRNÁVKA 1 P") == "Trnávka"


def test_rozpis_vysazeni_vcus():
    p = ("<strong>Kapr tržní 7800 kg od 1,6 až 2,8 kg </strong>- ÚN Rozkoš <strong>1600 kg</strong>, "
         "MO Přelouč <strong>3600 kg</strong>, MO Hradec Králové <strong>1000 kg,</strong>")
    r = _rozpis(p)
    assert [x.get("mo") or x.get("revir_text") for x in r] == ["Rozkoš", "Přelouč", "Hradec Králové"]
    assert r[1]["mnozstvi"] == 3600 and r[1]["jednotka"] == "kg" and r[1]["kategorie"] == "tržní"
    r = _rozpis("<strong>Kapr tržní 4950 kg</strong>&nbsp;– MO Jaroměř&nbsp;<strong>600 kg</strong>, "
                "ÚN Rozkoš<strong>&nbsp;1350 kg, MO&nbsp;</strong>Hradec Králové&nbsp;<strong>1400 kg</strong>")
    assert [(x.get("mo") or x.get("revir_text"), x["mnozstvi"]) for x in r] == [
        ("Jaroměř", 600), ("Rozkoš", 1350), ("Hradec Králové", 1400)]
    r = _rozpis("<strong>Amur tržní 400 kg á 2,2 kg </strong>- MO Hradec Králové")
    assert r == [{"druh": "amur", "kategorie": "tržní", "popis": "Amur tržní 400 kg á 2,2 kg", "mnozstvi": 400.0,
                  "jednotka": "kg", "mo": "Hradec Králové"}]


def test_parovani_nazvu():
    reviry = [
        {"id": "431038", "nazev": "OHŘE 17", "svaz": "ČRS – Západočeský ÚS", "mo": "Kynšperk nad Ohří"},
        {"id": "431100", "nazev": "OHŘE 17/R", "svaz": "ČRS – Západočeský ÚS", "mo": "Kynšperk nad Ohří"},
        {"id": "441169", "nazev": "RYBNÍČEK", "svaz": "ČRS – Severočeský ÚS"},
        {"id": "451200", "nazev": "ÚDOLNÍ NÁDRŽ ROZKOŠ", "svaz": "ČRS – Východočeský ÚS"},
    ]
    p = Parovac(reviry)
    assert p.podle_textu("Ohře 17") == ["431038"]
    assert p.podle_textu("Rybníček") == []          # obecné slovo, ne název revíru
    assert p.podle_textu("Ohře") == []
    assert p.podle_textu("Do ÚN Rozkoš bylo vysazeno", "ČRS – Východočeský ÚS", cely_text=True) == ["451200"]
    assert p.podle_mo("ČRS – Západočeský ÚS", "Kynšperk nad Ohří") == ["431038", "431100"]


def test_text_zpravy():
    from datetime import date
    from scraper.text import parse_date, typ_zpravy, vysazeni_z_textu
    assert parse_date("Wed, 16 Sep 2026 12:00:16 +0100") == date(2026, 9, 16)
    assert parse_date("15. 9. 2026") == date(2026, 9, 15)
    assert parse_date("10. října 2026") == date(2026, 10, 10)
    assert typ_zpravy("Na Trnávku vysazeni pstruzi duhoví") == "vysazeni"
    assert typ_zpravy("Zákaz rybolovu – Malše 1") == "zakaz"
    assert typ_zpravy("Úhyn ryb v řece Moravě") == "uhyn"
    assert typ_zpravy("Zkoušky pro získání rybářského lístku") == "info"
    v = vysazeni_z_textu("Do revíru bylo vysazeno 500 kg kapra. Dále 2 000 ks štiky.")
    assert v == [{"druh": "kapr", "mnozstvi": 500.0, "jednotka": "kg"}, {"druh": "štika", "mnozstvi": 2000.0, "jednotka": "ks"}]
