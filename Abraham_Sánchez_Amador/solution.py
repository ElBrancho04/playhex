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

class UnionFind:
    def __init__(self, size: int):
        total = size * size + 2
        self.parent = list(range(total))
        self.rank   = [0] * total

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def connected(self, x: int, y: int) -> bool:
        return self.find(x) == self.find(y)


def check_winner(board: list[list[int]], player_id: int, size: int) -> bool:
    dsu           = UnionFind(size)
    virtual_start = size * size
    virtual_end   = size * size + 1

    for r in range(size):
        for c in range(size):
            if board[r][c] != player_id:
                continue

            idx = r * size + c

            if player_id == 1:
                if c == 0:
                    dsu.union(idx, virtual_start)
                if c == size - 1:
                    dsu.union(idx, virtual_end)
            else:
                if r == 0:
                    dsu.union(idx, virtual_start)
                if r == size - 1:
                    dsu.union(idx, virtual_end)

            for nr, nc in get_neighbors(r, c, size):
                if board[nr][nc] == player_id:
                    dsu.union(idx, nr * size + nc)

    return dsu.connected(virtual_start, virtual_end)

class SmartPlayer(Player):
    def __init__(self, player_id: int):
        super().__init__(player_id)

    def play(self, board: HexBoard) -> tuple:
        pass