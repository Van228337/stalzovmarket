import pytest
from analytics.modules import (
    calculate_potential,
    compute_effect_value,
    parse_weapon_module,
    BANDS,
)


def test_potential_calculations():
    # Test cases directly from reference guide section 9 & prompt:
    # 1. aiming_speed_modifier_pre (Фокусный): quality=1, statsRandom=-0.89333594 -> ~24.68
    pot_focal = calculate_potential(quality=1, stats_random=-0.89333594)
    assert round(pot_focal, 2) == 24.68

    # 2. recoil_suf (Уходящий): quality=1, statsRandom=-0.45354962 -> ~27.04
    pot_recoil = calculate_potential(quality=1, stats_random=-0.45354962)
    assert round(pot_recoil, 2) == 27.04

    # 3. marksman (Снайпер): quality=0 (missing), statsRandom=-0.8085954 -> ~5.58
    pot_marksman = calculate_potential(quality=0, stats_random=-0.8085954)
    assert round(pot_marksman, 2) == 5.58


def test_effect_values_and_direction():
    # recoil_suf: min=13.087, max=3.272, potential=27.0437 -> ~11.69%
    eff_recoil = compute_effect_value(min_val=13.087, max_val=3.272, potential=27.0437)
    assert round(eff_recoil, 2) == 11.69

    # aiming_speed: min=1.76, max=3.76, potential=24.6766 -> ~2.02%
    eff_aim = compute_effect_value(min_val=1.76, max_val=3.76, potential=24.6766)
    assert round(eff_aim, 2) == 2.02

    # marksman: min=1.3, max=2.7, potential=5.5758 -> ~1.34%
    eff_marksman = compute_effect_value(min_val=1.3, max_val=2.7, potential=5.5758)
    assert round(eff_marksman, 2) == 1.34


def test_parse_weapon_module_full_lot():
    lot_additional = {
        "qlt": 1,
        "attributes": [
            {"type": 1, "statsRandom": -0.45354962, "definitionId": "recoil_suf", "quality": 1},
            {"statsRandom": -0.89333594, "definitionId": "aiming_speed_modifier_pre", "quality": 1},
            {"type": 2, "statsRandom": -0.8085954, "definitionId": "marksman"},
        ],
        "it_transf_count": 1,
    }

    parsed = parse_weapon_module(lot_additional)
    assert parsed.title == "Фокусный Уходящий «Снайпер»"
    assert parsed.overall_quality == 1
    assert parsed.segment_key == "1pyq:aiming_speed_modifier_pre:recoil_suf:marksman:q1"

    effects_by_name = {}
    for roll in parsed.rolls:
        for eff in roll.effects:
            effects_by_name[eff.name] = round(eff.value, 2)

    assert effects_by_name["Скорость прицеливания"] == 2.02
    assert effects_by_name["Отдача"] == 11.69
    assert effects_by_name["Урон"] == 1.34
