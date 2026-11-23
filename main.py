from random import choices, randint as rd
from pyscript import when
from pyscript.web import page, div, li
from engine import TournamentSM, Player, d6


def make_players(n_npc=7):
    alf = list("qwertyuiopasdfghjklzxcvbnm")
    npcs = [Player("".join(choices(alf, k=4)), d6(False), d6(False), rd(0, 2), rd(0, 1))
            for _ in range(n_npc)]
    return npcs + [Player("HUMAN", 3, 1, is_human=True)]


sm = TournamentSM(make_players())


def show(id_, visible):
    el = page[id_]
    if visible: el.classes.remove("hidden")
    else:       el.classes.add("hidden")

def init_player_list():
    pl = page["player-list"]
    pl.innerHTML = ""
    for p in sm.tour.players.values():
        item = li()
        item.innerText = f"{p.full_info()}"
        pl.append(item)

def render():
    # Панели
    show("panel-pc-roll",     sm.state == TournamentSM.WAITING_PC_ROLL)
    show("panel-reroll",      sm.state == TournamentSM.WAITING_REROLL)
    show("panel-round-done",  sm.state in (TournamentSM.ROUND_COMPLETE,
                                            TournamentSM.TOURNAMENT_DONE))

    if sm.state == TournamentSM.WAITING_PC_ROLL:
        page["pc-roll-prompt"].innerText = sm.prompt
    elif sm.state == TournamentSM.WAITING_REROLL:
        page["reroll-prompt"].innerText = sm.prompt
    else:
        page["round-done-prompt"].innerText = sm.prompt

    # Кнопка "Следующий раунд" прячется, когда турнир завершён
    btn = page["btn-next-round"]
    if sm.state == TournamentSM.TOURNAMENT_DONE:
        btn.classes.add("hidden")
    else:
        btn.classes.remove("hidden")

    # Лидерборд
    lb = page["leaderboard"]
    lb.innerHTML = ""
    for p in sm.leaderboard:
        item = li()
        item.innerText = f"{p.full_info()} — {sm.tour.scores[p.id]:.3f}"
        lb.append(item)

    # История раундов
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

    # Список игроков (заполняется один раз)


@when("click", "#btn-start")
def on_start(event):
    page["panel-start"].classes.add("hidden")
    sm.start_round()
    render()


@when("click", "#btn-submit-roll")
def on_submit_roll(event):
    raw = page["pc-roll-input"].value.strip()
    if not raw.isdigit():
        page["pc-roll-prompt"].innerText = "Введите целое число"
        return
    sm.submit_pc_roll(int(raw))
    page["pc-roll-input"].value = ""
    render()


@when("click", "#btn-reroll-yes")
def on_reroll_yes(event):
    sm.submit_reroll(True)
    render()


@when("click", "#btn-reroll-no")
def on_reroll_no(event):
    sm.submit_reroll(False)
    render()


@when("click", "#btn-next-round")
def on_next_round(event):
    sm.start_round()
    render()

init_player_list()
render()