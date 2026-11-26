from pyscript import when
from pyscript.web import page, div, li, button

from config import (
    generate_npc, normalize, CONFIG_DEFAULTS,
    download_json, from_json_str
    )

from engine import TournamentSM, Player



setup_players: list[Player] = []
sm: TournamentSM | None = None

config = dict(CONFIG_DEFAULTS)

CONFIG_NUMBER_FIELDS = (
    "cfg-dice-min", "cfg-dice-max",
    "cfg-modif-min", "cfg-modif-max",
    "cfg-reroll-min", "cfg-reroll-max",
    "cfg-adv-chance",
)
PLAYER_NUMBER_FIELDS = ("inp-dice", "inp-modif", "inp-reroll")

def notify(message: str, kind: str = "error"):
    """Показывает тост вверху экрана. Клик по тосту — скрыть."""
    toast = page["toast"]._dom_element
    toast.classList.remove("hidden", "toast-error", "toast-warn", "toast-info")
    toast.classList.add(f"toast-{kind}")
    toast.textContent = message


def hide_toast():
    page["toast"]._dom_element.classList.add("hidden")


def mark_invalid(field_id: str):
    page[field_id]._dom_element.classList.add("invalid")


def clear_invalid(*field_ids):
    for fid in field_ids:
        page[fid]._dom_element.classList.remove("invalid")


@when("click", "#toast")
def on_toast_click(event):
    hide_toast()


@when("input", "body")
def on_any_input(event):
    # Любой ввод снимает подсветку с этого поля — пользователь начал исправлять
    try:
        event.target.classList.remove("invalid")
    except Exception:
        pass
    
def _read_config_from_dom() -> dict:
    return {
        "dice_min": int(page["cfg-dice-min"].value),
        "dice_max": int(page["cfg-dice-max"].value),
        "modif_min": int(page["cfg-modif-min"].value),
        "modif_max": int(page["cfg-modif-max"].value),
        "reroll_min": int(page["cfg-reroll-min"].value),
        "reroll_max": int(page["cfg-reroll-max"].value),
        "adv_chance": int(page["cfg-adv-chance"].value),
        "distribution": "logit_normal" if page["cfg-dist-normal"]._dom_element.checked else "uniform",
    }


def _write_config_to_dom(cfg: dict):
    page["cfg-dice-min"].value = cfg["dice_min"]
    page["cfg-dice-max"].value = cfg["dice_max"]
    page["cfg-modif-min"].value = cfg["modif_min"]
    page["cfg-modif-max"].value = cfg["modif_max"]
    page["cfg-reroll-min"].value = cfg["reroll_min"]
    page["cfg-reroll-max"].value = cfg["reroll_max"]
    page["cfg-adv-chance"].value = cfg["adv_chance"]
    if cfg["distribution"] == "logit_normal":
        page["cfg-dist-normal"]._dom_element.checked = True
    else:
        page["cfg-dist-uniform"]._dom_element.checked = True


def show_config_modal(visible: bool):
    el = page["config-modal"]
    if visible:
        _write_config_to_dom(config)
        el.classes.remove("hidden")
    else:
        el.classes.add("hidden")


@when("click", "#btn-open-config")
def on_open_config(event):
    clear_invalid(*CONFIG_NUMBER_FIELDS)
    hide_toast()
    show_config_modal(True)


@when("click", "#btn-config-cancel")
def on_config_cancel(event):
    show_config_modal(False)


@when("click", "#btn-config-save")
def on_config_save(event):
    global config

    try:
        cfg = _read_config_from_dom()
    except ValueError:
        for fid in CONFIG_NUMBER_FIELDS:
            raw = page[fid].value.strip()
            if not raw or not raw.lstrip("-").isdigit():
                mark_invalid(fid)
        notify("Все числовые поля должны быть целыми числами", "error")
        return

    errors = []
    if cfg["dice_min"] < 1:
        errors.append(("cfg-dice-min", "Минимум кубов должен быть ≥ 1"))
    if cfg["dice_max"] < 1:
        errors.append(("cfg-dice-max", "Максимум кубов должен быть ≥ 1"))
    if cfg["dice_max"] < cfg["dice_min"]:
        errors.append(("cfg-dice-max", "Максимум кубов не может быть меньше минимума"))
    if cfg["modif_max"] < cfg["modif_min"]:
        errors.append(("cfg-modif-max", "Максимум модификатора не может быть меньше минимума"))
    if cfg["reroll_min"] < 0:
        errors.append(("cfg-reroll-min", "Минимум рероллов не может быть < 0"))
    if cfg["reroll_max"] > 2:
        errors.append(("cfg-reroll-max", "Максимум рероллов не может быть > 2"))
    if cfg["reroll_max"] < cfg["reroll_min"]:
        errors.append(("cfg-reroll-max", "Максимум рероллов не может быть меньше минимума"))
    if cfg["adv_chance"] < 0 or cfg["adv_chance"] > 100:
        errors.append(("cfg-adv-chance", "Шанс преимущества должен быть 0–100%"))

    if errors:
        for fid, _ in errors:
            mark_invalid(fid)
        first_msg = errors[0][1]
        if len(errors) > 1:
            notify(f"{first_msg} (и ещё {len(errors) - 1})", "error")
        else:
            notify(first_msg, "error")
        return

    config = normalize(cfg)
    filename = page["cfg-filename"].value.strip() or "dragon_config.json"
    download_json(config, filename)
    hide_toast()
    show_config_modal(False)


@when("click", "#btn-config-load")
def on_config_load_click(event):
    # Программный клик по скрытому <input type="file"> — открывает диалог выбора
    page["cfg-file-input"]._dom_element.click()


@when("change", "#cfg-file-input")
async def on_file_selected(event):
    global config
    input_el = page["cfg-file-input"]._dom_element
    files = input_el.files
    if files.length == 0:
        return
    file = files.item(0)
    try:
        text = await file.text()
        config = from_json_str(str(text))
        _write_config_to_dom(config)
    except Exception as e:
        page["cfg-filename"].value = f"Ошибка: {e}"
    finally:
        input_el.value = ""   # позволяет выбрать тот же файл повторно

# ==================== Setup ====================

def render_setup():
    pl = page["player-list"]
    pl.innerHTML = ""
    for idx, p in enumerate(setup_players):
        item = li()
        item.innerText = p.full_info()
        rm = button("✕", classes=["player-remove"])
        rm.dataset.idx = str(idx)         # dataset доступен на обёртке
        item.append(rm)
        pl.append(item)
    page["btn-start-tournament"].disabled = len(setup_players) < 2


@when("click", "#btn-add-player")
def on_add_player(event):
    name = page["inp-name"].value.strip() or f"Player{len(setup_players) + 1}"

    try:
        dice   = int(page["inp-dice"].value)
        modif  = int(page["inp-modif"].value)
        reroll = int(page["inp-reroll"].value)
    except ValueError:
        for fid in PLAYER_NUMBER_FIELDS:
            raw = page[fid].value.strip()
            if not raw or not raw.lstrip("-").isdigit():
                mark_invalid(fid)
        notify("Кубы, модификатор и рероллы должны быть числами", "error")
        return

    err = []
    if dice < 1:
        err.append(("inp-dice", "Количество кубов должно быть ≥ 1"))
    if reroll < 0 or reroll > 2:
        err.append(("inp-reroll", "Рероллы: от 0 до 2"))

    if err:
        for fid, _ in err:
            mark_invalid(fid)
        first_msg = err[0][1]
        if len(err) > 1:
            notify(f"{first_msg} (и ещё {len(err) - 1})", "error")
        else:
            notify(first_msg, "error")
        return

    advantage = page["inp-adv"].checked
    is_human  = page["inp-human"].checked

    try:
        pl = Player(name, dice, modif, reroll, advantage, is_human=is_human)
    except ValueError as e:
        notify(f"Ошибка: {e}", "error")
        return

    setup_players.append(pl)
    page["inp-name"].value = ""
    clear_invalid(*PLAYER_NUMBER_FIELDS)
    hide_toast()
    render_setup()


@when("click", "#btn-clear-players")
def on_clear(event):
    setup_players.clear()
    render_setup()


@when("click", "#player-list")
def on_player_list_click(event):
    # Делегирование: слушаем родителя, ловим клики по кнопкам ✕
    tgt = event.target
    if "player-remove" in tgt.className.split():
        setup_players.pop(int(tgt.dataset.idx))
        render_setup()

@when("click", "#btn-generate-npc")
def on_generate_npc(event):
    npc = generate_npc(config)
    
    page["inp-name"].value = npc.name
    page["inp-dice"].value = npc.dice_pull
    page["inp-modif"].value = npc.modif
    page["inp-reroll"].value = npc.reroll
    page["inp-adv"].checked = npc.advantage
    page["inp-human"].checked = npc.is_human
    
    render_setup()

@when("click", "#btn-start-tournament")
def on_start(event):
    global sm
    if len(setup_players) < 2:
        return
    show("panel-setup", False)
    sm = TournamentSM(list(setup_players))   # копия — чтобы форма не влияла на турнир
    sm.start_round()
    render_tournament()


# ==================== Tournament ====================

def show(id_, visible):
    el = page[id_]
    if visible: el.classes.remove("hidden")
    else:       el.classes.add("hidden")


def render_tournament():
    if sm is None:
        return

    show("panel-pc-roll",    sm.state == TournamentSM.WAITING_PC_ROLL)
    show("panel-reroll",     sm.state == TournamentSM.WAITING_REROLL)
    show("panel-round-done", sm.state in (TournamentSM.ROUND_COMPLETE,
                                           TournamentSM.TOURNAMENT_DONE))

    if sm.state == TournamentSM.WAITING_PC_ROLL:
        page["pc-roll-prompt"].innerText = sm.prompt
    elif sm.state == TournamentSM.WAITING_REROLL:
        page["reroll-prompt"].innerText = sm.prompt
    else:
        page["round-done-prompt"].innerText = sm.prompt

    page["btn-next-round"].disabled = sm.state == TournamentSM.TOURNAMENT_DONE

    lb = page["leaderboard"]
    lb.innerHTML = ""
    for p in sm.leaderboard:
        item = li()
        item.innerText = f"{p.full_info()}: {sm.tour.scores[p.id]:.3f}"
        lb.append(item)

    hist = page["history"]
    hist.innerHTML = ""
    for rd_ in sm.tour.road_map:
        block = div(classes=["match"])
        block.innerHTML = f"<strong>Раунд {rd_['round']}</strong>"
        for m in rd_["matches"]:
            line = div()
            if m["black_id"] is None:
                line.innerText = f"{sm.tour.players[m['white_id']].name} — bye"
            else:
                w = sm.tour.players[m["white_id"]].name
                b = sm.tour.players[m["black_id"]].name
                line.innerText = f"{w} vs {b} — {m['result']} (броски {m['throws']})"
            block.append(line)
        hist.append(block)


@when("click", "#btn-submit-roll")
def on_submit_roll(event):
    if sm is None:
        return
    raw = page["pc-roll-input"].value.strip()
    if not raw.isdigit():
        page["pc-roll-prompt"].innerText = "Введите целое число"
        return
    sm.submit_pc_roll(int(raw))
    page["pc-roll-input"].value = ""
    render_tournament()


@when("click", "#btn-reroll-yes")
def on_reroll_yes(event):
    if sm is None:
        return
    sm.submit_reroll(True)
    render_tournament()


@when("click", "#btn-reroll-no")
def on_reroll_no(event):
    if sm is None:
        return
    sm.submit_reroll(False)
    render_tournament()


@when("click", "#btn-next-round")
def on_next_round(event):
    if sm is None:
        return
    sm.start_round()
    render_tournament()


# ==================== Старт ====================

render_setup()