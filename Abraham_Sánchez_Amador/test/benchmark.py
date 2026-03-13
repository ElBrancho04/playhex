"""
benchmark.py — Torneo automático entre dos versiones de SmartPlayer.

Uso:
    Coloca solution1.py y solution2.py en el mismo directorio que este script.
    Ejecuta: python Abraham_Sánchez_Amador/test/benchmark.py

Configuración ajustable en la sección CONFIG más abajo.
"""

import importlib.util
import sys
import time
from collections import defaultdict

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

SIZES          = [5, 7, 9, 11, 15, 19, 25, 31]   # Tamaños de tablero a probar
GAMES_PER_SIZE = 4                                 # Partidas por tamaño (par → mitad empieza cada uno)
SMALL_THRESHOLD = 15                               # Tamaño máximo considerado "pequeño"

# ══════════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ══════════════════════════════════════════════════════════════════════════════

class HexBoard:
    def __init__(self, size: int):
        self.size  = size
        self.board = [[0] * size for _ in range(size)]


def get_neighbors(r, c, size):
    deltas = (
        [(-1,-1),(-1,0),(0,-1),(0,1),(1,-1),(1,0)] if r % 2 == 0
        else [(-1,0),(-1,1),(0,-1),(0,1),(1,0),(1,1)]
    )
    return [(r+dr, c+dc) for dr, dc in deltas
            if 0 <= r+dr < size and 0 <= c+dc < size]


def check_winner(board, size):
    for pid in (1, 2):
        n      = size * size + 2
        parent = list(range(n))
        VS, VE = size * size, size * size + 1

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry

        for r in range(size):
            for c in range(size):
                if board[r][c] != pid:
                    continue
                idx = r * size + c
                if pid == 1:
                    if c == 0:          union(idx, VS)
                    if c == size - 1:   union(idx, VE)
                else:
                    if r == 0:          union(idx, VS)
                    if r == size - 1:   union(idx, VE)
                for nr, nc in get_neighbors(r, c, size):
                    if board[nr][nc] == pid:
                        union(idx, nr * size + nc)

        if find(VS) == find(VE):
            return pid
    return 0


def load_player(path: str, player_id: int):
    """Carga un SmartPlayer desde un archivo .py arbitrario."""
    spec   = importlib.util.spec_from_file_location("solution_mod", path)
    module = importlib.util.module_from_spec(spec)

    # Inyectar stubs de board y player para que el módulo pueda importarlos
    board_mod        = type(sys)("board")
    board_mod.HexBoard = HexBoard
    player_mod       = type(sys)("player")

    class _Player:
        def __init__(self, pid): self.player_id = pid
        def play(self, b): raise NotImplementedError

    player_mod.Player = _Player
    sys.modules["board"]  = board_mod
    sys.modules["player"] = player_mod

    spec.loader.exec_module(module)
    return module.SmartPlayer(player_id)


def play_game(p1_path: str, p2_path: str, size: int, verbose: bool = False):
    """
    Juega una partida completa.
    p1 tiene id=1 (conecta izq↔der), p2 tiene id=2 (conecta arr↕abaj).
    El tablero se normaliza para cada jugador antes de llamar a play().
    Devuelve (winner_id, moves, duration_p1, duration_p2).
    """
    p1    = load_player(p1_path, 1)
    p2    = load_player(p2_path, 2)
    board = [[0] * size for _ in range(size)]
    turn  = 1
    moves = 0
    time1 = 0.0
    time2 = 0.0

    while True:
        hb = HexBoard(size)
        if turn == 1:
            # Tablero normalizado para p1: sus fichas=1, rival=2 (ya está así)
            hb.board = [row[:] for row in board]
            t0   = time.time()
            move = p1.play(hb)
            time1 += time.time() - t0
        else:
            # Tablero normalizado para p2: sus fichas=1, rival=2 (invertir)
            hb.board = [
                [2 if v == 1 else (1 if v == 2 else 0) for v in row]
                for row in board
            ]
            t0   = time.time()
            move = p2.play(hb)
            time2 += time.time() - t0

        r, c = move
        if board[r][c] != 0:
            # Jugada inválida → pierde
            return (3 - turn), moves, time1, time2

        board[r][c] = turn
        moves      += 1

        winner = check_winner(board, size)
        if winner:
            if verbose:
                label = "S1" if winner == 1 else "S2"
                print(f"    Gana {label} en {moves} jugadas  "
                      f"(S1: {time1:.2f}s, S2: {time2:.2f}s)")
            return winner, moves, time1, time2

        turn = 3 - turn


# ══════════════════════════════════════════════════════════════════════════════
# TORNEO
# ══════════════════════════════════════════════════════════════════════════════

def run_tournament(s1_path: str, s2_path: str):
    print("=" * 62)
    print(f"  BENCHMARK: {s1_path}  vs  {s2_path}")
    print("=" * 62)

    # Contadores globales y por categoría
    total   = defaultdict(int)   # total[key]
    by_size = defaultdict(lambda: defaultdict(int))

    for size in SIZES:
        print(f"\n── Tablero {size}×{size} ──")
        for game_idx in range(GAMES_PER_SIZE):
            # Alternar quién empieza: juegos pares → S1 empieza, impares → S2 empieza
            s1_starts = (game_idx % 2 == 0)
            if s1_starts:
                p1_path, p2_path = s1_path, s2_path
                label = "S1 empieza"
            else:
                p1_path, p2_path = s2_path, s1_path
                label = "S2 empieza"

            print(f"  Partida {game_idx+1}/{GAMES_PER_SIZE} ({label}) ... ", end="", flush=True)

            try:
                winner_id, moves, t1, t2 = play_game(p1_path, p2_path, size, verbose=True)
            except Exception as e:
                print(f"ERROR: {e}")
                total["errors"] += 1
                continue

            # winner_id es el id interno (1 o 2 del tablero de esa partida)
            # Necesitamos mapear al nombre del script
            if s1_starts:
                s1_won = (winner_id == 1)
            else:
                s1_won = (winner_id == 2)

            winner_label = "S1" if s1_won else "S2"
            starter      = "S1" if s1_starts else "S2"

            # Acumular estadísticas
            total["games"]       += 1
            by_size[size]["games"] += 1

            if s1_won:
                total["s1_wins"]         += 1
                by_size[size]["s1_wins"] += 1
            else:
                total["s2_wins"]         += 1
                by_size[size]["s2_wins"] += 1

            if s1_starts:
                total["s1_started"] += 1
                if s1_won: total["s1_wins_when_started"] += 1
            else:
                total["s2_started"] += 1
                if not s1_won: total["s2_wins_when_started"] += 1

            if size <= SMALL_THRESHOLD:
                total["small_games"] += 1
                if s1_won: total["s1_small_wins"] += 1
            else:
                total["large_games"] += 1
                if s1_won: total["s1_large_wins"] += 1

            total["total_moves"] += moves
            total["total_t1"]    += t1
            total["total_t2"]    += t2

    # ── Reporte final ─────────────────────────────────────────────────────────
    g = total["games"]
    if g == 0:
        print("\nNo se completó ninguna partida.")
        return

    print("\n" + "=" * 62)
    print("  RESULTADOS GLOBALES")
    print("=" * 62)

    def pct(num, den): return f"{100*num/den:.1f}%" if den > 0 else "N/A"

    print(f"  Partidas jugadas   : {g}")
    print(f"  Victorias S1       : {total['s1_wins']}  ({pct(total['s1_wins'], g)})")
    print(f"  Victorias S2       : {total['s2_wins']}  ({pct(total['s2_wins'], g)})")
    print()
    print(f"  S1 gana al empezar : {pct(total['s1_wins_when_started'], total['s1_started'])}"
          f"  ({total['s1_wins_when_started']}/{total['s1_started']})")
    print(f"  S2 gana al empezar : {pct(total['s2_wins_when_started'], total['s2_started'])}"
          f"  ({total['s2_wins_when_started']}/{total['s2_started']})")
    print()
    print(f"  S1 en tableros ≤{SMALL_THRESHOLD}  : {pct(total['s1_small_wins'], total['small_games'])}"
          f"  ({total['s1_small_wins']}/{total['small_games']})")
    print(f"  S1 en tableros >{SMALL_THRESHOLD}  : {pct(total['s1_large_wins'], total['large_games'])}"
          f"  ({total['s1_large_wins']}/{total['large_games']})")
    print()
    print(f"  Jugadas promedio   : {total['total_moves']/g:.1f}")
    print(f"  Tiempo medio S1/partida : {total['total_t1']/g:.2f}s")
    print(f"  Tiempo medio S2/partida : {total['total_t2']/g:.2f}s")

    print("\n── Por tamaño ──")
    print(f"  {'Tamaño':>7}  {'Partidas':>8}  {'S1 wins':>8}  {'S2 wins':>8}  {'S1 %':>6}")
    print(f"  {'-'*7}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*6}")
    for size in SIZES:
        d = by_size[size]
        if d["games"] == 0:
            continue
        print(f"  {size:>5}×{size:<2}  {d['games']:>8}  {d['s1_wins']:>8}  "
              f"{d['s2_wins']:>8}  {pct(d['s1_wins'], d['games']):>6}")

    if total["errors"]:
        print(f"\n  ⚠ Errores: {total['errors']}")

    print("=" * 62)
    winner = "S1" if total["s1_wins"] > total["s2_wins"] else (
             "S2" if total["s2_wins"] > total["s1_wins"] else "EMPATE")
    print(f"  GANADOR GLOBAL: {winner}")
    print("=" * 62)


if __name__ == "__main__":
    s1 = "Abraham_Sánchez_Amador/test/solution1.py"
    s2 = "Abraham_Sánchez_Amador/test/solution2.py"
    run_tournament(s1, s2)
