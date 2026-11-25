import json
from random import randint as rd, random, gauss, choices

from engine import Player


CONFIG_DEFAULTS = {
    "dice_min": 1, "dice_max": 3,
    "modif_min": -1, "modif_max": 2,
    "reroll_min": 0, "reroll_max": 2,
    "adv_chance": 30,
    "distribution": "uniform",
    "save_path": "default",
}

CURRENT_KEY = "dragon_config_current"
NAMED_PREFIX = "dragon_config_"


# ==================== Storage ====================

class BrowserStore:
    """Обёртка над localStorage. Импортирует js только при инстансе."""
    def __init__(self):
        from js import localStorage
        self._ls = localStorage

    def get(self, key):
        v = self._ls.getItem(key)
        return None if v is None else str(v)

    def set(self, key, value):
        self._ls.setItem(key, value)


class DictStore:
    """In-memory store — для тестов и консоли."""
    def __init__(self, initial=None):
        self.data = dict(initial or {})

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value


def make_browser_store():
    """Вернёт BrowserStore или None, если localStorage недоступен."""
    try:
        return BrowserStore()
    except Exception:
        return None


# ==================== Load / save ====================

def normalize(data: dict) -> dict:
    """Сливает с дефолтами и клампит значения в допустимые диапазоны."""
    cfg = {**CONFIG_DEFAULTS, **(data or {})}
    try:
        cfg["dice_min"] = max(1, int(cfg["dice_min"]))
        cfg["dice_max"] = max(cfg["dice_min"], int(cfg["dice_max"]))
        cfg["modif_min"] = int(cfg["modif_min"])
        cfg["modif_max"] = max(cfg["modif_min"], int(cfg["modif_max"]))
        cfg["reroll_min"] = max(0, min(2, int(cfg["reroll_min"])))
        cfg["reroll_max"] = max(cfg["reroll_min"], min(2, int(cfg["reroll_max"])))
        cfg["adv_chance"] = max(0, min(100, int(cfg["adv_chance"])))
        if cfg["distribution"] not in ("uniform", "normal"):
            cfg["distribution"] = "uniform"
        cfg["save_path"] = str(cfg["save_path"]).strip() or "default"
    except (TypeError, ValueError):
        return dict(CONFIG_DEFAULTS)
    return cfg


def load_current(store) -> dict:
    if store is None:
        return dict(CONFIG_DEFAULTS)
    raw = store.get(CURRENT_KEY)
    if not raw:
        return dict(CONFIG_DEFAULTS)
    try:
        return normalize(json.loads(raw))
    except Exception:
        return dict(CONFIG_DEFAULTS)


def save_current(store, cfg: dict):
    if store is None:
        return
    store.set(CURRENT_KEY, json.dumps(cfg, ensure_ascii=False))


def load_named(store, path: str) -> dict | None:
    if store is None:
        return None
    raw = store.get(NAMED_PREFIX + path)
    if not raw:
        return None
    try:
        return normalize(json.loads(raw))
    except Exception:
        return None


def save_named(store, path: str, cfg: dict):
    if store is None:
        return
    store.set(NAMED_PREFIX + path, json.dumps(cfg, ensure_ascii=False))


# ==================== Generation ====================

def _rand_int_dist(lo: int, hi: int, distribution: str) -> int:
    if lo > hi:
        lo, hi = hi, lo
    if distribution == "uniform":
        return rd(lo, hi)
    # нормальное: центр диапазона, sd = четверть ширины
    mid = (lo + hi) / 2
    sd = (hi - lo) / 4 if hi > lo else 0.5
    v = round(gauss(mid, sd))
    return max(lo, min(hi, v))


def generate_npc(config: dict, name: str | None = None) -> Player:
    dice = max(1, _rand_int_dist(config["dice_min"], config["dice_max"], config["distribution"]))
    modif = _rand_int_dist(config["modif_min"], config["modif_max"], config["distribution"])
    reroll = _rand_int_dist(config["reroll_min"], config["reroll_max"], config["distribution"])
    reroll = max(0, min(2, reroll))
    advantage = random() * 100 < config["adv_chance"]
    if name is None:
        name = "".join(choices("qwertyuiopasdfghjklzxcvbnm", k=rd(3, 6)))
    return Player(name, dice, modif, reroll, advantage, is_human=False)