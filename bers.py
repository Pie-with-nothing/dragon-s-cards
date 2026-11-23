from random import randint as rd
from random import choices
from abc import ABC, abstractmethod
from math import log2, ceil
from copy import deepcopy
from caissify_pairings import generate_pairings

def d6(advantage: bool) -> int:
    return max(rd(1, 6), rd(1, 6)) if advantage else rd(1, 6)

"""
3.5 - стандарт d6
4.25 - рерол
4.625 - рерол+рерол
4.47 - премка
5.07 - премка+прем_рерол
5.34 - премка+прем_рерол+прем_рерол
"""

class Player(ABC):
    _id_counter = 0
    def __init__(self, name: str, dice_pull: int, modif: int, reroll=0, advantage=False):
        if dice_pull <= 0:
            raise ValueError("dice_pull must be positive")
        if reroll < 0:
            raise ValueError("reroll cannot be negative")
        
        self.id = Player._id_counter
        Player._id_counter += 1
        self.name = name
        self.dice_pull = dice_pull
        self.modif = modif
        self.reroll = reroll
        self.advantage = advantage
        
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
    
    def full_info(self):
        ret = f"{self.id}: {self.name} - {self.dice_pull}d6+{self.modif}"
        ur = f", {self.reroll} переброс(а)" if self.reroll else ""
        n = f", преимущество" if self.advantage else ""
        return f"{ret}{ur}{n}"
    
    @abstractmethod 
    def make_roll(self) -> int:
        pass

class PC_Player(Player):
    #Вот тут io залупа     
    def make_roll(self):
        while 1:
            inp = input("Введите итоговый результат броска ")
            if inp.isdecimal():
                return int(inp)

class NPC_Player(Player):
    def __init__(self, name: str, dice_pull: int, modif: int, reroll=0, advantage=False):
        super().__init__(name, dice_pull, modif, reroll, advantage)
        self._curr_roll = None
    
    def full_info(self):
        sup_str = super().full_info()
        return f"{sup_str}. Бросок: {self._curr_roll}"
    
    #Вот тут io залупа
    def _reroll_loop(self) -> None:
        for i in range(self.reroll):
            while 1:
                print(f"Текущие броски: {self._curr_roll}. Осталось {self.reroll - i} перебросов")
                answ = input("Перебросить? (y/n) ")
                if answ.lower().replace(" ", "") in ("yes", "y", "да", "д"):
                    self._curr_roll[self._curr_roll.index(min(self._curr_roll))] = d6(self.advantage)
                    break
                elif answ.lower().replace(" ", "") in ("no", "n", "нет", "н"):
                    return
    
    def _roll(self) -> None:
        res = [d6(self.advantage) for i in range(self.dice_pull)]
        self._curr_roll = res
        self._reroll_loop()
        #return self._curr_roll.copy()
    
    def make_roll(self) -> int:
        self._roll()
        return sum(self._curr_roll) + self.modif

class Gen_Tour_Table():
    def __init__(self, num_players):
        self.num_players = num_players
    def gen(self): #test. need rewrite
        alf = 'qwertyuiopasdfghjklzxcvbnm'
        alf = [i for i in alf]
        return [NPC_Player("".join(choices(alf, k=4)), d6(False), d6(False), rd(0, 2), rd(0, 1)) for i in range(self.num_players)]

class Tour_Table():
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
        return False if self.curr_round == -1 else True
    
    def _get_pairs(self) -> list[dict]:
        json_players = [{
            "id": id_,
            "name": player.name,
            "score": self.scores[id_],
            "rating": player._avg_sum,
            "color_hist": self.players_clr_hist[id_],
            "float_history": self.players_flt_hist[id_],
            "bye_count": self.players_byes[id_]
            } for id_, player in self.players.items()]
        
        pairings = generate_pairings(
        system="dutch",
        players=json_players,
        previous_pairings=self.prev_pairs,
        round_number=self.curr_round,
        total_rounds=self.rounds,
        max_byes_per_player=1
        )
        return pairings
    
    def _game_roll(self, opps_ids: tuple[int]) -> list[dict]:
        out = []
        for i in opps_ids:
            roll = self.players[i].make_roll()
            #roll = [p for p in self.players if p.id == i][0].make_roll()
            out.append({"id": i, "round_score": None, "roll": roll})
            
        if out[0]["roll"] > out[1]["roll"]:
            out[0]["round_score"], out[1]["round_score"] = 1, 0
            
        elif out[0]["roll"] < out[1]["roll"]:
            out[0]["round_score"], out[1]["round_score"] = 0, 1
            
        else:
            out[0]["round_score"], out[1]["round_score"] = 0.5, 0.5
        return out

    def _save_round(
        self,
        white_id: int,
        black_id: int,
        score: tuple[float],
        float_: tuple[str],
        throws: tuple[int]
    ):
        if black_id == None:
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
            
        self.road_map[self.curr_round - 1]["matches"].append(
            {
            "white_id": white_id,
            "black_id": black_id,
            "result": score,
            "throws": throws,
            "curr_scores": 
                [
                    {"id": white_id, "score": self.scores[white_id]},
                    {"id": black_id, "score": self.scores[black_id] if black_id != None else None}
                ]
            }
        )
            
    
    def next_round(self):
        if not self.is_going():
            return []
         
        self.curr_round += 1
        self.road_map.append({"round": self.curr_round, "matches": []})
        
        curr_pairs = self._get_pairs()
        
        for i in curr_pairs:
            if i["black_id"] == None:
                self._save_round(i["white_id"], None, (1, 0), ("none", "none"), ())
                continue
            round_rolls = self._game_roll((i["white_id"], i["black_id"]))
            white = [k for k in round_rolls if k["id"] == i["white_id"]][0]
            black = [k for k in round_rolls if k["id"] == i["black_id"]][0]
            
            if self.scores[white["id"]] > self.scores[black["id"]]:
                float_ = ("down", "up")
            elif self.scores[white["id"]] < self.scores[black["id"]]:
                float_ = ("up", "down")
            else:
                float_ = ("none", "none")
            
            self._save_round(
                white["id"],
                black["id"],
                (white["round_score"], black["round_score"]),
                float_,
                (white["roll"], black["roll"]),
            )
            
        if self.curr_round == self.rounds:
            self.curr_round = -1
            
        return deepcopy(self.road_map[-1])
    
    def _buchgolc(self):
        curr_score = -1
        eq_score = {}
        for i in sorted(self.scores.items(), key=lambda x: x[1]):
            if i[1] > curr_score:
                curr_score = i[1]
                if len(eq_score) > 1:
                    for eq_score_i in eq_score:
                        for pair in self.prev_pairs:
                            if eq_score_i in pair:
                                opp_id = pair[0] if pair.index(eq_score_i) else pair[1]
                                eq_score[eq_score_i] += self.scores[opp_id]
                    for koef, score_i in enumerate(sorted(eq_score.items(), key=lambda x: x[1])):
                        self.scores[score_i[0]] += koef * 0.001
                eq_score = {i[0]: 0}
            else:
                eq_score[i[0]] = 0
    
    def tie_break(self):
        if not self.is_going():
            self._buchgolc()
    
    def get_liderboard(self) -> list[Player]:
        self.tie_break()
                        
        sort_scores = sorted(
            self.scores.items(),
            key=lambda x: x[1],
            reverse=True
            )
        
        return [self.players[i[0]] for i in sort_scores]
            

'''
Генератор бомжей
Норм ввод/вывод
Графен
'''

    
if __name__ == "__main__": #test tournament
    q = NPC_Player("qwas", 4, 2)
    q.make_roll()
    print(q, 'hui')
    qwas = Gen_Tour_Table(7).gen()
    w = Tour_Table(qwas)
    print(*w.players.values(), sep='\n')
    '''
    players = [{
        "id": player.id,
        "name": player.name,
        "score": w.scores[player.id],
        "rating": player._avg_sum,
        "color_hist": w.players_clr_hist[player.id],
        "float_history": w.players_flt_hist[player.id],
        "bye_count": w.players_byes[player.id]
        } for i, player in enumerate(w.players)]
    '''
    #print(*players, sep='\n')
    '''
    pairings = generate_pairings(
    system="dutch",
    players=players,
    previous_pairings={},
    round_number=1,
    total_rounds=w.rounds,
    max_byes_per_player=1
    )
    '''
    #for p in pairings:
    #    print(p)
    print(w.rounds)
    print(w.next_round())
    for i in w.get_liderboard():
        print(i, w.scores[i.id])
    print(w.next_round())
    for i in w.get_liderboard():
        print(i, w.scores[i.id])
    print(w.next_round())
    for i in w.get_liderboard():
        print(i, w.scores[i.id])
    print(w.next_round())
    for i in w.get_liderboard():
        print(i, w.scores[i.id])
    for i in w.road_map:
        for m in i["matches"]:
            bye = False if m["black_id"] != None else True
            print(f'{w.players[m["white_id"]]}', end=' ')
            print(f'{"vs " + str(w.players[m["black_id"]]) if not bye else "- bye"}', end=' ')
            print(f'{"- " + str(m["result"]) if not bye else ""}', sep='')
            print(f' {m["curr_scores"]}')
        print()
    print(w.road_map)