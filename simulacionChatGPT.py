# ============================================================
# Simulación de un CRT (Cathode Ray Tube) con tres vistas:
#  - Vista Superior (X vs Z)
#  - Vista Lateral (Y vs Z)
#  - Pantalla (X vs Y)
#
# Características principales:
#  - Dos modos de operación: Lissajous (señales sinusoidales en placas) y CRT manual (voltajes DC).
#  - Control de parámetros físicos por el usuario (Va, Vx, Vy, fX, fY, fases, persistencia).
#  - Persistencia tipo fósforo con decaimiento exponencial.
#  - Vistas Top/Side con rayo por tramos (recto hasta las placas y luego deflectado).
# ============================================================
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider, Button
from collections import deque
from dataclasses import dataclass, field

# =============== Physics + UI parameters ===============

@dataclass
class Geometry:
    # Simple tube geometry (meters); choose plausible defaults
    plate_len: float = 0.05     # l
    plate_gap: float = 0.006    # d
    drift: float = 0.20         # L (plates -> screen)
    z_screen: float = 0.30      # total Z length for drawing

@dataclass
class Ranges:
    Va_min: float = 0.2   # accel voltage [arbitrary units] (>0)
    Va_max: float = 2.0
    Vp_max: float = 10.0  # +/- VM for deflection plates
    f_min: float = 0.1
    f_max: float = 10.0
    tau_min: float = 0.02   # persistence seconds
    tau_max: float = 1.20

GEO = Geometry()
RNG = Ranges()

SCREEN_SCALE = 10.0  # maps meters-ish to plot units
DT = 0.02            # simulation step (s)
DT_LISS = 0.01       # finer step for smooth Lissajous
TIME_SCALE = 1.75    # speed multiplier for perceived motion

def deflection_gain(Va: float, plate_len=GEO.plate_len, gap=GEO.plate_gap, drift=GEO.drift):
    """
    Ganancia de deflexión electrostática ~ (Vp/Va)*K.
    K ≈ [l*(L + l/2)]/(2*d), en metros; multiplicamos por SCREEN_SCALE para encajar en ejes.
    Se limita Va para evitar divisiones casi por cero.
    """
    Va_eff = max(Va, 0.05)
    K_meters = (plate_len * (drift + plate_len/2.0)) / (2.0 * gap)
    return SCREEN_SCALE * K_meters / Va_eff

def brightness_from_Va(Va: float):
    # Brillo aproximado del punto: mapeo gamma simple de Va -> [0.25, 1.0]
    Va_clamped = np.clip(Va, RNG.Va_min, RNG.Va_max)
    x = (Va_clamped - RNG.Va_min) / (RNG.Va_max - RNG.Va_min + 1e-9)
    return 0.25 + 0.75 * (x ** 0.6)  # in [0.25, 1.0]

# =============== State containers ===============

@dataclass
class Controls:
    Va: float = 0.8
    Vx: float = 3.0     # in CRT mode: DC plate voltages; in Lissajous: amplitudes
    Vy: float = 3.0
    fx: float = 2.0
    fy: float = 3.0
    phx: float = 0.0
    phy: float = np.pi/2
    tau: float = 0.30   # persistence seconds

@dataclass
class Runtime:
    t: float = 0.0
    mode_lissajous: bool = True
    paused: bool = False
    trail: deque = field(default_factory=lambda: deque(maxlen=2000))
    # last computed positions (for ray + screen)
    x: float = 0.0
    y: float = 0.0
    dragging: bool = False

C = Controls()
S = Runtime()

# =============== Figuras y ejes ===============

fig, axes = plt.subplots(1, 3, figsize=(15, 6))
plt.subplots_adjust(left=0.07, right=0.97, top=0.90, bottom=0.40, wspace=0.30)

# Top view (X vs Z): Z horizontal, X vertical
ax_top = axes[0]
ax_top.set_xlim(0, GEO.z_screen)
ax_top.set_ylim(-SCREEN_SCALE, SCREEN_SCALE)
ax_top.set_xlabel("Z (dirección del haz)")
ax_top.set_ylabel("X (deflexión horizontal)")
ax_top.set_title("VISTA SUPERIOR (desde arriba)")

# Side view (Y vs Z): Z horizontal, Y vertical
ax_side = axes[1]
ax_side.set_xlim(0, GEO.z_screen)
ax_side.set_ylim(-SCREEN_SCALE, SCREEN_SCALE)
ax_side.set_xlabel("Z (dirección del haz)")
ax_side.set_ylabel("Y (deflexión vertical)")
ax_side.set_title("VISTA LATERAL (de lado)")

# Screen view (X vs Y): front
ax_screen = axes[2]
ax_screen.set_xlim(-SCREEN_SCALE, SCREEN_SCALE)
ax_screen.set_ylim(-SCREEN_SCALE, SCREEN_SCALE)
ax_screen.set_xlabel("X")
ax_screen.set_ylabel("Y")
ax_screen.set_title("PANTALLA")

# Contornos del tubo (embudo simple + placas) – cosmético
def draw_tube_guides():
    """Dibuja guías cosméticas: zona de placas y embudo del tubo en Top/Side."""
    # Plates region in Z
    z0 = 0.08; z1 = z0 + GEO.plate_len
    for ax, label in [(ax_top, "Horiz. plates"), (ax_side, "Vert. plates")]:
        ax.axvspan(z0, z1, color='0.9', alpha=0.5, ec='0.7')
        ax.text((z0+z1)/2, ax.get_ylim()[1]*0.9, label, ha='center', va='top', fontsize=9, color='0.3')
    # Funnel edges (just guide lines)
    for ax in (ax_top, ax_side):
        ax.plot([z1, GEO.z_screen], [0, 0], lw=1.0, color='0.7', ls='--')

draw_tube_guides()

def ray_poly(val):
    # Rayo por tramos: recto hasta el final de las placas y luego deflexión hasta la pantalla
    z0 = 0.08
    z1 = z0 + GEO.plate_len
    return [0.0, z1, GEO.z_screen], [0.0, 0.0, val]

# Rayos y elementos de pantalla
ray_top, = ax_top.plot([], [], lw=2)
ray_side, = ax_side.plot([], [], lw=2)
ray_top.set_antialiased(True);  ray_top.set_solid_capstyle('round');  ray_top.set_solid_joinstyle('round')
ray_side.set_antialiased(True); ray_side.set_solid_capstyle('round'); ray_side.set_solid_joinstyle('round')
# Punto de pantalla (bloom con scatter) + estela con desvanecimiento
spot = ax_screen.scatter([0], [0], s=60, alpha=0.9)
trail_scatter = ax_screen.scatter([], [], s=12, alpha=0.6)
trace_line, = ax_screen.plot([], [], lw=1.8, alpha=0.85)
trace_line.set_antialiased(True)
trace_line.set_solid_joinstyle('round')
trace_line.set_solid_capstyle('round')

# Cruz (opcional) para el centro de la pantalla
ax_screen.axhline(0, color='0.85', lw=0.8)
ax_screen.axvline(0, color='0.85', lw=0.8)

# === UI (sliders y botones) ===
def add_slider(x, y, w, h, label, vmin, vmax, vinit, step=None):
    # Crea un slider con fondo claro y devuelve el objeto Slider
    ax = plt.axes([x, y, w, h], facecolor='whitesmoke')
    return Slider(ax, label, vmin, vmax, valinit=vinit, valstep=step)

sx = 0.12; w = 0.58; h = 0.03; dy = 0.045; y0 = 0.08
s_Va  = add_slider(sx, y0+5*dy, w, h, "Va (Aceleración)", RNG.Va_min, RNG.Va_max, C.Va, 0.01)
s_Vx  = add_slider(sx, y0+4*dy, w, h, "Vx (Placas H)", -RNG.Vp_max, RNG.Vp_max, C.Vx, 0.05)
s_Vy  = add_slider(sx, y0+3*dy, w, h, "Vy (Placas V)", -RNG.Vp_max, RNG.Vp_max, C.Vy, 0.05)
s_fx  = add_slider(sx, y0+2*dy, w, h, "fX (Hz)", RNG.f_min, RNG.f_max, C.fx, 0.05)
s_fy  = add_slider(sx, y0+1*dy, w, h, "fY (Hz)", RNG.f_min, RNG.f_max, C.fy, 0.05)
s_tau = add_slider(sx, y0+0*dy, w, h, "τ (latencia s)", RNG.tau_min, RNG.tau_max, C.tau, 0.01)

# Ajusta el rango de Vx/Vy según Va, para que el usuario pueda alcanzar todo el plano
def _actualizar_rangos_voltajes():
    K = deflection_gain(C.Va)
    margin = SCREEN_SCALE * 0.95
    Vlim = float(margin / max(K, 1e-9))
    # Actualiza rango de sliders Vx/Vy a ±Vlim
    for sl in (s_Vx, s_Vy):
        sl.valmin = -Vlim
        sl.valmax = Vlim
        # Reposiciona los límites visuales del slider
        sl.ax.set_xlim(sl.valmin, sl.valmax)
        # Si el valor actual quedó fuera del nuevo rango, recórtalo
        if sl.val < sl.valmin:
            sl.set_val(sl.valmin)
        elif sl.val > sl.valmax:
            sl.set_val(sl.valmax)

_actualizar_rangos_voltajes()

# Phases
sx2 = 0.75; w2 = 0.20
s_phx = add_slider(sx2, 0.33, w2, h, "φX (rad)", -np.pi, np.pi, C.phx)
s_phy = add_slider(sx2, 0.285, w2, h, "φY (rad)", -np.pi, np.pi, C.phy)

# Buttons
b_mode_ax = plt.axes([0.75, 0.20, 0.20, 0.045])
b_pause_ax = plt.axes([0.75, 0.14, 0.20, 0.045])
b_reset_ax = plt.axes([0.75, 0.08, 0.20, 0.045])

b_mode = Button(b_mode_ax, "Modo: Lissajous", color='#e6f2ff', hovercolor='#b3daff')
b_pause = Button(b_pause_ax, "Pausar", color='#ffe6e6', hovercolor='#ffcccc')
b_reset = Button(b_reset_ax, "Reset", color='#eeeeee', hovercolor='#dddddd')

def update_labels():
    b_mode.label.set_text("Modo: Lissajous" if S.mode_lissajous else "Modo: CRT (manual)")
    b_pause.label.set_text("Reanudar" if S.paused else "Pausar")

def on_mode(event):
    S.mode_lissajous = not S.mode_lissajous
    # clear trail when switching mode (optional)
    S.trail.clear()
    update_labels()

def on_pause(event):
    S.paused = not S.paused
    update_labels()

def on_reset(event):
    S.t = 0.0
    S.trail.clear()

b_mode.on_clicked(on_mode)
b_pause.on_clicked(on_pause)
b_reset.on_clicked(on_reset)
update_labels()

# Slider callbacks
def on_slider(_):
    C.Va  = s_Va.val
    C.Vx  = s_Vx.val
    C.Vy  = s_Vy.val
    C.fx  = s_fx.val
    C.fy  = s_fy.val
    C.phx = s_phx.val
    C.phy = s_phy.val
    C.tau = s_tau.val
    _actualizar_rangos_voltajes()

for s in (s_Va, s_Vx, s_Vy, s_fx, s_fy, s_tau, s_phx, s_phy):
    s.on_changed(on_slider)

for sl in (s_Va, s_Vx, s_Vy, s_fx, s_fy, s_tau, s_phx, s_phy):
    sl.label.set_fontsize(10)
    sl.label.set_ha('left')
    sl.label.set_position((0.02, 1.35))  # place label above the slider within its axes

# Mapea un punto en la pantalla (X,Y) a voltajes DC de placas (Vx, Vy) en modo manual
def _set_voltages_from_point(x, y):
    _actualizar_rangos_voltajes()
    K = deflection_gain(C.Va)
    C.Vx = float(np.clip(x / K, s_Vx.valmin, s_Vx.valmax))
    C.Vy = float(np.clip(y / K, s_Vy.valmin, s_Vy.valmax))
    s_Vx.set_val(C.Vx); s_Vy.set_val(C.Vy)
    S.x, S.y = compute_xy(S.t)

# Handlers de ratón para mover el punto en modo CRT (click + arrastre en PANTALLA)
def _on_press(evt):
    if not S.mode_lissajous and evt.inaxes == ax_screen and (evt.xdata is not None) and (evt.ydata is not None):
        _set_voltages_from_point(evt.xdata, evt.ydata)
        S.dragging = True

def _on_release(evt):
    if S.dragging:
        S.dragging = False

def _on_move(evt):
    if not S.mode_lissajous and S.dragging and (evt.inaxes == ax_screen) and (evt.xdata is not None) and (evt.ydata is not None):
        _set_voltages_from_point(evt.xdata, evt.ydata)

fig.canvas.mpl_connect('button_press_event', _on_press)
fig.canvas.mpl_connect('button_release_event', _on_release)
fig.canvas.mpl_connect('motion_notify_event', _on_move)

# Curva Lissajous de alta resolución para suavidad visual
def _lissajous_curve(t_now, cycles=2.0, samples=1400):
    """Genera una curva Lissajous de alta resolución (ventana móvil) para dar suavidad visual."""
    fx = max(C.fx, 1e-6)
    fy = max(C.fy, 1e-6)
    Tslow = max(1.0/fx, 1.0/fy)
    window = cycles * Tslow
    ts = np.linspace(t_now - window, t_now, samples)
    K = deflection_gain(C.Va)
    xs = K * C.Vx * np.sin(2*np.pi*fx*ts + C.phx)
    ys = K * C.Vy * np.sin(2*np.pi*fy*ts + C.phy)
    # Smooth auto‑scale to keep the whole curve within the screen without flattening
    margin = SCREEN_SCALE * 0.95
    max_abs = max(np.max(np.abs(xs)), np.max(np.abs(ys)), 1e-9)
    if max_abs > margin:
        s = margin / max_abs
        xs *= s
        ys *= s
    return xs, ys

# =============== Simulación / dibujo ==============

# Bucle de animación: actualiza tiempo/estado y redibuja rayos, spot y persistencia
def update_frame(_):
    if not S.paused:
        # Avance temporal (más fino en Lissajous) y registro en la traza
        dt = (DT_LISS if S.mode_lissajous else DT) * TIME_SCALE
        S.t += dt
        S.x, S.y = compute_xy(S.t)
        S.trail.append((S.t, S.x, S.y))

    # Rayos en Top/Side: tramo recto hasta placas y tramo deflectado hasta pantalla
    z_poly, x_poly = ray_poly(S.x)
    _,      y_poly = ray_poly(S.y)
    ray_top.set_data(z_poly, x_poly)   # X vs Z (top view)
    ray_side.set_data(z_poly, y_poly)  # Y vs Z (side view)

    # Punto en pantalla (PANTALLA) con brillo/bloom proporcional a Va
    b = brightness_from_Va(C.Va)
    spot.set_offsets([[S.x, S.y]])
    spot.set_sizes([80 + 80*b])        # size scales with brightness
    spot.set_alpha(0.35 + 0.65*b)

    # Persistencia tipo fósforo: puntos con decaimiento exponencial (controlado por τ)
    if len(S.trail):
        times = np.array([t for (t, _, _) in S.trail])
        xs    = np.array([x for (_, x, _) in S.trail])
        ys    = np.array([y for (_, _, y) in S.trail])
        # exponential fade with tau; newer points brighter
        age = (S.t - times)
        alphas = np.exp(-age / max(C.tau, 1e-3))
        # draw subset for performance
        if len(xs) > 600:
            idx = np.linspace(0, len(xs)-1, 600).astype(int)
            xs, ys, alphas = xs[idx], ys[idx], alphas[idx]
        trail_scatter.set_offsets(np.c_[xs, ys])
        # map alpha & size by brightness too
        trail_scatter.set_alpha(0.6)
        trail_scatter.set_sizes(8 + 16*alphas*b)
        # Matplotlib no permite variar alpha por punto fácilmente sin mapa de color;
        # lo emulamos variando el tamaño + una alpha constante. Opcional: usar mapa de color por edad.
        trail_scatter.set_array(alphas)  # habilita el uso de mapa de color
        trail_scatter.set_cmap('Reds')
        trail_scatter.set_clim(0.0, 1.0)
        # En Lissajous, confiar solo en puntos de persistencia fósforo (sin línea continua)
        if S.mode_lissajous:
            _ = _lissajous_curve(S.t, cycles=2.5, samples=1600)  # keep call to honor future use
            trace_line.set_data([], [])
            trace_line.set_alpha(0.0)
            trail_scatter.set_alpha(0.5)
        else:
            trace_line.set_data([], [])
            trace_line.set_alpha(0.0)
            trail_scatter.set_alpha(0.6)
    else:
        trail_scatter.set_offsets(np.empty((0, 2)))
        trace_line.set_data([], [])

    return ray_top, ray_side, spot, trail_scatter, trace_line

def compute_xy(t):
    """Calcula (x,y) en función del tiempo y del modo.
    - Lissajous: señales sinusoidales y auto-escalado uniforme (mantiene proporciones X–Y).
    - CRT manual: voltajes DC y recorte independiente por eje (sin acoplar X e Y).
    """
    K = deflection_gain(C.Va)
    margin = SCREEN_SCALE * 0.95

    if S.mode_lissajous:
        # Señales sinusoidales (amplitudes Vx/Vy, frecuencias fX/fY, fases φX/φY)
        vx = C.Vx * np.sin(2*np.pi*C.fx*t + C.phx)
        vy = C.Vy * np.sin(2*np.pi*C.fy*t + C.phy)
        raw_x = K * vx
        raw_y = K * vy
        # Auto-escalado UNIFORME (misma escala en X e Y) para no pegarse a los bordes
        max_abs = max(abs(raw_x), abs(raw_y), 1e-9)
        scale = min(1.0, margin / max_abs)
        x = float(raw_x * scale)
        y = float(raw_y * scale)
    else:
        # Modo manual (DC): independiente por eje -> recorte por CLIP, no se escala en conjunto
        raw_x = K * C.Vx
        raw_y = K * C.Vy
        x = float(np.clip(raw_x, -margin, margin))
        y = float(np.clip(raw_y, -margin, margin))

    return x, y

ani = FuncAnimation(fig, update_frame, interval=10, blit=False)
plt.show()