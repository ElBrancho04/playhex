import heapq
import time
from math import log, sqrt
from random import choice, random
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
_CENTRAL: dict[int, frozenset] = {}


def resistance_dijkstra(
    board: list[list[int]],
    player_id: int,
    size: int,
) -> tuple[set[tuple[int, int]], float]:
    VSTART = size * size
    VEND   = size * size + 1
    total  = size * size + 2
    INF    = float('inf')

    def cell_cost(idx: int) -> float:
        if idx >= VSTART:
            return 0.0
        r, c = divmod(idx, size)
        val  = board[r][c]
        if val == player_id: return 0.0
        if val == 0: return 1.0
        return INF

    def neighbors(idx: int) -> list[int]:
        if idx == VSTART:
            return (
                [r * size for r in range(size)] if player_id == 1
                else [c for c in range(size)]
            )
        if idx == VEND:
            return (
                [r * size + size - 1 for r in range(size)] if player_id == 1
                else [(size - 1) * size + c for c in range(size)]
            )
        r, c   = divmod(idx, size)
        result = [nr * size + nc for nr, nc in _NBRS[size][r][c]]
        if player_id == 1:
            if c == 0:        result.append(VSTART)
            if c == size - 1: result.append(VEND)
        else:
            if r == 0:        result.append(VSTART)
            if r == size - 1: result.append(VEND)
        return result

    def dijkstra(source: int) -> list[float]:
        dist         = [INF] * total
        dist[source] = 0.0
        heap         = [(0.0, source)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            for v in neighbors(u):
                cost_v = cell_cost(v)
                if cost_v == INF:
                    continue
                nd = d + cost_v
                if nd < dist[v]:
                    dist[v] = nd
                    heapq.heappush(heap, (nd, v))
        return dist

    dist_start = dijkstra(VSTART)
    dist_end   = dijkstra(VEND)
    shortest   = dist_start[VEND]

    if shortest == INF:
        return set(), INF

    # Two-distance toward VEND: assume opponent blocks the single best onward neighbor.
    # two_dist_end[v] = cell_cost(v) + second_min{dist_end[u] : u in neighbors(v)}
    two_dist_end        = [INF] * total
    two_dist_end[VEND]  = 0.0
    for idx in range(total):
        if idx == VEND:
            continue
        cost = cell_cost(idx)
        if cost == INF:
            continue
        nbr_d = sorted(dist_end[v] for v in neighbors(idx) if dist_end[v] < INF)
        if len(nbr_d) >= 2:
            two_dist_end[idx] = cost + nbr_d[1]
        elif nbr_d:
            two_dist_end[idx] = cost + nbr_d[0]

    # Path value through cell v = dist_start[v] + two_dist_end[v] - cell_cost(v)
    two_shortest = min(
        (dist_start[r * size + c] + two_dist_end[r * size + c] - 1.0
         for r in range(size) for c in range(size)
         if board[r][c] == 0
         and dist_start[r * size + c] < INF
         and two_dist_end[r * size + c] < INF),
        default=INF,
    )

    if two_shortest >= INF:
        return set(), shortest

    return {
        (r, c)
        for r in range(size)
        for c in range(size)
        if board[r][c] == 0
        and dist_start[r * size + c] + two_dist_end[r * size + c] - 1.0 == two_shortest
    }, shortest


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
    me_id: int,
    size: int,
) -> tuple[int, int]:
    board[r][c] = cell_value
    dsu        = dsu_me if cell_value == me_id else dsu_opp
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
        exploitation = self.wins / self.visits
        log_term     = log(self.parent.visits) / self.visits
        # Varianza observada estimada, acotada por el máximo teórico 1/4
        variance     = exploitation - exploitation ** 2 + sqrt(2 * log_term)
        return exploitation + sqrt(log_term * min(0.25, variance))

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
            cr, cc  = size // 2 + 1, size // 2 + 1
            rad     = size // 3
            central = []
            for dr in range(-rad, rad + 1):
                c_rad = rad - abs(dr)
                for dc in range(-c_rad, c_rad + 1):
                    r, c = cr + dr, cc + dc
                    if 0 <= r < size and 0 <= c < size:
                        central.append((r, c))
            _CENTRAL[size] = frozenset(central)

        # Build DSUs incrementally from the existing board state
        dsu_me  = ReversibleDSU(size, self.player_id)
        dsu_opp = ReversibleDSU(size, 3 - self.player_id)
        for r in range(size):
            for c in range(size):
                if b[r][c] != 0:
                    make_move(b, r, c, b[r][c], dsu_me, dsu_opp, self.player_id, size)

        free = [(r, c) for r in range(size) for c in range(size) if b[r][c] == 0]

        if len(free) == 1:
            return free[0]

        # Forced moves
        # Pass 1: immediate winning move for me
        for r, c in free:
            cp = make_move(b, r, c, self.player_id, dsu_me, dsu_opp, self.player_id, size)
            won = dsu_me.win()
            undo_move(b, r, c, dsu_me, dsu_opp, *cp)
            if won:
                return (r, c)

        # Pass 2: block opponent's immediate winning move
        for r, c in free:
            cp = make_move(b, r, c, 3 - self.player_id, dsu_me, dsu_opp, self.player_id, size)
            opp_wins = dsu_opp.win()
            undo_move(b, r, c, dsu_me, dsu_opp, *cp)
            if opp_wins:
                return (r, c)

        is_opening = (size * size - len(free)) <= size // 2
        central    = _CENTRAL.get(size, frozenset())

        crit1, d1 = resistance_dijkstra(b, self.player_id, size)
        crit2, d2 = resistance_dijkstra(b, 3-self.player_id, size)
        total_d   = d1 + d2
        p1_off    = (d2 / total_d) if total_d > 0 else 0.5

        root = MCTSNode(
            move=None, player=None,
            untried_moves=free[:], free_cells=free[:],
            parent=None,
        )

        deadline = time.time() + 5.0 - (0.35 + 0.002 * size)

        def _pop_random(lst):
            idx      = int(random() * len(lst))
            val      = lst[idx]
            lst[idx] = lst[-1]
            lst.pop()
            return val

        while time.time() < deadline:
            node    = root
            # path entries: (node, r, c, cp_me, cp_opp)
            path    = []
            to_move = self.player_id
            winner  = 0

            # SELECT
            while node.children:
                max_allowed_children = 2 + int(5 * sqrt(node.visits))
                if node.untried_moves and len(node.children) < max_allowed_children:
                    break
                    
                node          = node.best_child()
                r, c          = node.move
                cp_me, cp_opp = make_move(b, r, c, to_move, dsu_me, dsu_opp, self.player_id, size)
                path.append((node, r, c, cp_me, cp_opp))
                to_move = 3 - to_move
                if dsu_me.win():
                    winner = self.player_id; break
                if dsu_opp.win():
                    winner = 3 - self.player_id; break

            # EXPAND
            if not winner and node.untried_moves:
                depth_factor = max(0.0, 1.0 - 1.5 * len(path) / len(free)) if free else 0.0
                chosen_move = None
                
                if is_opening and random() < 0.85:
                    preferred = [m for m in node.untried_moves if m in central]
                    if preferred:
                        chosen_move = choice(preferred)
                        
                elif random() < (0.7 * depth_factor):
                    preferred = [m for m in node.untried_moves if m in crit1 or m in crit2]
                    if preferred:
                        chosen_move = choice(preferred)
                        
                if chosen_move is None:
                    chosen_move = choice(node.untried_moves)
                    
                r, c = chosen_move
                node.untried_moves.remove((r, c))
                cp_me, cp_opp = make_move(b, r, c, to_move, dsu_me, dsu_opp, self.player_id, size)

                if dsu_me.win():    winner = self.player_id
                elif dsu_opp.win(): winner = 3 - self.player_id

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

            # SIMULATE (Dijkstra-guided playout with decaying confidence and forced moves)
            if not winner:
                sim_path    = []
                sim_to_move = to_move
                both_pool = []; only1_pool = []; only2_pool = []; other_pool = []
                for cell in node.free_cells:
                    in1 = cell in crit1
                    in2 = cell in crit2
                    if in1 and in2:   both_pool.append(cell)
                    elif in1:         only1_pool.append(cell)
                    elif in2:         only2_pool.append(cell)
                    else:             other_pool.append(cell)
                steps_total  = len(node.free_cells)
                crit_total   = len(both_pool) + len(only1_pool) + len(only2_pool)
                crit_played  = 0
                forced_threshold = size * size // 3
                depth_factor = max(0.0, 1.0 - 1.5 * len(path) / len(free)) if free else 0.0
                forced      = None
                last_r2, last_c2 = (path[-1][1], path[-1][2]) if path else (-1, -1)

                while both_pool or only1_pool or only2_pool or other_pool:
                    remaining = len(both_pool) + len(only1_pool) + len(only2_pool) + len(other_pool)

                    # Forced move: single O(6x6) DSU-only pass, victory > block
                    if remaining <= forced_threshold and last_r2 >= 0:
                        dsu_cur  = dsu_me  if sim_to_move == self.player_id else dsu_opp
                        dsu_opp_ = dsu_opp if sim_to_move == self.player_id else dsu_me
                        own_val  = sim_to_move
                        opp_val  = 3 - sim_to_move
                        rs_cur   = dsu_cur.find(dsu_cur.VSTART)
                        re_cur   = dsu_cur.find(dsu_cur.VEND)
                        rs_opp   = dsu_opp_.find(dsu_opp_.VSTART)
                        re_opp   = dsu_opp_.find(dsu_opp_.VEND)
                        block    = None
                        for nr, nc in _NBRS[size][last_r2][last_c2]:
                            if b[nr][nc] != 0:
                                continue
                            ts = te = fs = fe = False
                            for xr, xc in _NBRS[size][nr][nc]:
                                v = b[xr][xc]
                                if v == own_val:
                                    rr = dsu_cur.find(xr * size + xc)
                                    if rr == rs_cur: ts = True
                                    if rr == re_cur: te = True
                                elif v == opp_val:
                                    rr = dsu_opp_.find(xr * size + xc)
                                    if rr == rs_opp: fs = True
                                    if rr == re_opp: fe = True
                            if ts and te:
                                forced = (nr, nc); break
                            if fs and fe and block is None:
                                block = (nr, nc)
                        if forced is None:
                            forced = block

                    if forced is not None:
                        r2, c2 = forced
                        forced = None
                        for pool in (both_pool, only1_pool, only2_pool, other_pool):
                            if (r2, c2) in pool:
                                pool.remove((r2, c2)); break
                        cp_me, cp_opp = make_move(b, r2, c2, sim_to_move, dsu_me, dsu_opp, self.player_id, size)
                        sim_path.append((r2, c2, cp_me, cp_opp))
                        last_r2, last_c2 = r2, c2
                        if dsu_me.win():
                            winner = self.player_id; break
                        if dsu_opp.win():
                            winner = 3 - self.player_id; break
                        sim_to_move = 3 - sim_to_move
                        continue

                    # Decaying confidence scaled by depth_factor (trust in root Dijkstra)
                    steps_played = steps_total - remaining
                    ratio_total  = steps_played / steps_total if steps_total > 0 else 1.0
                    ratio_crit   = (crit_played / crit_total) if crit_total > 0 else 1.0
                    p_crit       = max(0.0, depth_factor * (1.0 - 1.5 * max(ratio_crit, ratio_total)))

                    any_crit = both_pool or only1_pool or only2_pool
                    if any_crit and (not other_pool or random() < p_crit):
                        if both_pool:
                            chosen = _pop_random(both_pool)
                        else:
                            p_off              = p1_off if sim_to_move == self.player_id else 1.0 - p1_off
                            off_pool, def_pool = (
                                (only1_pool, only2_pool) if sim_to_move == self.player_id
                                else (only2_pool, only1_pool)
                            )
                            if off_pool and (not def_pool or random() < p_off):
                                chosen = _pop_random(off_pool)
                            elif def_pool:
                                chosen = _pop_random(def_pool)
                            else:
                                chosen = _pop_random(both_pool)
                    else:
                        chosen = _pop_random(other_pool)

                    r2, c2 = chosen
                    if (r2, c2) in crit1 or (r2, c2) in crit2:
                        crit_played += 1
                    cp_me, cp_opp = make_move(b, r2, c2, sim_to_move, dsu_me, dsu_opp, self.player_id, size)
                    sim_path.append((r2, c2, cp_me, cp_opp))
                    last_r2, last_c2 = r2, c2
                    if dsu_me.win():
                        winner = self.player_id; break
                    if dsu_opp.win():
                        winner = 3 - self.player_id; break
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
