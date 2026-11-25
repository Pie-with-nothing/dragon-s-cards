from pyscript import when
from pyscript.web import page, div, li, button

from config import (
    CONFIG_DEFAULTS, CURRENT_KEY, NAMED_PREFIX,
    make_browser_store, load_current, save_current,
    load_named, save_named, generate_npc, normalize,
)

from engine import TournamentSM, Player



setup_players: list[Player] = []
sm: TournamentSM | None = None

_store = make_browser_store()
config = load_current(_store)


def _read_config_from_dom() -> dict:
    return {
        "dice_min": int(page["cfg-dice-min"].value),
        "dice_max": int(page["cfg-dice-max"].value),
        "modif_min": int(page["cfg-modif-min"].value),
        "modif_max": int(page["cfg-modif-max"].value),
        "reroll_min": int(page["cfg-reroll-min"].value),
        "reroll_max": int(page["cfg-reroll-max"].value),
        "adv_chance": int(page["cfg-adv-chance"].value),
        "distribution": "normal" if page["cfg-dist-normal"]._dom_element.checked else "uniform",
        "save_path": page["cfg-save-path"].value.strip() or "default",
    }


def _write_config_to_dom(cfg: dict):
    page["cfg-dice-min"].value = cfg["dice_min"]
    page["cfg-dice-max"].value = cfg["dice_max"]
    page["cfg-modif-min"].value = cfg["modif_min"]
    page["cfg-modif-max"].value = cfg["modif_max"]
    page["cfg-reroll-min"].value = cfg["reroll_min"]
    page["cfg-reroll-max"].value = cfg["reroll_max"]
    page["cfg-adv-chance"].value = cfg["adv_chance"]
    if cfg["distribution"] == "normal":
        page["cfg-dist-normal"]._dom_element.checked = True
    else:
        page["cfg-dist-uniform"]._dom_element.checked = True
    page["cfg-save-path"].value = cfg["save_path"]


def show_config_modal(visible: bool):
    el = page["config-modal"]
    if visible:
        _write_config_to_dom(config)
        el.classes.remove("hidden")
    else:
        el.classes.add("hidden")


@when("click", "#btn-open-config")
def on_open_config(event):
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
        return
    if cfg["dice_min"] < 1 or cfg["dice_max"] < 1:
        return
    if cfg["reroll_min"] < 0 or cfg["reroll_max"] > 2 or cfg["reroll_max"] < cfg["reroll_min"]:
        return
    config = normalize(cfg)                # защита от того, что пришло из DOM
    save_current(_store, config)
    save_named(_store, config["save_path"], config)
    show_config_modal(False)


@when("click", "#btn-config-load")
def on_config_load(event):
    global config
    path = page["cfg-save-path"].value.strip() or "default"
    cfg = load_named(_store, path)
    if cfg is not None:
        config = cfg
        _write_config_to_dom(config)
        

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
        return
    advantage = page["inp-adv"].checked
    is_human  = page["inp-human"].checked

    try:
        pl = Player(name, dice, modif, reroll, advantage, is_human=is_human)
    except ValueError:
        return
    
    setup_players.append(pl)
    page["inp-name"].value = ""           # удобно вводить следующего
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