from pyscript import when
from pyscript.web import page, div, li, button
from engine import TournamentSM, Player


setup_players: list[Player] = []
sm: TournamentSM | None = None


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
        page["inp-dice"].style["background-color"] = "#FF604A"
        page["inp-reroll"].style["background-color"] = "#FF604A"
        return
    page["inp-dice"].style["background-color"] = "#FFFFFF"
    page["inp-reroll"].style["background-color"] = "#FFFFFF"
    
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