from random import choices, randint as rd
from engine import TournamentSM, Player, d6


def make_players(n_npc=7):
    alf = list("qwertyuiopasdfghjklzxcvbnm")
    npcs = [Player("".join(choices(alf, k=4)), d6(False), rd(-2, 6), rd(0, 2), rd(0, 1))
            for _ in range(n_npc)]
    return npcs + [Player("HUMAN", 3, -1, is_human=True)]


def resolve(sm):
    """Прокручивает SM через все интерактивные точки, читая ввод из консоли."""
    while sm.is_waiting:
        if sm.state == TournamentSM.WAITING_PC_ROLL:
            print(sm.prompt)
            while True:
                v = input("> ")
                if v.strip().isdigit():
                    sm.submit_pc_roll(int(v))
                    break
                print("Введите целое число")
        else:  # WAITING_REROLL
            print(sm.prompt)
            while True:
                a = input("(y/n) > ").lower().replace(" ", "")
                if a in ("y", "yes", "д", "да"):
                    sm.submit_reroll(True); break
                if a in ("n", "no", "н", "нет"):
                    sm.submit_reroll(False); break


def show_round(sm):
    if not sm.last_round_result:
        return
    print(f"\n=== Раунд {sm.last_round_result['round']} ===")
    for m in sm.last_round_result["matches"]:
        if m["black_id"] is None:
            print(f"  {sm.tour.players[m['white_id']].name} — bye")
        else:
            w = sm.tour.players[m["white_id"]].name
            b = sm.tour.players[m["black_id"]].name
            print(f"  {w} vs {b} — {m['result']} (броски {m['throws']})")


def show_leaderboard(sm):
    for p in sm.leaderboard:
        print(f"  {p.full_info()}:\t{sm.tour.scores[p.id]:.3f}")


def run(sm):
    print("Игроки:")
    for p in sm.tour.players.values():
        print(f'  {p.full_info()}')
    print()

    while True:
        sm.start_round()
        resolve(sm)
        if sm.state == TournamentSM.TOURNAMENT_DONE:
            print(sm.prompt)
            break
        show_round(sm)
        print("\nЛидерборд:")
        show_leaderboard(sm)
        print()

    print("\nФинал:")
    show_leaderboard(sm)


if __name__ == "__main__":
    run(TournamentSM(make_players()))