import pytest
from collector.items_db import ItemsDatabase


@pytest.mark.asyncio
async def test_items_db_parsing_and_id_extraction():
    db = ItemsDatabase()
    sample_listing = [
        {
            "data": "/items/weapon/submachine_gun/96mj0.json",
            "icon": "/icons/weapon/submachine_gun/96mj0.png",
            "name": {
                "type": "translation",
                "key": "item.wpn.kedr.name",
                "lines": {"ru": "ПП-91 «Кедр»", "en": "PP-91 KEDR"},
            },
            "color": "RANK_NEWBIE",
        },
        {
            "data": "/items/weapon/pistol/0n9q.json",
            "icon": "/icons/weapon/pistol/0n9q.png",
            "name": {
                "lines": {"ru": "Пистолет Макарова", "en": "PM"},
            },
            "color": "RANK_NEWBIE",
        },
    ]

    parsed = db._parse_listing(sample_listing)
    assert len(parsed) == 2
    assert "96mj0" in parsed
    assert parsed["96mj0"]["name_ru"] == "ПП-91 «Кедр»"
    assert parsed["96mj0"]["category"] == "weapon/submachine_gun"
    assert "0n9q" in parsed
    assert parsed["0n9q"]["name_ru"] == "Пистолет Макарова"
