"""
gui.py — GUI interactiva para probar SmartPlayer en HEX
Coloca este fichero en la misma carpeta que solution.py, board.py y player.py
Ejecuta con: python gui.py

Controles:
  Clic izquierdo  → colocar ficha
  R               → reiniciar partida
  Q / Escape      → salir
"""

import tkinter as tk
from tkinter import messagebox
import threading
import math
import time

# ── Importar las implementaciones del torneo ──────────────────────────────────
from board import HexBoard
from solution import SmartPlayer

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════

BOARD_SIZE   = 11       # Cambia aquí el tamaño del tablero
HUMAN_PLAYER = 1        # 1 → humano juega izq↔der / 2 → humano juega arr↕abaj
HEX_RADIUS   = 20       # Radio de cada celda en píxeles (ajusta según tu pantalla)
PADDING      = 60       # Margen exterior del tablero

# Paleta de colores
BG           = "#0f0f18"
SURFACE      = "#16161f"
COL_EMPTY    = "#1e1e30"
COL_BORDER   = "#2a2a40"
COL_P1       = "#d94f4f"   # fichas jugador 1
COL_P1_LIGHT = "#ff9090"
COL_P2       = "#3d82e0"   # fichas jugador 2
COL_P2_LIGHT = "#7db4ff"
COL_WIN      = "#f0c040"   # camino ganador
COL_LAST     = "#ffffff"   # marca último movimiento
COL_HOVER    = "#8899cc"
COL_TEXT     = "#ccccdd"
COL_LABEL    = "#555570"
FONT_MONO    = ("Courier New", 11)
FONT_TITLE   = ("Courier New", 18, "bold")
FONT_STATUS  = ("Courier New", 12)

# ══════════════════════════════════════════════════════════════════════════════
# GEOMETRÍA HEX — even-r offset
# ══════════════════════════════════════════════════════════════════════════════

def hex_center(r, c, radius, ox, oy):
    """Centro en píxeles de la celda (r, c) con even-r layout."""
    w = math.sqrt(3) * radius
    h = 2 * radius
    x = ox + c * w + (w / 2 if r % 2 == 1 else 0) + w / 2
    y = oy + r * h * 0.75 + radius
    return x, y

def hex_corners(cx, cy, radius):
    """Lista de 6 vértices del hexágono centrado en (cx, cy)."""
    pts = []
    for i in range(6):
        angle = math.pi / 180 * (60 * i - 30)
        pts.append(cx + (radius - 1) * math.cos(angle))
        pts.append(cy + (radius - 1) * math.sin(angle))
    return pts

def pixel_to_cell(px, py, size, radius, ox, oy):
    """Convierte coordenadas de píxel al (r, c) más cercano, o None."""
    best, best_dist = None, radius * 1.1
    for r in range(size):
        for c in range(size):
            cx, cy = hex_center(r, c, radius, ox, oy)
            d = math.hypot(px - cx, py - cy)
            if d < best_dist:
                best_dist = d
                best = (r, c)
    return best

# ══════════════════════════════════════════════════════════════════════════════
# DSU simple (solo lectura, para detectar victoria y camino ganador)
# ══════════════════════════════════════════════════════════════════════════════

def get_neighbors(r, c, size):
    deltas = (
        [(-1,-1),(-1,0),(0,-1),(0,1),(1,-1),(1,0)] if r % 2 == 0
        else [(-1,0),(-1,1),(0,-1),(0,1),(1,0),(1,1)]
    )
    return [(r+dr, c+dc) for dr,dc in deltas
            if 0 <= r+dr < size and 0 <= c+dc < size]

def check_winner(board, size):
    """Devuelve 1, 2 o 0 según quién haya ganado."""
    for pid in (1, 2):
        n = size * size + 2
        parent = list(range(n))
        VS, VE = size*size, size*size+1

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
                    if c == 0:        union(idx, VS)
                    if c == size - 1: union(idx, VE)
                else:
                    if r == 0:        union(idx, VS)
                    if r == size - 1: union(idx, VE)
                for nr, nc in get_neighbors(r, c, size):
                    if board[nr][nc] == pid:
                        union(idx, nr * size + nc)

        if find(VS) == find(VE):
            return pid
    return 0

def find_win_path(board, size, pid):
    """BFS para encontrar el camino ganador. Devuelve set de índices r*size+c."""
    cells = [(r, c) for r in range(size) for c in range(size) if board[r][c] == pid]
    starts = [( r, c) for r, c in cells if (c == 0 if pid == 1 else r == 0)]
    visited, prev, queue = set(), {}, list(starts)
    for r, c in starts:
        visited.add(r * size + c)
    while queue:
        r, c = queue.pop(0)
        at_end = (c == size - 1) if pid == 1 else (r == size - 1)
        if at_end:
            path, cur = set(), r * size + c
            while cur is not None:
                path.add(cur)
                cur = prev.get(cur)
            return path
        for nr, nc in get_neighbors(r, c, size):
            k = nr * size + nc
            if k not in visited and board[nr][nc] == pid:
                visited.add(k)
                prev[k] = r * size + c
                queue.append((nr, nc))
    return set()

# ══════════════════════════════════════════════════════════════════════════════
# APLICACIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class HexGUI:
    def __init__(self, root):
        self.root      = root
        self.size      = BOARD_SIZE
        self.radius    = HEX_RADIUS
        self.ox        = PADDING
        self.oy        = PADDING
        self.human_pid = HUMAN_PLAYER
        self.ai_pid    = 3 - HUMAN_PLAYER

        root.title("HEX — SmartPlayer")
        root.configure(bg=BG)
        root.resizable(False, False)

        self._build_ui()
        self.new_game()

        root.bind("<r>", lambda e: self.new_game())
        root.bind("<R>", lambda e: self.new_game())
        root.bind("<Escape>", lambda e: root.quit())
        root.bind("<q>", lambda e: root.quit())

    # ── Construir UI ──────────────────────────────────────────────────────────

    def _build_ui(self):
        w = math.sqrt(3) * self.radius
        h = 2 * self.radius
        svgW = int(w * (self.size + 0.5) + self.ox * 2 + 20)
        svgH = int(h * 0.75 * (self.size - 1) + h + self.oy * 2 + 10)

        # Título
        tk.Label(self.root, text="HEX", font=FONT_TITLE,
                 fg=COL_TEXT, bg=BG).pack(pady=(14, 0))
        tk.Label(self.root, text="MCTS · UCB1 · EVEN-R · DSU",
                 font=("Courier New", 8), fg=COL_LABEL, bg=BG).pack()

        # Barra de estado
        self.status_var = tk.StringVar(value="")
        self.status_label = tk.Label(self.root, textvariable=self.status_var,
                 font=FONT_STATUS, fg=COL_TEXT, bg=BG,
                 width=46, anchor="center")
        self.status_label.pack(pady=(8, 0))

        # Timer en vivo
        self.timer_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.timer_var,
                 font=("Courier New", 10), fg=COL_LABEL, bg=BG,
                 width=46, anchor="center").pack(pady=(0, 4))

        # Canvas del tablero
        self.canvas = tk.Canvas(self.root, width=svgW, height=svgH,
                                bg=SURFACE, highlightthickness=0)
        self.canvas.pack(padx=20, pady=4)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_hover)
        self.canvas.bind("<Leave>", self._on_leave)

        # Historial de tiempos por jugada
        self.history_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.history_var,
                 font=("Courier New", 9), fg=COL_LABEL, bg=BG,
                 width=60, anchor="center", justify="center").pack(pady=(2, 0))

        # Controles inferiores
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(pady=(6, 14))

        btn_style = dict(font=FONT_MONO, bg="#1a1a2e", fg=COL_LABEL,
                         activebackground="#2a2a40", activeforeground=COL_TEXT,
                         relief="flat", bd=0, padx=12, pady=4, cursor="hand2")

        tk.Button(bar, text="↺  Nueva partida (R)", **btn_style,
                  command=self.new_game).pack(side="left", padx=6)

        self.size_var = tk.IntVar(value=self.size)
        for s in (5, 7, 9, 11):
            tk.Radiobutton(bar, text=f"{s}×{s}", variable=self.size_var, value=s,
                           font=FONT_MONO, bg=BG, fg=COL_LABEL,
                           selectcolor="#2a2a40", activebackground=BG,
                           command=self._change_size).pack(side="left", padx=4)

        tk.Button(bar, text="✕  Salir (Q)", **btn_style,
                  command=self.root.quit).pack(side="left", padx=6)

    # ── Estado del juego ──────────────────────────────────────────────────────

    def new_game(self):
        self.board      = [[0]*self.size for _ in range(self.size)]
        self.hex_board  = HexBoard(self.size)
        self.ai         = SmartPlayer(self.ai_pid)
        self.turn       = 1
        self.winner     = 0
        self.win_path   = set()
        self.last_move  = None
        self.hover_cell = None
        self.thinking   = False
        self.move_times = []       # lista de (jugador, segundos)
        self._think_start = None   # cuándo empezó a pensar la IA
        self._tick_job    = None   # id del after() del tick del timer
        self.timer_var.set("")
        self.history_var.set("")
        self._draw_board()
        self._update_status()

        if self.turn == self.ai_pid:
            self._schedule_ai()

    def _change_size(self):
        self.size = self.size_var.get()
        self.radius = max(18, min(38, int(360 / (self.size * math.sqrt(3)))))
        # Reconstruir canvas
        self.canvas.destroy()
        w = math.sqrt(3) * self.radius
        h = 2 * self.radius
        svgW = int(w * (self.size + 0.5) + self.ox * 2 + 20)
        svgH = int(h * 0.75 * (self.size - 1) + h + self.oy * 2 + 10)
        self.canvas = tk.Canvas(self.root, width=svgW, height=svgH,
                                bg=SURFACE, highlightthickness=0)
        self.canvas.pack(padx=20, pady=4)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_hover)
        self.canvas.bind("<Leave>", self._on_leave)
        self.new_game()

    # ── Dibujo ────────────────────────────────────────────────────────────────

    def _draw_board(self):
        self.canvas.delete("all")
        size, R = self.size, self.radius
        ox, oy  = self.ox, self.oy

        # Marcadores de borde: puntos pequeños en los bordes de cada jugador
        # Jugador 1: izquierda y derecha
        pid1_col = COL_P1 if self.human_pid == 1 else COL_P2
        pid2_col = COL_P2 if self.human_pid == 1 else COL_P1
        w = math.sqrt(3) * R

        for r in range(size):
            lx, ly = hex_center(r, 0,      R, ox, oy)
            rx, ry = hex_center(r, size-1, R, ox, oy)
            self.canvas.create_oval(lx-w*0.65-4, ly-4, lx-w*0.65+4, ly+4,
                                    fill=pid1_col, outline="")
            self.canvas.create_oval(rx+w*0.65-4, ry-4, rx+w*0.65+4, ry+4,
                                    fill=pid1_col, outline="")

        for c in range(size):
            tx, ty = hex_center(0,      c, R, ox, oy)
            bx, by = hex_center(size-1, c, R, ox, oy)
            self.canvas.create_oval(tx-4, ty-R*1.15-4, tx+4, ty-R*1.15+4,
                                    fill=pid2_col, outline="")
            self.canvas.create_oval(bx-4, by+R*1.15-4, bx+4, by+R*1.15+4,
                                    fill=pid2_col, outline="")

        # Celdas
        for r in range(size):
            for c in range(size):
                self._draw_cell(r, c)

        # Leyenda
        self._draw_legend()

    def _draw_cell(self, r, c):
        size, R = self.size, self.radius
        cx, cy  = hex_center(r, c, R, self.ox, self.oy)
        val     = self.board[r][c]
        idx     = r * size + c
        is_win  = idx in self.win_path
        is_last = self.last_move == (r, c)
        is_hov  = self.hover_cell == (r, c)
        can_click = (not self.winner and not self.thinking
                     and val == 0 and self.turn == self.human_pid)

        # Color de relleno
        if is_win:
            fill = COL_WIN
        elif val == 1:
            fill = COL_P1
        elif val == 2:
            fill = COL_P2
        elif is_hov and can_click:
            fill = COL_HOVER
        else:
            fill = COL_EMPTY

        # Borde
        if is_win:
            outline, width = "#ffe060", 2
        elif is_last:
            outline, width = COL_LAST, 2
        elif is_hov and can_click:
            outline, width = "#8899dd", 1
        else:
            outline, width = COL_BORDER, 1

        tag = f"cell_{r}_{c}"
        self.canvas.delete(tag)
        pts = hex_corners(cx, cy, R)
        self.canvas.create_polygon(pts, fill=fill, outline=outline,
                                   width=width, tags=tag)

        # Punto central para última jugada
        if is_last and val:
            col = "white" if not is_win else "#333"
            self.canvas.create_oval(cx-R*0.2, cy-R*0.2,
                                    cx+R*0.2, cy+R*0.2,
                                    fill=col, outline="", tags=tag)

    def _draw_legend(self):
        self.canvas.delete("legend")
        x, y = self.ox, self.oy // 2 - 4
        pid1_col = COL_P1 if self.human_pid == 1 else COL_P2
        pid2_col = COL_P2 if self.human_pid == 1 else COL_P1
        dir1 = "izq ↔ der" if self.human_pid == 1 else "arr ↕ abaj"
        dir2 = "arr ↕ abaj" if self.human_pid == 1 else "izq ↔ der"

        self.canvas.create_oval(x,   y-5, x+10, y+5, fill=pid1_col, outline="", tags="legend")
        self.canvas.create_text(x+16, y, text=f"Tú ({dir1})",
                                anchor="w", fill=COL_TEXT,
                                font=("Courier New", 9), tags="legend")

        self.canvas.create_oval(x+140, y-5, x+150, y+5, fill=pid2_col, outline="", tags="legend")
        self.canvas.create_text(x+156, y, text=f"IA ({dir2})",
                                anchor="w", fill=COL_TEXT,
                                font=("Courier New", 9), tags="legend")

    def _update_status(self):
        if self.winner:
            if self.winner == self.human_pid:
                msg, col = "¡Ganaste! 🎉", "#6effa0"
            else:
                msg, col = "Ganó la IA 🤖", "#ff7777"
        elif self.thinking:
            msg, col = "IA pensando…", COL_P2_LIGHT
        elif self.turn == self.human_pid:
            col = COL_P1_LIGHT if self.human_pid == 1 else COL_P2_LIGHT
            msg = "Tu turno — haz clic en una celda"
        else:
            msg, col = "", COL_TEXT
        self.status_var.set(msg)
        self.status_label.configure(fg=col)

    def _update_history(self):
        """Construye la línea de historial de tiempos."""
        if not self.move_times:
            self.history_var.set("")
            return
        who = {self.human_pid: "Tú", self.ai_pid: "IA"}
        parts = []
        for i, (pid, secs) in enumerate(self.move_times):
            label = who.get(pid, f"P{pid}")
            parts.append(f"#{i+1} {label} {secs:.2f}s")
        # Mostrar solo los últimos 6 movimientos para no desbordar
        shown = parts[-6:]
        self.history_var.set("  ·  ".join(shown))

    def _tick_timer(self):
        """Actualiza el contador de tiempo en vivo cada 100ms."""
        if not self.thinking or self._think_start is None:
            return
        elapsed = time.time() - self._think_start
        self.timer_var.set(f"⏱  {elapsed:.1f}s")
        self._tick_job = self.root.after(100, self._tick_timer)

    def _set_status_color(self, col):
        pass  # ya no se usa

    # ── Eventos ───────────────────────────────────────────────────────────────

    def _on_click(self, event):
        if self.winner or self.thinking or self.turn != self.human_pid:
            return
        cell = pixel_to_cell(event.x, event.y, self.size,
                              self.radius, self.ox, self.oy)
        if cell is None:
            return
        r, c = cell
        if self.board[r][c] != 0:
            return
        self._place(r, c, self.human_pid)

    def _on_hover(self, event):
        cell = pixel_to_cell(event.x, event.y, self.size,
                              self.radius, self.ox, self.oy)
        if cell == self.hover_cell:
            return
        old = self.hover_cell
        self.hover_cell = cell
        if old:
            self._draw_cell(*old)
        if cell:
            self._draw_cell(*cell)

    def _on_leave(self, event):
        old = self.hover_cell
        self.hover_cell = None
        if old:
            self._draw_cell(*old)

    # ── Lógica del juego ──────────────────────────────────────────────────────

    def _place(self, r, c, pid):
        # Registrar tiempo del movimiento humano (instantáneo desde perspectiva del reloj)
        if pid == self.human_pid:
            self.move_times.append((pid, 0.0))
            self.timer_var.set("")

        self.board[r][c] = pid
        self.hex_board.board[r][c] = pid
        self.last_move = (r, c)
        self._draw_cell(r, c)

        w = check_winner(self.board, self.size)
        if w:
            self.winner   = w
            self.win_path = find_win_path(self.board, self.size, w)
            self._draw_board()
            self._update_status()
            self._update_history()
            return

        self.turn = 3 - pid
        self._update_status()
        self._update_history()

        if self.turn == self.ai_pid:
            self._schedule_ai()

    def _schedule_ai(self):
        """Lanza la IA en un hilo separado para no bloquear la GUI."""
        self.thinking       = True
        self._think_start   = time.time()
        self._update_status()
        self.root.update()
        self._tick_job = self.root.after(100, self._tick_timer)
        threading.Thread(target=self._ai_move, daemon=True).start()

    def _ai_move(self):
        # Normalizar el tablero
        normalized = HexBoard(self.size)
        for r in range(self.size):
            for c in range(self.size):
                val = self.hex_board.board[r][c]
                if val == self.ai_pid:
                    normalized.board[r][c] = 1
                elif val == self.human_pid:
                    normalized.board[r][c] = 2
                else:
                    normalized.board[r][c] = 0
        move    = self.ai.play(normalized)
        elapsed = time.time() - self._think_start
        self.root.after(0, lambda: self._apply_ai_move(move, elapsed))

    def _apply_ai_move(self, move, elapsed):
        # Detener el tick del timer
        if self._tick_job:
            self.root.after_cancel(self._tick_job)
            self._tick_job = None
        self.thinking = False
        if move and not self.winner:
            self.move_times.append((self.ai_pid, elapsed))
            self.timer_var.set(f"⏱  IA tardó {elapsed:.2f}s")
            r, c = move
            self._place(r, c, self.ai_pid)


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    root = tk.Tk()
    app  = HexGUI(root)
    root.mainloop()