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


class ReversibleDSU:
    def __init__(self, size: int, player_id: int):
        self.size      = size
        self.player_id = player_id
        self.VSTART    = size * size
        self.VEND      = size * size + 1
        total          = size * size + 2
        self.parent    = list(range(total))
        self.rank      = [0] * total
        self.history   = []

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            self.history.append(None)
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.history.append((ry, self.parent[ry], rx, self.rank[rx]))
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def undo(self) -> None:
        entry = self.history.pop()
        if entry is None:
            return
        ry, old_parent_ry, rx, old_rank_rx = entry
        self.parent[ry] = old_parent_ry
        self.rank[rx]   = old_rank_rx

    def checkpoint(self) -> int:
        return len(self.history)

    def rollback(self, cp: int) -> None:
        while len(self.history) > cp:
            self.undo()

    def win(self) -> bool:
        return self.find(self.VSTART) == self.find(self.VEND)

    def connect_borders(self, r: int, c: int) -> None:
        idx = r * self.size + c
        if self.player_id == 1:
            if c == 0:               self.union(idx, self.VSTART)
            if c == self.size - 1:   self.union(idx, self.VEND)
        else:
            if r == 0:               self.union(idx, self.VSTART)
            if r == self.size - 1:   self.union(idx, self.VEND)


def make_move(
    board: list[list[int]],
    r: int, c: int,
    cell_value: int,
    dsu_me: ReversibleDSU,
    dsu_opp: ReversibleDSU,
    size: int,
) -> tuple[int, int]:
    """
    Places cell_value at (r, c), updates the correct DSU incrementally.
    Returns (cp_me, cp_opp) checkpoints to pass to undo_move.
    """
    board[r][c] = cell_value
    dsu = dsu_me if cell_value == 1 else dsu_opp

    cp_me  = dsu_me.checkpoint()
    cp_opp = dsu_opp.checkpoint()

    idx = r * size + c
    dsu.connect_borders(r, c)
    for nr, nc in get_neighbors(r, c, size):
        if board[nr][nc] == cell_value:
            dsu.union(idx, nr * size + nc)

    return cp_me, cp_opp


def undo_move(
    board: list[list[int]],
    r: int, c: int,
    dsu_me: ReversibleDSU,
    dsu_opp: ReversibleDSU,
    cp_me: int,
    cp_opp: int,
) -> None:
    """Removes the piece at (r, c) and rolls back the DSU to the given checkpoints."""
    board[r][c] = 0
    dsu_me.rollback(cp_me)
    dsu_opp.rollback(cp_opp)


class SmartPlayer(Player):
    def __init__(self, player_id: int):
        super().__init__(player_id)

    def play(self, board: HexBoard) -> tuple:
        pass