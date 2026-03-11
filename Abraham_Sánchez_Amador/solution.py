import time
from math import log, sqrt
from random import choice, shuffle
from player import Player
from board import HexBoard


def get_neighbors(r: int, c: int, size: int) -> list[tuple[int, int]]:
    if r % 2 == 0:
        deltas = [
            (-1, -1), (-1,  0),
            ( 0, -1), ( 0,  1),
            ( 1, -1), ( 1,  0),
        ]
    else:
        deltas = [
            (-1,  0), (-1,  1),
            ( 0, -1), ( 0,  1),
            ( 1,  0), ( 1,  1),
        ]
    neighbors = []
    for dr, dc in deltas:
        nr, nc = r + dr, c + dc
        if 0 <= nr < size and 0 <= nc < size:
            neighbors.append((nr, nc))
    return neighbors


# Module-level neighbors cache: _NBRS[size][r][c] → list of (nr, nc)
# Built once per board size, reused across every make_move call.
_NBRS: dict[int, list] = {}


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
            if c == 0:             self.union(idx, self.VSTART)
            if c == self.size - 1: self.union(idx, self.VEND)
        else:
            if r == 0:             self.union(idx, self.VSTART)
            if r == self.size - 1: self.union(idx, self.VEND)


def make_move(
    board: list[list[int]],
    r: int, c: int,
    cell_value: int,
    dsu_me: ReversibleDSU,
    dsu_opp: ReversibleDSU,
    size: int,
) -> tuple[int, int]:
    board[r][c] = cell_value
    dsu        = dsu_me if cell_value == 1 else dsu_opp
    cp_me      = dsu_me.checkpoint()
    cp_opp     = dsu_opp.checkpoint()
    idx        = r * size + c
    dsu.connect_borders(r, c)
    # Use precomputed cache when available (built in play()), else compute on the fly.
    nbrs = _NBRS.get(size)
    for nr, nc in (nbrs[r][c] if nbrs else get_neighbors(r, c, size)):
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
    board[r][c] = 0
    dsu_me.rollback(cp_me)
    dsu_opp.rollback(cp_opp)


class MCTSNode:
    """
    player       : cell_value (1 or 2) of whoever made the move to reach this node.
                   None for the root.
    wins         : wins for `player` accumulated through simulations.
    free_cells   : ALL free cells at this node's board state. Never modified after init.
    untried_moves: subset of free_cells not yet expanded as children. Shrinks over time.
    """
    __slots__ = ('move', 'player', 'wins', 'visits', 'children',
                 'untried_moves', 'free_cells', 'parent')

    def __init__(self, move, player, untried_moves, parent=None, free_cells=None):
        self.move          = move
        self.player        = player
        self.wins          = 0
        self.visits        = 0
        self.children      = []
        self.untried_moves = untried_moves
        # free_cells: immutable snapshot of all free cells at this state.
        self.free_cells    = free_cells if free_cells is not None else untried_moves[:]
        self.parent        = parent

    def ucb1(self) -> float:
        if self.visits == 0:
            return float('inf')
        return self.wins / self.visits + sqrt(2) * sqrt(log(self.parent.visits) / self.visits)

    def best_child(self) -> 'MCTSNode':
        return max(self.children, key=lambda n: n.ucb1())


class SmartPlayer(Player):
    def __init__(self, player_id: int):
        super().__init__(player_id)

    def play(self, board: HexBoard) -> tuple:
        size = board.size
        b    = [row[:] for row in board.board]

        if size not in _NBRS:
            _NBRS[size] = [
                [get_neighbors(r, c, size) for c in range(size)]
                for r in range(size)
            ]

        # Build DSUs incrementally from the existing board state
        dsu_me  = ReversibleDSU(size, self.player_id)
        dsu_opp = ReversibleDSU(size, 3 - self.player_id)
        for r in range(size):
            for c in range(size):
                if b[r][c] != 0:
                    make_move(b, r, c, b[r][c], dsu_me, dsu_opp, size)

        free = [(r, c) for r in range(size) for c in range(size) if b[r][c] == 0]

        if len(free) == 1:
            return free[0]

        # Forced moves
        # Pass 1: immediate winning move for me
        for r, c in free:
            cp = make_move(b, r, c, 1, dsu_me, dsu_opp, size)
            won = dsu_me.win()
            undo_move(b, r, c, dsu_me, dsu_opp, *cp)
            if won:
                return (r, c)

        # Pass 2: block opponent's immediate winning move
        for r, c in free:
            cp = make_move(b, r, c, 2, dsu_me, dsu_opp, size)
            opp_wins = dsu_opp.win()
            undo_move(b, r, c, dsu_me, dsu_opp, *cp)
            if opp_wins:
                return (r, c)
        # ______________________________________________________

        root = MCTSNode(
            move=None, player=None,
            untried_moves=free[:], free_cells=free[:],
            parent=None,
        )

        # margin = 0.35s OS/GC jitter buffer + 0.002s per unit of N (algorithmic growth)
        deadline = time.time() + 5.0 - (0.35 + 0.002 * size)

        while time.time() < deadline:
            node    = root
            # path entries: (node, r, c, cp_me, cp_opp)
            path    = []
            to_move = 1
            winner  = 0

            # SELECT
            while not node.untried_moves and node.children:
                node          = node.best_child()
                r, c          = node.move
                cp_me, cp_opp = make_move(b, r, c, to_move, dsu_me, dsu_opp, size)
                path.append((node, r, c, cp_me, cp_opp))
                to_move = 3 - to_move
                if dsu_me.win():
                    winner = 1; break
                if dsu_opp.win():
                    winner = 2; break

            # EXPAND
            if not winner and node.untried_moves:
                r, c = choice(node.untried_moves)
                node.untried_moves.remove((r, c))
                cp_me, cp_opp = make_move(b, r, c, to_move, dsu_me, dsu_opp, size)

                if dsu_me.win():    winner = 1
                elif dsu_opp.win(): winner = 2

                child_free = [x for x in node.free_cells if x != (r, c)]
                child = MCTSNode(
                    move=(r, c), player=to_move,
                    untried_moves=child_free[:], free_cells=child_free,
                    parent=node,
                )
                node.children.append(child)
                path.append((child, r, c, cp_me, cp_opp))
                node    = child
                to_move = 3 - to_move

            # SIMULATE (random playout)
            if not winner:
                sim_path    = []
                sim_cells   = node.free_cells[:]
                shuffle(sim_cells)
                sim_to_move = to_move

                for r2, c2 in sim_cells:
                    cp_me, cp_opp = make_move(b, r2, c2, sim_to_move, dsu_me, dsu_opp, size)
                    sim_path.append((r2, c2, cp_me, cp_opp))
                    if dsu_me.win():
                        winner = 1; break
                    if dsu_opp.win():
                        winner = 2; break
                    sim_to_move = 3 - sim_to_move

                for r2, c2, cp_me, cp_opp in reversed(sim_path):
                    undo_move(b, r2, c2, dsu_me, dsu_opp, cp_me, cp_opp)

            # BACKPROPAGATE
            for pnode, _, _, _, _ in reversed(path):
                pnode.visits += 1
                if pnode.player == winner:
                    pnode.wins += 1
            root.visits += 1

            # UNDO PATH
            for _, pr, pc, cp_me, cp_opp in reversed(path):
                undo_move(b, pr, pc, dsu_me, dsu_opp, cp_me, cp_opp)

        return max(root.children, key=lambda n: n.visits).move
