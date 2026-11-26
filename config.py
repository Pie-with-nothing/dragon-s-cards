import json
from random import randint as rd, random, choices, choice, Random
import math
import numpy as np
from engine import Player


CONFIG_DEFAULTS = {
    "dice_min": 1, "dice_max": 3,
    "modif_min": -1, "modif_max": 2,
    "reroll_min": 0, "reroll_max": 2,
    "adv_chance": 30,
    "distribution": "uniform"
}

# ==================== Serialize ====================

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
        if cfg["distribution"] not in ("uniform", "logit_normal"):
            cfg["distribution"] = "uniform"
    except (TypeError, ValueError):
        return dict(CONFIG_DEFAULTS)
    return cfg


def to_json_str(cfg: dict) -> str:
    return json.dumps(normalize(cfg), ensure_ascii=False, indent=2)


def from_json_str(raw: str) -> dict:
    return normalize(json.loads(raw))


# ==================== Download (browser) ====================

def download_json(cfg: dict, filename: str):
    """Инициирует скачивание файла в браузере. Только для PyScript."""
    from js import Blob, URL, document

    if not filename.lower().endswith(".json"):
        filename += ".json"

    content = to_json_str(cfg)
    blob = Blob.new([content], {"type": "application/json"})
    url = URL.createObjectURL(blob)

    a = document.createElement("a")
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)


# ==================== Generation ====================
def _sigmoid(z: float) -> float:
    """Численно устойчивая сигмоида: 1 / (1 + exp(-z))."""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)          # z < 0, значит exp(z) ∈ (0, 1] — без переполнения
    return e / (1.0 + e)


def generate_logit_normal(min_val: float, max_val: float,
                          n: int = 10000,
                          mu: float = -2.5,
                          sigma: float = 1.5) -> list[float]:
    """
    mu < 0         — масса у нижней границы (много слабых)
    sigma большая  — более тяжёлый хвост к верхней границе
    """
    rng = Random()  # локальный ГПСЧ; можно передать seed=rng для воспроизводимости
    span = max_val - min_val
    return [
        min_val + span * _sigmoid(rng.gauss(mu, sigma))
        for _ in range(n)
    ]

def np_generate_logit_normal(min_val, max_val):
    """
    mu < 0     — масса у нижней границы (много слабых)
    sigma большая — более тяжёлый хвост к верхней границе
    """
    z = np.random.normal(-2.5, 1.5, 10000)
    u = 1.0 / (1.0 + np.exp(-z))               # сигмоида → (0, 1)
    return min_val + (max_val - min_val) * u

def _rand_int_dist(lo: int, hi: int, distribution: str) -> int:
    if lo > hi:
        lo, hi = hi, lo
    if distribution == "uniform":
        return rd(lo, hi)
    if distribution == "logit_normal":
        #return round(choice(generate_logit_normal(lo, hi)))
        return round(np.random.choice(np_generate_logit_normal(lo, hi)))


def generate_npc(config: dict, name: str | None = None) -> Player:
    dice = max(1, _rand_int_dist(config["dice_min"], config["dice_max"], config["distribution"]))
    modif = _rand_int_dist(config["modif_min"], config["modif_max"], config["distribution"])
    reroll = _rand_int_dist(config["reroll_min"], config["reroll_max"], config["distribution"])
    reroll = max(0, min(2, reroll))
    advantage = random() * 100 < config["adv_chance"]
    if name is None:
        name = "".join(choices("qwertyuiopasdfghjklzxcvbnm", k=rd(3, 6)))
    return Player(name, dice, modif, reroll, advantage, is_human=False)