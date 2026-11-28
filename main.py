from pyscript import when
from pyscript.web import page, div, li, button

from config import (
    generate_npc, normalize, CONFIG_DEFAULTS,
    download_json, from_json_str, gen_name,
    download_player_json, player_from_json_str, safe_filename,
)

from engine import TournamentSM, Player



setup_players: list[Player] = []
sm: TournamentSM | None = None

lb_detailed = False

config = dict(CONFIG_DEFAULTS)

CONFIG_NUMBER_FIELDS = (
    "cfg-dice-min", "cfg-dice-max",
    "cfg-modif-min", "cfg-modif-max",
    "cfg-reroll-min", "cfg-reroll-max",
    "cfg-adv-chance",
)

CONFIG_FIELD_PAIRS = {
    "cfg-dice-min":   "cfg-dice-max",
    "cfg-dice-max":   "cfg-dice-min",
    "cfg-modif-min":  "cfg-modif-max",
    "cfg-modif-max":  "cfg-modif-min",
    "cfg-reroll-min": "cfg-reroll-max",
    "cfg-reroll-max": "cfg-reroll-min",
}

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
    # Любой ввод снимает подсветку с этого поля — и с парного, если это граница диапазона
    try:
        el = event.target
        el.classList.remove("invalid")
        pair_id = CONFIG_FIELD_PAIRS.get(el.id)
        if pair_id is not None:
            page[pair_id]._dom_element.classList.remove("invalid")
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
        errors.append((("cfg-dice-min",), "Минимум кубов должен быть ≥ 1"))
    if cfg["dice_max"] < 1:
        errors.append((("cfg-dice-max",), "Максимум кубов должен быть ≥ 1"))
    if cfg["dice_max"] < cfg["dice_min"]:
        errors.append((("cfg-dice-max", "cfg-dice-min"), "Максимум кубов не может быть меньше минимума"))
    if cfg["modif_max"] < cfg["modif_min"]:
        errors.append((("cfg-modif-max", "cfg-modif-min"), "Максимум модификатора не может быть меньше минимума"))
    if cfg["reroll_min"] < 0:
        errors.append((("cfg-reroll-min",), "Минимум рероллов не может быть < 0"))
    if cfg["reroll_min"] > 2:
        errors.append((("cfg-reroll-min",), "Минимум рероллов не может быть > 2"))
    if cfg["reroll_max"] < 0:
        errors.append((("cfg-reroll-max",), "Максимум рероллов не может быть < 0"))
    if cfg["reroll_max"] > 2:
        errors.append((("cfg-reroll-max",), "Максимум рероллов не может быть > 2"))
    if cfg["reroll_max"] < cfg["reroll_min"]:
        errors.append((("cfg-reroll-max", "cfg-reroll-min"), "Максимум рероллов не может быть меньше минимума"))
    if cfg["adv_chance"] < 0 or cfg["adv_chance"] > 100:
        errors.append((("cfg-adv-chance",), "Шанс преимущества должен быть 0–100%"))

    if errors:
        for fids, _ in errors:
            for fid in fids:
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
        # Импортированный конфиг всегда валиден — снимаем все следы прошлых ошибок
        clear_invalid(*CONFIG_NUMBER_FIELDS)
        hide_toast()
    except Exception as e:
        # Реальную ошибку чтения/парсинга файла показываем тостом, не трогая #cfg-filename
        notify(f"Ошибка импорта конфига: {e}", "error")
    finally:
        input_el.value = ""   # позволяет выбрать тот же файл повторно

# ==================== Setup ====================

def _export_player(p: Player):
    try:
        download_player_json(p, safe_filename(p.name))
        notify(f"Экспортирован: {p.name}", "info")
    except Exception as e:
        notify(f"Ошибка экспорта: {e}", "error")


@when("click", "#btn-import-player")
def on_import_player_click(event):
    page["player-file-input"]._dom_element.click()


@when("change", "#player-file-input")
async def on_player_file_selected(event):
    input_el = page["player-file-input"]._dom_element
    files = input_el.files
    if files.length == 0:
        return
    file = files.item(0)
    try:
        text = await file.text()
        p = player_from_json_str(str(text))
        setup_players.append(p)
        render_setup()
        notify(f"Импортирован: {p.name}", "info")
    except Exception as e:
        notify(f"Ошибка импорта: {e}", "error")
    finally:
        input_el.value = ""

def render_setup():
    pl = page["player-list"]
    pl.innerHTML = ""
    for idx, p in enumerate(setup_players):
        item = li()
        item.innerText = p.full_info()

        exp = button("▼", classes=["player-export"])
        exp._dom_element.title = "Экспорт персонажа"
        exp.dataset.idx = str(idx)

        rm = button("✕", classes=["player-remove"])
        rm._dom_element.title = "Удалить персонажа"
        rm.dataset.idx = str(idx)

        item.append(exp)
        item.append(rm)
        pl.append(item)
    page["btn-start-tournament"].disabled = len(setup_players) < 2


@when("click", "#btn-add-player")
def on_add_player(event):
    name = page["inp-name"].value.strip() or gen_name()

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
    tgt = event.target
    classes = tgt.className.split()

    if "player-remove" in classes:
        setup_players.pop(int(tgt.dataset.idx))
        render_setup()
    elif "player-export" in classes:
        idx = int(tgt.dataset.idx)
        if 0 <= idx < len(setup_players):
            _export_player(setup_players[idx])

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
    sm = TournamentSM(list(setup_players))
    sm.start_round()
    render_tournament()


# ==================== Tournament ====================

def show(id_, visible):
    el = page[id_]
    if visible: el.classes.remove("hidden")
    else:       el.classes.add("hidden")


def render_leaderboard():
    lb = page["leaderboard"]
    lb.innerHTML = ""

    page["btn-lb-details"].disabled = sm is None
    if sm is None:
        return

    for p in sm.leaderboard:
        item = li()
        item.innerText = p.full_info()

        exp = button("▼", classes=["leaderboard-export"])
        exp._dom_element.title = "Экспорт персонажа"
        exp.dataset.pid = str(p.id)
        item.append(exp)

        if lb_detailed:
            details = div(classes=["lb-details"])
            details.innerText = (
                f"Очки: {sm.tour.scores[p.id]} · "
                f"Оппоненты: {sm.tour.opps_scores_sum[p.id]} · "
                f"Ср. сумма: {p._avg_sum}"
            )
            item.append(details)

        lb.append(item)

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


    is_done = sm.state == TournamentSM.TOURNAMENT_DONE
    show("btn-next-round",         not is_done)
    show("btn-restart-tournament", is_done)


    render_leaderboard()

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

@when("click", "#btn-restart-tournament")
def on_restart_tournament(event):
    global sm, lb_detailed
    sm = None
    lb_detailed = False
    page["btn-lb-details"].innerText = "Подробно"

    show("panel-round-done", False)
    show("panel-pc-roll",    False)
    show("panel-reroll",     False)
    show("panel-setup",      True)

    page["history"].innerHTML = ""
    render_leaderboard()   # очистит лидерборд и задизейблит «Подробно»
    render_setup()         # восстановит список игроков

@when("click", "#leaderboard")
def on_leaderboard_click(event):
    tgt = event.target
    if "leaderboard-export" not in tgt.className.split():
        return
    if sm is None:
        return
    pid = int(tgt.dataset.pid)
    p = sm.tour.players.get(pid)
    if p is None:
        return
    _export_player(p)

@when("click", "#btn-lb-details")
def on_lb_details(event):
    global lb_detailed
    if sm is None:
        return
    lb_detailed = not lb_detailed
    page["btn-lb-details"].innerText = "Скрыть" if lb_detailed else "Подробно"
    render_leaderboard()
# ==================== Старт ====================

def hide_loading():
    try:
        page["loading-overlay"]._dom_element.classList.add("hidden")
    except Exception:
        pass

render_setup()
hide_loading()