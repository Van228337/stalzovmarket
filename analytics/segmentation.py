"""Item segmentation engine for STALCRAFT market.

Segments items based on their operational and pricing characteristics:
1. Artefacts:
   - Rarity (qlt): 0=Обычный, 1=Необычный, 2=Особый, 3=Редкий, 4=Исключительный, 5=Легендарный
   - Upgrade level (ptn): 0..15 (заточка)
   - Quality bonus (upgrade_bonus): % (100%..150%)
   Segment key: "q{qlt}:p{ptn}"
   Segment label: "{rarity} (+{ptn})" (e.g. "Обычный (+0)", "Особый (+10)", "Редкий (+15)")
2. Weapons and Armor:
   - Upgrade level (ptn or upgrade_level): 0..15
   Segment key: "p{ptn}" (or "default" if +0)
   Segment label: "+{ptn}" (or "Базовый" if +0)
3. Weapon Modules (1pyq):
   - Handled via parse_weapon_module if active
4. Standard / Homogenous items (ammo, spare parts, containers, materials):
   Segment key: "default"
   Segment label: "Стандарт"
"""

from typing import Any, Dict, Optional, Tuple

RARITY_NAMES_RU = {
    0: "Обычный",
    1: "Необычный",
    2: "Особый",
    3: "Редкий",
    4: "Исключительный",
    5: "Легендарный",
}

RARITY_NAMES_EN = {
    0: "Common",
    1: "Uncommon",
    2: "Special",
    3: "Rare",
    4: "Exceptional",
    5: "Legendary",
}


def get_item_segment(
    item_id: str,
    item_meta: Optional[Dict[str, Any]] = None,
    additional: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Return (segment_key, human_label) for any item."""
    category = (item_meta.get("category") or "") if item_meta else ""
    add = additional or {}

    # 1. Weapon Module (1pyq)
    if item_id == "1pyq":
        return "1pyq", "Модуль"

    # 2. Artefacts (either category starts with artefact/ or additional has typical artefact keys)
    is_artefact = (
        category.startswith("artefact/")
        or "bonus_properties" in add
        or "it_transf_count" in add
        or ("qlt" in add and "upgrade_bonus" in add)
    )

    if is_artefact:
        qlt = int(add.get("qlt", 0))
        ptn = int(add.get("ptn", 0))

        rarity_name = RARITY_NAMES_RU.get(qlt, f"Ранг {qlt}")
        segment_key = f"q{qlt}:p{ptn}"
        segment_label = f"{rarity_name} (+{ptn})"
        return segment_key, segment_label

    # 3. Weapons & Armor with upgrade level
    ptn = add.get("ptn") or add.get("upgrade_level")
    if ptn is not None:
        try:
            ptn_int = int(ptn)
            if ptn_int > 0:
                return f"p{ptn_int}", f"+{ptn_int}"
        except (ValueError, TypeError):
            pass

    # 4. Standard uniform items
    return "default", "Стандарт"
