SHOP_ITEMS = {
    "potion_s": {"name": "经验药水(小)", "gold_price": 500, "daily_limit": 10},
    "potion_m": {"name": "经验药水(中)", "gold_price": 4000, "daily_limit": 3},
    "potion_l": {"name": "经验药水(大)", "gold_price": 30000, "daily_limit": 1},
    "energy_potion": {"name": "行动力药水", "gold_price": 2000, "daily_limit": 3},
}

DIAMOND_ITEMS = {
    "potion_l": {"name": "经验药水(大)", "diamond_price": 5, "daily_limit": 2},
    "energy_potion": {"name": "行动力药水", "diamond_price": 3, "daily_limit": 5},
}

USE_ITEMS = {
    "potion_s": {"name": "经验药水(小)", "exp": 100, "daily_limit": 20},
    "potion_m": {"name": "经验药水(中)", "exp": 1000, "daily_limit": 10},
    "potion_l": {"name": "经验药水(大)", "exp": 10000, "daily_limit": 5},
    "energy_potion": {"name": "行动力药水", "energy": 30, "daily_limit": 5},
}

ITEM_ALIASES = {
    "经验药水小": "potion_s",
    "经验药水中": "potion_m",
    "经验药水大": "potion_l",
    "行动力药水": "energy_potion",
    "经验药水(小)": "potion_s",
    "经验药水(中)": "potion_m",
    "经验药水(大)": "potion_l",
}


def resolve_item_id(name: str) -> str | None:
    if name in SHOP_ITEMS or name in USE_ITEMS:
        return name
    return ITEM_ALIASES.get(name)
