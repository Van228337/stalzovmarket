"""Weapon Module ('1pyq') calculation and parsing engine.

Adheres strictly to STALCRAFT API Specification Section 9.
Handles:
- Attribute slot mapping (add-on, deviation, concept)
- Quality band scaling (0..6)
- Potential calculation (scale 0..190, NOT 0..100)
- Stat effect computation: value = min + (max - min) * potential / 190
- Name construction: "<add-on> <deviation> «<concept>»"
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Quality bands for weapon modules (Section 9.4 / 9.7)
BANDS: List[Tuple[float, float]] = [
    (0.0, 18.72),     # 0: Common (Обычный)
    (18.72, 40.25),   # 1: Uncommon (Необычный)
    (40.25, 64.58),   # 2: Special (Особый)
    (64.58, 91.72),   # 3: Rare (Редкий)
    (91.72, 121.67),  # 4: Exceptional (Исключительный)
    (121.67, 154.43), # 5: Legendary (Легендарный)
    (154.43, 190.0),  # 6: Unique (Уникальный)
]

SLOT_NAMES = {
    0: "add-on",     # Надстройка (type is absent)
    1: "deviation",  # Отклонение (type = 1)
    2: "concept",    # Концепт (type = 2)
}

# Known reference definitions from the documentation fixtures (Section 9.6)
BUILTIN_MODULE_DEFS: Dict[str, Dict[str, Any]] = {
    "aiming_speed_modifier_pre": {
        "item_id": "aim_pre",
        "slot": 0,
        "title_ru": "Фокусный",
        "description_ru": "Скорость прицеливания",
        "stats": [
            {"key": "aiming_speed", "name_ru": "Скорость прицеливания", "type": "positive", "min": 1.76, "max": 3.76}
        ]
    },
    "recoil_suf": {
        "item_id": "n4kx",
        "slot": 1,
        "title_ru": "Уходящий",
        "description_ru": "Отдача",
        "stats": [
            # Note: min can be greater than max in game specs
            {"key": "recoil", "name_ru": "Отдача", "type": "negative", "min": 13.087, "max": 3.272}
        ]
    },
    "marksman": {
        "item_id": "mrk",
        "slot": 2,
        "title_ru": "Снайпер",
        "description_ru": "Концепт снайпера",
        "stats": [
            {"key": "damage", "name_ru": "Урон", "type": "positive", "min": 1.3, "max": 2.7}
        ]
    }
}


@dataclass
class ModuleEffect:
    name: str
    value: float


@dataclass
class ModuleRoll:
    slot_id: int
    slot_name: str
    definition_id: str
    title: str
    quality: int
    stats_random: float
    potential: float
    effects: List[ModuleEffect] = field(default_factory=list)


@dataclass
class ParsedWeaponModule:
    title: str
    overall_quality: int
    rolls: List[ModuleRoll]
    segment_key: str


def calculate_potential(quality: int, stats_random: float) -> float:
    """Calculate potential on 0..190 scale from quality band and statsRandom position.

    statsRandom is deviation from band center (0 = center, +/-2 = edges).
    statsRandom can extend below -2 (down to -2.95).
    """
    quality_clamped = max(0, min(quality, len(BANDS) - 1))
    lo, hi = BANDS[quality_clamped]
    center = (lo + hi) / 2.0
    half_width = (hi - lo) / 4.0
    raw_potential = center + half_width * stats_random
    return max(0.0, min(190.0, raw_potential))


def compute_effect_value(min_val: float, max_val: float, potential: float) -> float:
    """Compute exact in-game stat effect value based on potential (0..190).

    Formula: min + (max - min) * potential / 190.0
    Preserves direction when min > max.
    """
    return min_val + (max_val - min_val) * (potential / 190.0)


def parse_weapon_module(
    additional_data: Dict[str, Any],
    module_index: Optional[Dict[str, Dict[str, Any]]] = None
) -> ParsedWeaponModule:
    """Parse a '1pyq' weapon module additional payload into structured roll data and title."""
    index = module_index or BUILTIN_MODULE_DEFS
    overall_qlt = int(additional_data.get("qlt", 0))
    raw_attributes = additional_data.get("attributes", [])

    rolls: List[ModuleRoll] = []
    by_slot: Dict[int, ModuleRoll] = {}

    for attr in raw_attributes:
        # slot: absent -> 0 (add-on), 1 -> deviation, 2 -> concept
        slot_id = int(attr.get("type", 0))
        def_id = str(attr.get("definitionId", "unknown"))
        # quality: absent -> 0 (common)
        qlt = int(attr.get("quality", 0))
        stats_random = float(attr.get("statsRandom", 0.0))

        potential = calculate_potential(qlt, stats_random)

        def_info = index.get(def_id)
        title = def_info.get("title_ru", def_id) if def_info else def_id

        effects: List[ModuleEffect] = []
        if def_info and "stats" in def_info:
            for stat in def_info["stats"]:
                eff_val = compute_effect_value(stat["min"], stat["max"], potential)
                effects.append(ModuleEffect(name=stat["name_ru"], value=eff_val))

        roll = ModuleRoll(
            slot_id=slot_id,
            slot_name=SLOT_NAMES.get(slot_id, "unknown"),
            definition_id=def_id,
            title=title,
            quality=qlt,
            stats_random=stats_random,
            potential=potential,
            effects=effects,
        )
        rolls.append(roll)
        by_slot[slot_id] = roll

    # Construct name: "<add-on> <deviation> «<concept>»"
    add_on = by_slot.get(0)
    dev = by_slot.get(1)
    concept = by_slot.get(2)

    add_on_title = add_on.title if add_on else "???"
    dev_title = dev.title if dev else "???"
    concept_title = f"«{concept.title}»" if concept else "«???»"
    full_title = f"{add_on_title} {dev_title} {concept_title}"

    # Build segment key
    add_on_id = add_on.definition_id if add_on else "_"
    dev_id = dev.definition_id if dev else "_"
    concept_id = concept.definition_id if concept else "_"
    segment_key = f"1pyq:{add_on_id}:{dev_id}:{concept_id}:q{overall_qlt}"

    return ParsedWeaponModule(
        title=full_title,
        overall_quality=overall_qlt,
        rolls=rolls,
        segment_key=segment_key,
    )
