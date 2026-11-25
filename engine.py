from random import randint as rd
from math import ceil, log2
from copy import deepcopy
from caissify_pairings import generate_pairings

"""
3.5 - стандарт d6
4.25 - рерол
4.625 - рерол+рерол
4.47 - премка
5.07 - премка+прем_рерол
5.34 - премка+прем_рерол+прем_рерол
"""


def d6(advantage: bool) -> int:
    return max(rd(1, 6), rd(1, 6)) if advantage else rd(1, 6)


class Player:
    _id_counter = 0

    def __init__(self, name: str, dice_pull: int, modif: int, reroll=0, advantage=False, is_human=False):
        if dice_pull <= 0:
            raise ValueError("dice_pull must be positive")
        if reroll < 0:
            raise ValueError("reroll cannot be negative")
        self.id = Player._id_counter
        Player._id_counter += 1
        self.name = name
        self.dice_pull = dice_pull
        self.modif = modif
        self.reroll = min(reroll, 2)
        self.advantage = advantage
        self.is_human = is_human
        self._avg_sum = self._comp_avg_sum()

    def _comp_avg_sum(self):
        if self.advantage:
            if self.reroll > self.dice_pull:
                return self.modif + 5.34
            return self.modif + 4.47 * (self.dice_pull - self.reroll) + 5.07 * self.reroll
        if self.reroll > self.dice_pull:
            return self.modif + 4.625
        return self.modif + 3.5 * (self.dice_pull - self.reroll) + 4.25 * self.reroll

    def __str__(self):
        return f'{self.id}: {self.name}'

    def full_info(self) -> str:
        pc = "PC" if self.is_human else "NPC"
        mod_sign = "" if self.modif < 0 else "+"
        
        ret = f"{self.name} ({pc}) - {self.dice_pull}d6{mod_sign}{self.modif}"
        ur = f", {self.reroll} переброс(а)" if self.reroll else ""
        n = f", преимущество" if self.advantage else ""
        return f"{ret}{ur}{n}"


class Tour_Table:
    def __init__(self, players: list[Player]):
        self.players = {p.id: p for p in players}
        self.scores = {p.id: 0.0 for p in players}
        self.players_flt_hist = {p.id: [] for p in players}
        self.players_clr_hist = {p.id: [] for p in players}
        self.players_byes = {p.id: 0 for p in players}
        self.prev_pairs = set()
        self.road_map = []
        self.rounds = ceil(log2(len(players)))
        self.curr_round = 0

    def is_going(self) -> bool:
        return self.curr_round != -1

    def _get_pairs(self) -> list[dict]:
        json_players = [{
            "id": id_, "name": p.name,
            "score": self.scores[id_], "rating": p._avg_sum,
            "color_hist": self.players_clr_hist[id_],
            "float_history": self.players_flt_hist[id_],
            "bye_count": self.players_byes[id_],
        } for id_, p in self.players.items()]
        return generate_pairings(
            system="dutch",
            players=json_players,
            previous_pairings=self.prev_pairs,
            round_number=self.curr_round,
            total_rounds=self.rounds,
            max_byes_per_player=1,
        )

    def _save_round(self, white_id, black_id, score, float_, throws):
        if black_id is None:
            self.players_byes[white_id] += 1
            self.scores[white_id] += 1
            self.players_clr_hist[white_id].append("none")
            self.players_flt_hist[white_id].append("none")
        else:
            for i, id_ in enumerate((white_id, black_id)):
                self.scores[id_] += score[i]
                self.players_clr_hist[id_].append(("white", "black")[i])
                self.players_flt_hist[id_].append(float_[i])
            self.prev_pairs.add(tuple(sorted([white_id, black_id])))
        self.road_map[self.curr_round - 1]["matches"].append({
            "white_id": white_id,
            "black_id": black_id,
            "result": score,
            "throws": throws,
            "curr_scores": [
                {"id": white_id, "score": self.scores[white_id]},
                {"id": black_id, "score": self.scores[black_id] if black_id is not None else None},
            ],
        })

    def _iter_on_eq_score(self, eq_score: dict[int, float]):
        if len(eq_score) > 1:
            for eq_score_i in eq_score:
                for pair in self.prev_pairs:
                    if eq_score_i in pair:
                        opp_id = pair[0] if pair.index(eq_score_i) else pair[1]
                        eq_score[eq_score_i] += float(f'{self.scores[opp_id]:.1f}')
                        
            for koef, score_i in enumerate(
                                    sorted(
                                        eq_score.items(), 
                                        key=lambda x: (x[1], -self.players[x[0]]._avg_sum)
                                    )
                                ):
                self.scores[score_i[0]] += koef * 0.001

    def _buchgolc(self):
        curr_score = -1
        eq_score = {}
        for i in sorted(self.scores.items(), key=lambda x: x[1]):
            if i[1] > curr_score:
                curr_score = i[1]
                self._iter_on_eq_score(eq_score)
                eq_score = {i[0]: 0}
            else:
                eq_score[i[0]] = 0
        self._iter_on_eq_score(eq_score)

    def tie_break(self):
        if not self.is_going():
            self._buchgolc()

    def get_liderboard(self) -> list[Player]:
        self.tie_break()
        sort_scores = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
        return [self.players[i[0]] for i in sort_scores]


class TournamentSM:
    IDLE = "idle"
    WAITING_PC_ROLL = "waiting_pc_roll"
    WAITING_REROLL = "waiting_reroll"
    ROUND_COMPLETE = "round_complete"
    TOURNAMENT_DONE = "tournament_done"

    def __init__(self, players: list[Player]):
        self.tour = Tour_Table(players)
        self.state = self.IDLE
        self.prompt = ""
        self.last_round_result = None

        # внутреннее состояние раунда
        self._pairings: list[dict] = []
        self._pair_idx = 0
        self._pair_rolls: list[dict] = []   # [{"id": int, "roll": int}] до 2 шт.
        self._npc_ctx: dict | None = None   # {"player_id", "dice", "remaining", "advantage"}

    @property
    def is_waiting(self) -> bool:
        return self.state in (self.WAITING_PC_ROLL, self.WAITING_REROLL)

    def start_round(self):
        if not self.tour.is_going():
            self.state = self.TOURNAMENT_DONE
            self.prompt = "Турнир завершён"
            return
        self.tour.curr_round += 1
        self.tour.road_map.append({"round": self.tour.curr_round, "matches": []})
        self._pairings = self.tour._get_pairs()
        self._pair_idx = 0
        self._pair_rolls = []
        self._npc_ctx = None
        self.last_round_result = None
        self._step()

    def submit_pc_roll(self, value: int):
        if self.state != self.WAITING_PC_ROLL:
            raise RuntimeError(f"submit_pc_roll в состоянии {self.state}")
        pair = self._pairings[self._pair_idx]
        player_id = pair[("white_id", "black_id")[len(self._pair_rolls)]]
        self._pair_rolls.append({"id": player_id, "roll": value})
        self._step()

    def submit_reroll(self, do_reroll: bool):
        if self.state != self.WAITING_REROLL:
            raise RuntimeError(f"submit_reroll в состоянии {self.state}")
        ctx = self._npc_ctx
        if do_reroll:
            dice = ctx["dice"]
            dice[dice.index(min(dice))] = d6(ctx["advantage"])
            ctx["remaining"] -= 1
        else:
            ctx["remaining"] = 0
        self._step()

    @property
    def leaderboard(self) -> list[Player]:
        return self.tour.get_liderboard()

    def _step(self):
        """Продвигает автомат без ввода, пока возможно. Останавливается на ожидании."""
        while True:
            # 1) Продолжаем перебросы NPC, если они начаты
            if self._npc_ctx is not None:
                if self._npc_ctx["remaining"] <= 0:
                    self._finish_npc_roll()
                    continue
                ctx = self._npc_ctx
                player = self.tour.players[ctx["player_id"]]
                self.state = self.WAITING_REROLL
                self.prompt = (
                    f"{player.name}: текущие броски {ctx['dice']}, "
                    f"осталось {ctx['remaining']} перебросов. Перебросить?"
                )
                return

            # 2) Раунд закончился?
            if self._pair_idx >= len(self._pairings):
                self._finish_round()
                return

            # 3) Пара собрала оба броска — обрабатываем
            if len(self._pair_rolls) == 2:
                self._process_pair()
                continue

            pair = self._pairings[self._pair_idx]

            # 4) Bye
            if pair["black_id"] is None:
                self.tour._save_round(pair["white_id"], None, (1, 0), ("none", "none"), ())
                self._pair_idx += 1
                self._pair_rolls = []
                continue

            # 5) Нужен бросок от текущего игрока
            player_id = pair[("white_id", "black_id")[len(self._pair_rolls)]]
            player = self.tour.players[player_id]

            if player.is_human:
                self.state = self.WAITING_PC_ROLL
                self.prompt = f"{player.name}: введите итоговый результат броска"
                return

            # NPC — начинаем бросать, цикл вернётся наверх и обработает ветку NPC
            dice = [d6(player.advantage) for _ in range(player.dice_pull)]
            self._npc_ctx = {
                "player_id": player_id,
                "dice": dice,
                "remaining": player.reroll,
                "advantage": player.advantage,
            }

    def _finish_npc_roll(self):
        ctx = self._npc_ctx
        player = self.tour.players[ctx["player_id"]]
        total = sum(ctx["dice"]) + player.modif
        self._pair_rolls.append({"id": ctx["player_id"], "roll": total})
        self._npc_ctx = None

    def _process_pair(self):
        pair = self._pairings[self._pair_idx]
        w, b = pair["white_id"], pair["black_id"]
        wr = next(r["roll"] for r in self._pair_rolls if r["id"] == w)
        br = next(r["roll"] for r in self._pair_rolls if r["id"] == b)

        if wr > br:   ws, bs = 1, 0
        elif wr < br: ws, bs = 0, 1
        else:         ws, bs = 0.5, 0.5

        sw, sb = self.tour.scores[w], self.tour.scores[b]
        if sw > sb:   float_ = ("down", "up")
        elif sw < sb: float_ = ("up", "down")
        else:         float_ = ("none", "none")

        self.tour._save_round(w, b, (ws, bs), float_, (wr, br))
        self._pair_idx += 1
        self._pair_rolls = []

    def _finish_round(self):
        self.last_round_result = deepcopy(self.tour.road_map[-1])
        if self.tour.curr_round == self.tour.rounds:
            self.tour.curr_round = -1
            self.state = self.TOURNAMENT_DONE
            self.prompt = "Турнир завершён"
        else:
            self.state = self.ROUND_COMPLETE
            self.prompt = f"Раунд {self.tour.curr_round} завершён"
            

#TODO try except +
#TODO отрицательные модификаторы +
#TODO тайбрейкер на тайбрейкер +
#TODO readme
#TODO config
#TODO генератор бомжей
"""Генератор бомжей. Надо такой, чтоб я мог выставить минимальное и
максимальное значения кубов и модификатор, и бомж генерится с
равномерным (или нормальным) распределением в этом диапазоне, с реролами тоже самое,
с преимуществом - чтоб я выставлял шанс получения рерола"""
#TODO оффлайн билд
#TODO перезагрузка по кннопке
#TODO библиотека персонажей
"""Чтоб я мог как гм заполнить челиков туда и просто брать из банка,
того же Кузьму, чтоб не дрочить каждый раз его ввод"""
#TODO коллекция карточек
"""Было бы прикольно сделать там коллекцию карточек, чтоб в свободное время делать
карточки и заливать, чтоб прям видеть что ты коллекционируешь (просто раздел,
карточки я пока не наделал, тока персы под них есть)"""