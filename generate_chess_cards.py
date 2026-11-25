"""
Generador v10 - Mazo de 60 cartas fisicas (A anverso + B reverso espejo = 120 imagenes)
        con CADA PIEZA DIBUJADA DOS VECES por casilla, en diagonal "\\":
          - copia 1: girada 45 grados  (cabeza hacia arriba-izquierda)
          - copia 2: girada 225 grados (cabeza hacia abajo-derecha)
        Las bases quedan enfrentadas en el centro de la casilla, asi cada jugador
        (sentados frente a frente a lo largo de la diagonal) ve una pieza "de pie".

Estructura del script (los numeros coinciden con la explicacion paso a paso):
  1. Configuracion y constantes
  2. Geometria del tablero (rotar, espejar)
  3. Reglas del juego (alfil oscuro, caballo fuera del centro)
  4. Dibujo de una pieza (sprite) y de una carta
  5. Universo de cartas validas y parejas espejo
  6. Eleccion del mazo (semilla fija)
  7. Verificaciones
  8. Guardado de imagenes y manifiesto
"""
import itertools, json, math, os, random
from PIL import Image, ImageDraw, ImageFont

# ============================================================================
# 1. CONFIGURACION
# ============================================================================
SEED       = 2026          # misma semilla que v9 -> mismo mazo de 60 cartas
N_PAREJAS  = 60            # 60 cartas fisicas (cada una con A y B)
OUT        = "output_v10"

PIECES  = ["Rey", "Reina", "Torre", "Caballo", "Alfil"]      # orden fijo de las piezas
SYMBOLS = {"Rey": "♔", "Reina": "♕", "Torre": "♖",
           "Caballo": "♘", "Alfil": "♗"}
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DARK_SQUARES = {0, 2, 4, 6, 8}                               # esquinas + centro

CARD_SIZE, CORNER_R, CARD_BG = 540, 36, (210, 170, 150)
CELL      = 160                                              # lado de una casilla (px)
BOARD_PX  = CELL * 3
BOARD_OFF = (CARD_SIZE - BOARD_PX) // 2                      # margen del tablero
DARK_C, LIGHT_C = (140, 80, 70), (240, 225, 200)
CELL_COLORS = {p: (DARK_C if p in DARK_SQUARES else LIGHT_C) for p in range(9)}

# Parametros del dibujo en diagonal
PIECE_H   = 78      # altura objetivo de cada pieza (px)
PIECE_MAXW = 58     # ancho maximo de cada pieza (px)
GAP       = 6       # separacion entre las dos bases en el centro (px)
ANGLES    = {"\\": (45, 225),     # eje "\"  : cabezas hacia arriba-izq / abajo-der
             "/":  (-45, 135)}    # eje "/"  : (por si se quiere el otro sentido)
DIAG_A, DIAG_B = "\\", "\\"       # diagonal usada en el anverso A y en el reverso B

# ============================================================================
# 2. GEOMETRIA DEL TABLERO  (casillas 0-8, izquierda->derecha, arriba->abajo)
# ============================================================================
def rc(p):      return divmod(p, 3)            # casilla -> (fila, columna)
def P(r, c):    return r * 3 + c               # (fila, columna) -> casilla
def rot90(p):   r, c = rc(p); return P(c, 2 - r)
def flip_h(p):  r, c = rc(p); return P(r, 2 - c)   # espejo: columna izq <-> der

def apply(f, arr):
    """arr[i] = casilla de la pieza i. Mueve cada pieza CON su casilla."""
    return tuple(f(p) for p in arr)

def rotations(arr):
    out = [arr]
    for _ in range(3):
        out.append(apply(rot90, out[-1]))
    return out

def canon(arr):
    """Representante de la clase de rotacion (el menor de las 4 rotaciones)."""
    return min(rotations(arr))

# ============================================================================
# 3. REGLAS DEL JUEGO
# ============================================================================
def is_valid(arr):
    # arr[3] = caballo, arr[4] = alfil
    return arr[4] in DARK_SQUARES and arr[3] != 4

# ============================================================================
# 4. DIBUJO
# ============================================================================
def piece_sprite(name, color, shadow):
    """Dibuja UNA pieza (con sombra) sobre transparente, la recorta y la escala."""
    font = ImageFont.truetype(FONT_PATH, 400)          # grande: se reduce sin perder calidad
    S = 700
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    sym = SYMBOLS[name]
    bb = d.textbbox((0, 0), sym, font=font)
    ox = (S - (bb[2] - bb[0])) // 2 - bb[0]
    oy = (S - (bb[3] - bb[1])) // 2 - bb[1]
    d.text((ox + 12, oy + 12), sym, font=font, fill=shadow)   # sombra
    d.text((ox, oy), sym, font=font, fill=color)              # pieza
    layer = layer.crop(layer.getbbox())                       # quitar bordes vacios
    scale = min(PIECE_H / layer.height, PIECE_MAXW / layer.width)
    return layer.resize((max(1, round(layer.width * scale)),
                         max(1, round(layer.height * scale))), Image.LANCZOS)

def paste_piece(card, name, cell_box, dark, angle):
    """Pega una copia de la pieza girada 'angle' grados (antihorario) en la casilla."""
    color  = (30, 15, 10)    if dark else (50, 30, 20)
    shadow = (180, 120, 100) if dark else (160, 130, 110)
    sprite = piece_sprite(name, color, shadow)
    w, h = sprite.size
    # direccion hacia donde mira la "cabeza" de la pieza tras girar 'angle' (coords de pantalla)
    a = math.radians(angle)
    ux, uy = -math.sin(a), -math.cos(a)
    x0, y0, x1, y1 = cell_box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    dist = h / 2 + GAP / 2                    # la base queda a GAP/2 del centro
    px, py = cx + ux * dist, cy + uy * dist   # centro de la pieza
    rot = sprite.rotate(angle, expand=True, resample=Image.BICUBIC)
    rw, rh = rot.size
    left, top = round(px - rw / 2), round(py - rh / 2)
    # comprobacion: la parte visible de la pieza debe quedar dentro de la casilla
    vb = rot.getbbox()
    assert left + vb[0] >= x0 + 2 and left + vb[2] <= x1 - 2 and \
           top + vb[1] >= y0 + 2 and top + vb[3] <= y1 - 2, \
           f"{name} se sale de la casilla {cell_box}"
    card.alpha_composite(rot, dest=(left, top))

def make_card(arr, diag="\\"):
    """arr[i] = casilla de la pieza PIECES[i]. Devuelve la imagen de la carta."""
    piece_at = {arr[i]: PIECES[i] for i in range(5)}
    card = Image.new("RGBA", (CARD_SIZE, CARD_SIZE), CARD_BG + (255,))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, CARD_SIZE - 1, CARD_SIZE - 1], radius=CORNER_R,
                        outline=(80, 50, 40), width=4)
    # a) casillas
    boxes = {}
    for pos in range(9):
        r, c = rc(pos)
        x0, y0 = BOARD_OFF + c * CELL, BOARD_OFF + r * CELL
        boxes[pos] = (x0, y0, x0 + CELL, y0 + CELL)
        d.rectangle([x0, y0, x0 + CELL - 1, y0 + CELL - 1], fill=CELL_COLORS[pos])
    # b) cuadricula
    for i in range(4):
        d.line([(BOARD_OFF + i * CELL, BOARD_OFF), (BOARD_OFF + i * CELL, BOARD_OFF + BOARD_PX - 1)],
               fill=(90, 55, 45), width=3)
        d.line([(BOARD_OFF, BOARD_OFF + i * CELL), (BOARD_OFF + BOARD_PX - 1, BOARD_OFF + i * CELL)],
               fill=(90, 55, 45), width=3)
    # c) piezas: dos copias por casilla (45 y 225 grados)
    for pos, name in piece_at.items():
        for angle in ANGLES[diag]:
            paste_piece(card, name, boxes[pos], pos in DARK_SQUARES, angle)
    # d) esquinas redondeadas
    mask = Image.new("L", (CARD_SIZE, CARD_SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, CARD_SIZE - 1, CARD_SIZE - 1],
                                           radius=CORNER_R, fill=255)
    card.putalpha(mask)
    return card

# ============================================================================
# 5. UNIVERSO DE CARTAS Y PAREJAS ESPEJO
# ============================================================================
validas = [a for a in itertools.permutations(range(9), 5) if is_valid(a)]   # 7,560
clases  = sorted({canon(a) for a in validas})                               # 1,890
print(f"Disposiciones validas: {len(validas)}")
print(f"Clases distintas bajo rotacion: {len(clases)}")

parejas = set()
for c in clases:
    m = canon(apply(flip_h, c))                 # clase del espejo de c
    assert m != c, "clase simetrica consigo misma (no esperado)"
    parejas.add(tuple(sorted((c, m))))
parejas = sorted(parejas)                       # 945
print(f"Parejas espejo disponibles: {len(parejas)}")

# ============================================================================
# 6. ELECCION DEL MAZO (semilla fija -> reproducible)
# ============================================================================
rng = random.Random(SEED)
elegidas = rng.sample(parejas, N_PAREJAS)
mazo = []
for cA, _ in elegidas:
    A = rng.choice(rotations(cA))               # orientacion de la carta A
    B = apply(flip_h, A)                        # B = espejo horizontal exacto de A
    mazo.append((A, B))

# ============================================================================
# 7. VERIFICACIONES
# ============================================================================
todas = [x for par in mazo for x in par]
assert len(todas) == 120
assert len({canon(x) for x in todas}) == 120, "hay cartas iguales bajo rotacion"
assert all(is_valid(x) for x in todas), "carta invalida"
assert all(apply(flip_h, A) == B and apply(flip_h, B) == A for A, B in mazo)
print("OK: 60 cartas (120 imagenes A+B), todas distintas bajo rotacion")
print("OK: alfil siempre en casilla oscura, caballo nunca en el centro")
print("OK: B = espejo de A y A = espejo de B en las 60 cartas")

# ============================================================================
# 8. GUARDADO
# ============================================================================
os.makedirs(OUT, exist_ok=True)
manifest = []
for i, (A, B) in enumerate(mazo, 1):
    make_card(A, DIAG_A).save(os.path.join(OUT, f"tarjeta_{i:02d}_a.png"))
    make_card(B, DIAG_B).save(os.path.join(OUT, f"tarjeta_{i:02d}_b.png"))
    manifest.append({"par": i,
                     "a": {PIECES[k]: A[k] for k in range(5)},
                     "b": {PIECES[k]: B[k] for k in range(5)}})
with open(os.path.join(OUT, "manifiesto.json"), "w", encoding="utf-8") as f:
    json.dump({"semilla": SEED,
               "transformacion_b": "espejo horizontal (col -> 2-col)",
               "dibujo": "cada pieza duplicada en diagonal, giros de 45 y 225 grados",
               "casillas": "0-8 de izquierda a derecha, arriba a abajo",
               "pares": manifest}, f, ensure_ascii=False, indent=2)
print(f"120 imagenes (60 cartas A+B) guardadas en '{OUT}/'")
