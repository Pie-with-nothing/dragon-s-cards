import json
from random import randint as rd, random, choices, choice, Random
import math
import numpy as np
from engine import Player

from faker import Faker
from marmel_grammar import MarmelGrammar


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

# ==================== Single character (player) ====================

def player_to_dict(p: Player) -> dict:
    return {
        "name": p.name,
        "dice_pull": p.dice_pull,
        "modif": p.modif,
        "reroll": p.reroll,
        "advantage": p.advantage,
        "is_human": p.is_human,
    }


def dict_to_player(d) -> Player:
    if not isinstance(d, dict):
        raise ValueError("ожидался JSON-объект с полями персонажа")

    required = ("name", "dice_pull", "modif", "reroll", "advantage", "is_human")
    missing = [k for k in required if k not in d]
    if missing:
        raise ValueError("отсутствуют поля: " + ", ".join(missing))

    raw_name = d["name"]
    name = str(raw_name).strip() if raw_name is not None else ""
    if not name:
        raise ValueError("поле 'name' пустое")

    try:
        dice_pull = int(d["dice_pull"])
        modif = int(d["modif"])
        reroll = int(d["reroll"])
    except (TypeError, ValueError):
        raise ValueError("dice_pull / modif / reroll должны быть целыми")

    if not isinstance(d["advantage"], bool):
        raise ValueError("поле 'advantage' должно быть true или false")
    if not isinstance(d["is_human"], bool):
        raise ValueError("поле 'is_human' должно быть true или false")

    if dice_pull < 1:
        raise ValueError("dice_pull должен быть ≥ 1")
    if reroll < 0 or reroll > 2:
        raise ValueError("reroll должен быть от 0 до 2")

    return Player(name, dice_pull, modif, reroll,
                  d["advantage"], is_human=d["is_human"])


def player_to_json_str(p: Player) -> str:
    return json.dumps(player_to_dict(p), ensure_ascii=False, indent=2)


def player_from_json_str(raw: str) -> Player:
    return dict_to_player(json.loads(raw))


def safe_filename(name: str, fallback: str = "character") -> str:
    bad = '/\\:*?"<>|'
    cleaned = "".join("_" if c in bad else c for c in name).strip()
    return (cleaned or fallback) + ".json"


def download_player_json(p: Player, filename: str):
    from js import Blob, URL, document

    if not filename.lower().endswith(".json"):
        filename += ".json"

    content = player_to_json_str(p)
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


def _gen_faker():
    locales = [
        "am_ET", "ar_AE", "ar_BH", "ar_EG",
        "ar_JO", "bg_BG", "bs_BA", "de_LU",
        "dk_DK", "el_CY", "en", "en_AU",
        "en_BD", "en_CA", "en_GB", "en_IE",
        "en_IN", "en_KE", "en_MS", "en_NG",
        "en_NZ", "en_PH", "en_PK", "en_TH",
        "en_US", "es_AR", "es_VE", "fil_PH",
        "fr_DZ", "ha_NG", "id_ID", "ig_NG", 
        "it_CH", "it_IT", "la", "lb_LU", 
        "mt_MT", "ng_NG", 
        "ru_RU", "sq_AL", "sr_BA", "sw",
        "tl_PH", "tw_GH", "uz_UZ", "yo_NG",
        "zu_ZA"
    ]

    trash = [
        'prof', 'dr', 'md', 'mr', 'ms', 'mrs', 'г-жа', 'г-н', 'pol', 'const',
        'kh', 'г-ца', 'др', 'hr', 'ii', 'iii', 'dds', 'fr', 'wg', 'cd', 'dvm',
        'phd', 'rev', 'sis', 'eng', 'pastor', 'cdr', 'maj', 'col', 'lt', 'acm',
        'sen', 'sgt', 'lac', 'adm', 'pfk', 'sub', 'fs', 'cpl', 'phrapalad', 'palad',
        'phrakhu', 'l/c', 'jg', 'gen', 'cpo', 'capt', 'amn', 'phrabaidika', 'sea-man',
        'pfc', 'sqn', 'ldr', 'off', 'flt', 'pvt', 'gp', 'plt', 'am', 'po', 'flg', 'miss'
    ]

    gram = MarmelGrammar()
    raw_name = Faker([choice(locales)]).name()

    name = [s for s in raw_name.split() if "." not in s]
    name = [s for s in name if len(s) > 1 and s.lower() not in trash]

    trans = []
    for i in name:
        char = ""
        if '-' in i and "'" in i or "’" in i:
            char = "’" if "’" in i else "'"
            batch = []
            for bth in [ap.split(char) for ap in i.split('-')]:
                if len(bth) == 1:
                    batch.append(gram.transliterate_to_russian(bth[0]))
                else:
                    batch.append("'".join([gram.transliterate_to_russian(s) for s in bth]))
            trans.append('-'.join(batch))
        elif '-' in i:
            trans.append('-'.join([gram.transliterate_to_russian(b) for b in i.split('-')]))
        elif "'" in i or "’" in i:
            char = "’" if "’" in i else "'"
            trans.append("'".join([gram.transliterate_to_russian(b) for b in i.split(char)]))
        else:
            trans.append(gram.transliterate_to_russian(i))
        
    return " ".join(trans)

def gen_name():
    return _gen_faker()


def generate_npc(config: dict, name: str | None = None) -> Player:
    dice = max(1, _rand_int_dist(config["dice_min"], config["dice_max"], config["distribution"]))
    modif = _rand_int_dist(config["modif_min"], config["modif_max"], config["distribution"])
    reroll = _rand_int_dist(config["reroll_min"], config["reroll_max"], config["distribution"])
    reroll = max(0, min(2, reroll))
    advantage = random() * 100 < config["adv_chance"]
    if name is None:
        name = gen_name()
    return Player(name, dice, modif, reroll, advantage, is_human=False)