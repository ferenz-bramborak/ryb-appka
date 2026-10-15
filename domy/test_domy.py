import unittest

from domy.spolecne import cislo, dispozice_z_textu, typ_z_textu, poloha_z_textu, stavba_z_textu
from domy.run import _podobne, duvod_vyrazeni, sluc


class Prevody(unittest.TestCase):
    def test_cislo(self):
        self.assertEqual(cislo("11‍\xa0990‍\xa0000‍\xa0Kč"), 11_990_000)
        self.assertEqual(cislo("95,8 m 2"), 96)
        self.assertIsNone(cislo("Info v RK"))

    def test_dispozice(self):
        self.assertEqual(dispozice_z_textu("Prodej domu 4+kk, v podkroví další 2+1"), ("4+kk", 4))
        self.assertEqual(dispozice_z_textu("bez dispozice"), ("", None))

    def test_text(self):
        self.assertEqual(typ_z_textu("Krásný bungalov 5+kk"), "bungalov")
        self.assertEqual(poloha_z_textu("Prodej řadového domu"), "řadový")
        self.assertEqual(stavba_z_textu("moderní dřevostavba"), "dřevostavba")


def zaznam(**kw):
    base = dict(zdroj="Sreality", obec="Rosice", lat=49.18, lon=16.39, cena=10_000_000, uzitna=150,
                pozemek=800, pokoje=5, poloha="", prvni="2026-10-01", posledni="2026-10-01")
    base.update(kw)
    return base


class Filtry(unittest.TestCase):
    def test_vyrazeni(self):
        self.assertIsNone(duvod_vyrazeni(zaznam()))
        self.assertEqual(duvod_vyrazeni(zaznam(poloha="řadový")), "řadový")
        self.assertEqual(duvod_vyrazeni(zaznam(pokoje=3)), "pokoje")
        self.assertEqual(duvod_vyrazeni(zaznam(cena=16_000_000)), "cena")
        self.assertEqual(duvod_vyrazeni(zaznam(lat=50.08, lon=14.42)), "daleko")
        self.assertIsNone(duvod_vyrazeni(zaznam(pokoje=None)))

    def test_duplicity(self):
        a = zaznam()
        b = zaznam(zdroj="iDNES Reality", cena=10_100_000, lat=49.1805, lon=16.3902)
        c = zaznam(zdroj="Reas", pozemek=500, uzitna=100, cena=7_000_000)
        self.assertTrue(_podobne(a, b))
        self.assertFalse(_podobne(a, c))
        z = {"sr-1": a, "id-1": b, "re-1": c}
        sk = sluc(z)
        self.assertEqual(sorted(len(v) for v in sk.values()), [1, 2])
        self.assertEqual(z["id-1"]["dum"], z["sr-1"]["dum"])


if __name__ == "__main__":
    unittest.main()
