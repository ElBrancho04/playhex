from player import Player
from board import HexBoard

def get_neighbors(r: int, c: int, size: int) -> list[tuple[int, int]]:

    if r % 2 == 0:
        deltas = [
            (-1, -1), (-1,  0),
            ( 0, -1), ( 0, 1),
            (1, -1), (1,  0)
        ]
    else:
        deltas = [
            (-1,  0), (-1, 1),
            ( 0, -1), ( 0, 1),
            (1,  0), (1, 1)
        ]

    neighbors = []
    for dr, dc in deltas:
        nr, nc = r + dr, c + dc
        if 0 <= nr < size and 0 <= nc < size:
            neighbors.append((nr, nc))

    return neighbors

class SmartPlayer(Player):
    def __init__(self, player_id: int):
        super().__init__(player_id)

    def play(self, board: HexBoard) -> tuple:
        pass