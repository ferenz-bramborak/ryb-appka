"""Zdroje dat. Každý modul vystavuje NAZEV, DRUH a funkci fetch().

DRUH určuje, co fetch() vrací:
  "reviry"   -> (list[Revir], dict[revir_id, list[Vysazeni]])
  "ulovky"   -> (dict[revir_id, list[Ulovek]]) – revir_id je evidenční číslo
  "voda"     -> list[Stanice]
"""
from . import chmi, crs, mrs, ulovky_fora

ALL = [crs, mrs, ulovky_fora, chmi]
