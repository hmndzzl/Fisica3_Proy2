# crt_simulacion_limpia.py
import pygame
import math
import sys
from collections import deque

pygame.init()

# -------------------------------
# CONSTANTES FÍSICAS Y GEOMETRÍA
# -------------------------------
ELECTRON_CHARGE = -1.602e-19    # C (carga real negativa)
ELECTRON_CHARGE_MAG = 1.602e-19 # magnitud para energía
ELECTRON_MASS = 9.109e-31       # kg

SCREEN_SIZE = 0.20          # m (20 cm)
PLATE_SEPARATION = 0.02     # m
PLATE_LENGTH = 0.05         # m
PLATE_WIDTH = 0.03          # m (no usado en física, solo dibujo)
DISTANCE_TO_SCREEN = 0.15   # m
DISTANCE_BETWEEN_PLATES = 0.03
DISTANCE_GUN_TO_PLATES = 0.05

# -------------------------------
# PANTALLA / COLORES / UI
# -------------------------------
WINDOW_WIDTH = 1650
WINDOW_HEIGHT = 800
CONTROL_PANEL_WIDTH = 500

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 136)
YELLOW = (255, 255, 0)
RED = (255, 68, 68)
BLUE = (68, 68, 255)
GRAY = (102, 102, 102)
LIGHT_GRAY = (170, 170, 170)
DARK_GRAY = (68, 68, 68)
TRACE_GREEN = (0, 255, 136)
ELECTRON_BEAM = (0, 255, 255)
CYAN = (0, 255, 255)

# -------------------------------
# UTILIDADES UI (Slider / Button)
# -------------------------------
class Slider:
    def __init__(self, x, y, width, height, min_val, max_val, initial_val, label, unit=""):
        self.rect = pygame.Rect(x, y, width, height)
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.val = float(initial_val)
        self.label = label
        self.unit = unit
        self.dragging = False
        self.font = pygame.font.Font(None, 18)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            rel_x = event.pos[0] - self.rect.x
            rel_x = max(0, min(rel_x, self.rect.width))
            self.val = self.min_val + (rel_x / self.rect.width) * (self.max_val - self.min_val)

    def draw(self, screen):
        pygame.draw.rect(screen, GRAY, self.rect, 2)
        handle_pos = int((self.val - self.min_val) / (self.max_val - self.min_val) * self.rect.width)
        handle_rect = pygame.Rect(self.rect.x + handle_pos - 5, self.rect.y - 3, 10, self.rect.height + 6)
        pygame.draw.rect(screen, GREEN, handle_rect)
        label = f"{self.label}: {self.val:.1f}" + (f" {self.unit}" if self.unit else "")
        screen.blit(self.font.render(label, True, WHITE), (self.rect.x, self.rect.y - 20))

class Button:
    def __init__(self, x, y, width, height, text, active=False):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.active = active
        self.font = pygame.font.Font(None, 20)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            return True
        return False

    def draw(self, screen):
        color = GREEN if self.active else GRAY
        pygame.draw.rect(screen, color, self.rect)
        pygame.draw.rect(screen, WHITE, self.rect, 2)
        text_color = BLACK if self.active else WHITE
        surf = self.font.render(self.text, True, text_color)
        screen.blit(surf, surf.get_rect(center=self.rect.center))

# -------------------------------
# CLASE ELECTRÓN (FÍSICA)
# -------------------------------
class Electron:
    def __init__(self):
        self.reset()

    def reset(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.001
        self.vx = 0.0
        self.vy = 0.0
        self.vz = 0.0
        self.path = deque(maxlen=1000)
        self.initial_acceleration_done = False

    def update(self, dt, acceleration_voltage, vertical_voltage, horizontal_voltage):
        # velocidad axial inicial por energía (una vez)
        if not self.initial_acceleration_done and abs(acceleration_voltage) > 0:
            # usamos magnitud de carga para energía
            self.vz = math.sqrt(2 * ELECTRON_CHARGE_MAG * abs(acceleration_voltage) / ELECTRON_MASS)
            self.initial_acceleration_done = True

        # definir regiones z de placas
        v_start = DISTANCE_GUN_TO_PLATES
        v_end = v_start + PLATE_LENGTH
        h_start = v_end + DISTANCE_BETWEEN_PLATES
        h_end = h_start + PLATE_LENGTH

        # vertical plates -> deflexión Y
        if v_start <= self.z <= v_end and abs(self.y) < PLATE_SEPARATION / 2:
            # convención: vertical_voltage = V_top - V_bottom
            # E_y = -ΔV/d (campo apunta del + al -). multiplicando por carga negativa dará dirección física correcta
            Ey = -vertical_voltage / PLATE_SEPARATION
            Fy = ELECTRON_CHARGE * Ey
            ay = Fy / ELECTRON_MASS
            self.vy += ay * dt

        # horizontal plates -> deflexión X
        if h_start <= self.z <= h_end and abs(self.x) < PLATE_SEPARATION / 2:
            Ex = -horizontal_voltage / PLATE_SEPARATION
            Fx = ELECTRON_CHARGE * Ex
            ax = Fx / ELECTRON_MASS
            self.vx += ax * dt

        # integrar movimiento (Euler explícito)
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt

        self.path.append((self.x, self.y, self.z))

    def has_hit_screen(self):
        screen_distance = (DISTANCE_GUN_TO_PLATES + PLATE_LENGTH + DISTANCE_BETWEEN_PLATES + PLATE_LENGTH + DISTANCE_TO_SCREEN)
        return self.z >= screen_distance

    def get_screen_position(self):
        return (self.x, self.y)

    def is_within_screen_bounds(self):
        return abs(self.x) <= SCREEN_SIZE / 2 and abs(self.y) <= SCREEN_SIZE / 2

# -------------------------------
# SIMULACIÓN (UI + BUCLE)
# -------------------------------
class CRTSimulation:
    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Simulación CRT - Física 3")
        self.clock = pygame.time.Clock()
        self.running = True

        # estado físico y visual
        self.time = 0
        self.electron = Electron()
        self.screen_traces = deque(maxlen=5000)
        self.simulation_speed = 1
        self.beam_visible = True
        self.mode = 'manual'  # 'manual' o 'lissajous'
        self.show_presets = False
        self.preset_buttons = []

        # fuentes
        self.font_title = pygame.font.Font(None, 28)
        self.font_label = pygame.font.Font(None, 20)
        self.font_small = pygame.font.Font(None, 16)

        self._create_controls()
        self._create_presets()

    def _create_controls(self):
        cx = WINDOW_WIDTH - CONTROL_PANEL_WIDTH + 20
        self.sliders = {
            'acceleration_voltage': Slider(cx, 90, 250, 15, 500, 5000, 2000, "Voltaje Aceleración", "V"),
            'persistence': Slider(cx, 135, 250, 15, 50, 2000, 500, "Persistencia", "ms"),
            'vertical_voltage': Slider(cx, 265, 250, 15, -300, 300, 0, "Voltaje Placas Verticales", "V"),
            'horizontal_voltage': Slider(cx, 310, 250, 15, -300, 300, 0, "Voltaje Placas Horizontales", "V"),
            'vert_amplitude': Slider(cx, 265, 250, 15, 50, 300, 150, "Amplitud Vertical", "V"),
            'vert_frequency': Slider(cx, 310, 250, 15, 0.1, 10.0, 1.0, "Frecuencia Vertical", "Hz"),
            'vert_phase': Slider(cx, 355, 250, 15, 0, 360, 0, "Fase Vertical", "°"),
            'horiz_amplitude': Slider(cx, 400, 250, 15, 50, 300, 150, "Amplitud Horizontal", "V"),
            'horiz_frequency': Slider(cx, 445, 250, 15, 0.1, 10.0, 1.5, "Frecuencia Horizontal", "Hz"),
            'horiz_phase': Slider(cx, 490, 250, 15, 0, 360, 90, "Fase Horizontal", "°")
        }
        self.buttons = {
            'manual': Button(cx, 185, 80, 25, "Manual", True),
            'lissajous': Button(cx + 85, 185, 80, 25, "Lissajous", False),
            'preset_lissajous': Button(cx + 170, 185, 150, 25, "Tabla Lissajous", False),
            'clear': Button(cx, 550, 80, 25, "Limpiar", False),
            'pause': Button(cx + 85, 550, 80, 25, "Pausa", False),
            'beam_toggle': Button(cx + 170, 550, 80, 25, "Haz ON", True)
        }

    def _create_presets(self):
        self.lissajous_presets = {
            "1:1": [{"name": "δ=0°", "fv": 1.0, "fh": 1.0, "phase": 0},
                    {"name": "δ=45°", "fv": 1.0, "fh": 1.0, "phase": 45},
                    {"name": "δ=90°", "fv": 1.0, "fh": 1.0, "phase": 90},
                    {"name": "δ=135°", "fv": 1.0, "fh": 1.0, "phase": 135},
                    {"name": "δ=180°", "fv": 1.0, "fh": 1.0, "phase": 180}],
            "1:2": [{"name": "δ=0°", "fv": 2.0, "fh": 1.0, "phase": 0},
                    {"name": "δ=45°", "fv": 2.0, "fh": 1.0, "phase": 45},
                    {"name": "δ=90°", "fv": 2.0, "fh": 1.0, "phase": 90},
                    {"name": "δ=135°", "fv": 2.0, "fh": 1.0, "phase": 135},
                    {"name": "δ=180°", "fv": 2.0, "fh": 1.0, "phase": 180}],
            "1:3": [{"name": "δ=0°", "fv": 3.0, "fh": 1.0, "phase": 180},
                    {"name": "δ=45°", "fv": 3.0, "fh": 1.0, "phase": 45},
                    {"name": "δ=90°", "fv": 3.0, "fh": 1.0, "phase": 90},
                    {"name": "δ=135°", "fv": 3.0, "fh": 1.0, "phase": 135},
                    {"name": "δ=180°", "fv": 3.0, "fh": 1.0, "phase": 0}],
            "2:3": [{"name": "δ=0°", "fv": 3.0, "fh": 2.0, "phase": 0},
                    {"name": "δ=45°", "fv": 3.0, "fh": 2.0, "phase": 45},
                    {"name": "δ=90°", "fv": 3.0, "fh": 2.0, "phase": 90},
                    {"name": "δ=135°", "fv": 3.0, "fh": 2.0, "phase": 135},
                    {"name": "δ=180°", "fv": 3.0, "fh": 2.0, "phase": 180}]
        }

    # -------------------------------
    # EVENTOS
    # -------------------------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.simulation_speed = 0 if self.simulation_speed > 0 else 1
                    self.buttons['pause'].text = "Reanudar" if self.simulation_speed == 0 else "Pausa"
                if event.key == pygame.K_c:
                    self.screen_traces.clear()
                if event.key == pygame.K_r:
                    self.electron.reset()
                if event.key == pygame.K_b:
                    self.beam_visible = not self.beam_visible
                    self.buttons['beam_toggle'].text = "Haz ON" if self.beam_visible else "Haz OFF"
                    self.buttons['beam_toggle'].active = self.beam_visible

            # sliders
            for s in self.sliders.values():
                s.handle_event(event)

            # botones
            if self.buttons['manual'].handle_event(event):
                self.mode = 'manual'
                self.buttons['manual'].active = True
                self.buttons['lissajous'].active = False
            if self.buttons['lissajous'].handle_event(event):
                self.mode = 'lissajous'
                self.buttons['manual'].active = False
                self.buttons['lissajous'].active = True
            if self.mode == 'lissajous' and self.buttons['preset_lissajous'].handle_event(event):
                self.show_presets = not self.show_presets
            if self.buttons['clear'].handle_event(event):
                self.screen_traces.clear()
            if self.buttons['pause'].handle_event(event):
                self.simulation_speed = 0 if self.simulation_speed > 0 else 1
                self.buttons['pause'].text = "Reanudar" if self.simulation_speed == 0 else "Pausa"
            if self.buttons['beam_toggle'].handle_event(event):
                self.beam_visible = not self.beam_visible
                self.buttons['beam_toggle'].text = "Haz ON" if self.beam_visible else "Haz OFF"
                self.buttons['beam_toggle'].active = self.beam_visible

            # presets (cuando se muestran)
            if self.mode == 'lissajous' and self.show_presets:
                for btn, preset in self.preset_buttons:
                    if btn.handle_event(event):
                        self.sliders['vert_frequency'].val = preset['fv']
                        self.sliders['horiz_frequency'].val = preset['fh']
                        self.sliders['horiz_phase'].val = preset['phase']
                        self.show_presets = False

    # -------------------------------
    # CÁLCULO DE VOLTAJES
    # -------------------------------
    def get_voltages(self):
        if self.mode == 'manual':
            return self.sliders['vertical_voltage'].val, self.sliders['horizontal_voltage'].val
        else:
            t = self.time / 1000.0  # ms -> s
            vert_v = (self.sliders['vert_amplitude'].val *
                      math.sin(2 * math.pi * self.sliders['vert_frequency'].val * t +
                               self.sliders['vert_phase'].val * math.pi / 180))
            horiz_v = (self.sliders['horiz_amplitude'].val *
                       math.sin(2 * math.pi * self.sliders['horiz_frequency'].val * t +
                                self.sliders['horiz_phase'].val * math.pi / 180))
            return vert_v, horiz_v

    # -------------------------------
    # FÍSICA: ACTUALIZAR ELECTRÓN
    # -------------------------------
    def update_physics(self):
        if self.simulation_speed == 0:
            return
        dt = 2e-9
        vertical_voltage, horizontal_voltage = self.get_voltages()
        acc_voltage = self.sliders['acceleration_voltage'].val

        for _ in range(100):  # sub-steps por frame
            self.electron.update(dt, acc_voltage, vertical_voltage, horizontal_voltage)

            if self.electron.has_hit_screen():
                if self.electron.is_within_screen_bounds():
                    sx, sy = self.electron.get_screen_position()
                    brightness = min(1.0, acc_voltage / 4000.0)
                    self.screen_traces.append({'x': sx, 'y': sy, 'time': self.time, 'brightness': brightness})
                self.electron.reset()

    # -------------------------------
    # DIBUJOS / ESCALADOS
    # -------------------------------
    def _physical_screen_distance(self):
        return (DISTANCE_GUN_TO_PLATES + PLATE_LENGTH + DISTANCE_BETWEEN_PLATES + PLATE_LENGTH + DISTANCE_TO_SCREEN)

    def draw_side_view(self):
        view = pygame.Rect(50, 50, 500, 300)
        pygame.draw.rect(self.screen, BLACK, view)
        pygame.draw.rect(self.screen, WHITE, view, 2)
        title = self.font_label.render("Vista Lateral (Deflexión Vertical)", True, GREEN)
        self.screen.blit(title, (view.x + 10, view.y - 30))

        # geometría y escalas
        physical_dist = self._physical_screen_distance()
        margin_left = 70
        usable_w = view.width - margin_left - 20
        scale_z = usable_w / physical_dist
        scale_y = (view.height - 40) / SCREEN_SIZE
        center_y = view.y + view.height // 2
        gun_center = (view.x + 20 + 40, view.y + 140 + 10)

        # haz visible
        if self.beam_visible and self.electron.path:
            cx, cy, cz = self.electron.path[-1]
            z_vis = min(cz, physical_dist)
            ex = view.x + margin_left + z_vis * scale_z
            ey = center_y - cy * scale_y
            pygame.draw.line(self.screen, ELECTRON_BEAM, gun_center, (int(ex), int(ey)), 3)
            pygame.draw.line(self.screen, WHITE, gun_center, (int(ex), int(ey)), 1)

        # trayectoria (verde)
        if len(self.electron.path) > 1:
            pts = []
            for (px, py, pz) in self.electron.path:
                xpx = view.x + 70 + pz * scale_z
                ypx = center_y - py * scale_y
                if view.collidepoint(xpx, ypx):
                    pts.append((int(xpx), int(ypx)))
            if len(pts) > 1:
                pygame.draw.lines(self.screen, TRACE_GREEN, False, pts, 2)

        # electrón actual
        if self.electron.path:
            cx, cy, cz = self.electron.path[-1]
            ex = view.x + margin_left + min(cz, physical_dist) * scale_z
            ey = center_y - cy * scale_y
            pygame.draw.circle(self.screen, YELLOW, (int(ex), int(ey)), 4)

        # placas (indicadores simples)
        vert_v, _ = self.get_voltages()
        top = pygame.Rect(view.x + 100, view.y + 100, 80, 8)
        bottom = pygame.Rect(view.x + 100, view.y + 192, 80, 8)
        color_top = RED if vert_v > 0 else BLUE if vert_v < 0 else GRAY
        color_bottom = BLUE if vert_v > 0 else RED if vert_v < 0 else GRAY
        pygame.draw.rect(self.screen, color_top, top)
        pygame.draw.rect(self.screen, color_bottom, bottom)
        if vert_v != 0:
            sign_top = "+" if vert_v > 0 else "-"
            sign_bottom = "-" if vert_v > 0 else "+"
            self.screen.blit(self.font_small.render(sign_top, True, WHITE), (top.x + 35, top.y - 15))
            self.screen.blit(self.font_small.render(sign_bottom, True, WHITE), (bottom.x + 35, bottom.y + 10))

        # info
        def_text = f"Deflexión Y: {self.electron.y * 1000:.2f} mm"
        volt_text = f"Voltaje V: {vert_v:.1f} V"
        self.screen.blit(self.font_small.render(def_text, True, WHITE), (view.x + 10, view.y + view.height - 55))
        self.screen.blit(self.font_small.render(volt_text, True, WHITE), (view.x + 10, view.y + view.height - 35))

    def draw_top_view(self):
        view = pygame.Rect(575, 50, 500, 300)
        pygame.draw.rect(self.screen, BLACK, view)
        pygame.draw.rect(self.screen, WHITE, view, 2)
        title = self.font_label.render("Vista Superior (Deflexión Horizontal)", True, GREEN)
        self.screen.blit(title, (view.x + 10, view.y - 30))

        physical_dist = self._physical_screen_distance()
        margin_left = 70
        usable_w = view.width - margin_left - 20
        scale_z = usable_w / physical_dist
        scale_x = (view.height - 40) / SCREEN_SIZE
        center_y = view.y + view.height // 2
        gun_center = (view.x + 20 + 40, view.y + 140 + 10)

        if self.beam_visible and self.electron.path:
            cx, cy, cz = self.electron.path[-1]
            z_vis = min(cz, physical_dist)
            ex = view.x + margin_left + z_vis * scale_z
            ey = center_y - cx * scale_x
            pygame.draw.line(self.screen, ELECTRON_BEAM, gun_center, (int(ex), int(ey)), 3)
            pygame.draw.line(self.screen, WHITE, gun_center, (int(ex), int(ey)), 1)

        if len(self.electron.path) > 1:
            pts = []
            for (px, py, pz) in self.electron.path:
                xpx = view.x + 70 + pz * scale_z
                ypx = center_y - px * scale_x
                if view.collidepoint(xpx, ypx):
                    pts.append((int(xpx), int(ypx)))
            if len(pts) > 1:
                pygame.draw.lines(self.screen, TRACE_GREEN, False, pts, 2)

        if self.electron.path:
            cx, cy, cz = self.electron.path[-1]
            ex = view.x + margin_left + min(cz, physical_dist) * scale_z
            ey = center_y - cx * scale_x
            pygame.draw.circle(self.screen, YELLOW, (int(ex), int(ey)), 4)

        _, horiz_v = self.get_voltages()
        left_plate = pygame.Rect(view.x + 200, view.y + 110, 8, 80)
        right_plate = pygame.Rect(view.x + 272, view.y + 110, 8, 80)
        color_left = RED if horiz_v > 0 else BLUE if horiz_v < 0 else GRAY
        color_right = BLUE if horiz_v > 0 else RED if horiz_v < 0 else GRAY
        pygame.draw.rect(self.screen, color_left, left_plate)
        pygame.draw.rect(self.screen, color_right, right_plate)
        if horiz_v != 0:
            self.screen.blit(self.font_small.render(("+" if horiz_v > 0 else "-"), True, WHITE), (left_plate.x - 15, left_plate.y + 35))
            self.screen.blit(self.font_small.render(("-" if horiz_v > 0 else "+"), True, WHITE), (right_plate.x + 15, right_plate.y + 35))

        def_text = f"Deflexión X: {self.electron.x * 1000:.2f} mm"
        volt_text = f"Voltaje H: {horiz_v:.1f} V"
        self.screen.blit(self.font_small.render(def_text, True, WHITE), (view.x + 10, view.y + view.height - 55))
        self.screen.blit(self.font_small.render(volt_text, True, WHITE), (view.x + 10, view.y + view.height - 35))

    def draw_screen_view(self):
        view = pygame.Rect(240, 385, 650, 400)
        pygame.draw.rect(self.screen, BLACK, view)
        pygame.draw.rect(self.screen, WHITE, view, 2)
        title = self.font_label.render("PANTALLA - Aquí impactan los electrones", True, GREEN)
        self.screen.blit(title, (view.x + 10, view.y - 20))

        # grid y centro
        grid = 50
        for i in range(grid, view.width, grid):
            pygame.draw.line(self.screen, DARK_GRAY, (view.x + i, view.y), (view.x + i, view.y + view.height))
        for i in range(grid, view.height, grid):
            pygame.draw.line(self.screen, DARK_GRAY, (view.x, view.y + i), (view.x + view.width, view.y + i))

        center_x = view.x + view.width // 2
        center_y = view.y + view.height // 2
        pygame.draw.line(self.screen, WHITE, (center_x - 20, center_y), (center_x + 20, center_y), 2)
        pygame.draw.line(self.screen, WHITE, (center_x, center_y - 20), (center_x, center_y + 20), 2)

        persistence = self.sliders['persistence'].val
        current_time = self.time
        scale_x = (view.width - 40) / SCREEN_SIZE
        scale_y = (view.height - 40) / SCREEN_SIZE

        for trace in list(self.screen_traces):
            age = current_time - trace['time']
            if age < persistence * 2:
                alpha = max(0.1, 1 - age / (persistence * 2))
                screen_x = center_x + (trace['x'] * scale_x)
                screen_y = center_y - (trace['y'] * scale_y)
                if view.collidepoint(screen_x, screen_y):
                    brightness = trace.get('brightness', 1.0)
                    intensity = int(255 * alpha * brightness)
                    color = (0, intensity, int(intensity * 0.8))
                    size = max(2, int(7 * alpha * brightness))
                    pygame.draw.circle(self.screen, color, (int(screen_x), int(screen_y)), size)

        if self.electron.path:
            cx, cy, _ = self.electron.path[-1]
            sx = center_x + cx * scale_x
            sy = center_y - cy * scale_y
            if view.collidepoint(sx, sy):
                pygame.draw.circle(self.screen, YELLOW, (int(sx), int(sy)), 4)

    def draw_controls(self):
        rect = pygame.Rect(WINDOW_WIDTH - CONTROL_PANEL_WIDTH, 0, CONTROL_PANEL_WIDTH, WINDOW_HEIGHT)
        pygame.draw.rect(self.screen, (20, 20, 40), rect)
        pygame.draw.line(self.screen, WHITE, (rect.x, 0), (rect.x, WINDOW_HEIGHT), 2)

        self.screen.blit(self.font_title.render("Controles", True, GREEN), (rect.x + 20, 20))
        self.screen.blit(self.font_label.render("Modo de Control", True, WHITE), (rect.x + 20, 165))

        # dibujar botones modo
        self.buttons['manual'].draw(self.screen)
        self.buttons['lissajous'].draw(self.screen)
        self.buttons['preset_lissajous'].draw(self.screen)

        # básicos
        self.screen.blit(self.font_label.render("Controles Básicos", True, WHITE), (rect.x + 20, 50))
        self.sliders['acceleration_voltage'].draw(self.screen)
        self.sliders['persistence'].draw(self.screen)

        if self.mode == 'manual':
            self.screen.blit(self.font_label.render("Control Manual", True, WHITE), (rect.x + 20, 225))
            self.sliders['vertical_voltage'].draw(self.screen)
            self.sliders['horizontal_voltage'].draw(self.screen)
        else:
            self.screen.blit(self.font_label.render("Figuras de Lissajous", True, WHITE), (rect.x + 20, 225))
            self.sliders['vert_amplitude'].draw(self.screen)
            self.sliders['vert_frequency'].draw(self.screen)
            self.sliders['vert_phase'].draw(self.screen)
            self.sliders['horiz_amplitude'].draw(self.screen)
            self.sliders['horiz_frequency'].draw(self.screen)
            self.sliders['horiz_phase'].draw(self.screen)

            if self.show_presets:
                self._draw_presets(rect.x + 20, 600)

        # control buttons
        self.buttons['clear'].draw(self.screen)
        self.buttons['pause'].draw(self.screen)
        self.buttons['beam_toggle'].draw(self.screen)

        # status
        info_y = 620
        status = "PAUSADO" if self.simulation_speed == 0 else "EJECUTANDO"
        vert_v, horiz_v = self.get_voltages()
        info_texts = [
            f"Estado: {status}",
            f"Tiempo: {self.time/1000:.1f}s",
            f"Modo: {self.mode.capitalize()}",
            f"V_vert: {vert_v:.1f}V",
            f"V_horiz: {horiz_v:.1f}V"
        ]
        for i, t in enumerate(info_texts):
            color = GREEN if i == 1 and status == "EJECUTANDO" else LIGHT_GRAY
            if i == 1 and status == "PAUSADO":
                color = RED
            self.screen.blit(self.font_small.render(t, True, color), (rect.x + 20, info_y + i * 16))

        # ayuda teclado
        help_y = info_y + len(info_texts) * 16 + 10
        help_texts = [
            "Teclas:",
            "ESPACIO: Pausa/Resume",
            "C: Limpiar pantalla",
            "R: Reset electrón",
            "B: Haz ON/OFF"
        ]
        for i, t in enumerate(help_texts):
            color = YELLOW if i == 0 else LIGHT_GRAY
            self.screen.blit(self.font_small.render(t, True, color), (rect.x + 20, help_y + i * 12))

    def _draw_presets(self, start_x, start_y):
        rows = list(self.lissajous_presets.keys())
        cols = ["0°", "45°", "90°", "135°", "180°"]
        cell_w, cell_h = 80, 30
        menu_w = cell_w * (len(cols) + 1) + 20
        menu_h = cell_h * (len(rows) + 1) + 20
        menu_rect = pygame.Rect(start_x - 10, start_y - 10, menu_w, menu_h)
        pygame.draw.rect(self.screen, DARK_GRAY, menu_rect)
        pygame.draw.rect(self.screen, WHITE, menu_rect, 2)
        self.screen.blit(self.font_label.render("Tabla de Presets Lissajous", True, YELLOW), (start_x, start_y - 25))
        self.preset_buttons = []
        for j, col in enumerate(cols):
            self.screen.blit(self.font_small.render(col, True, CYAN), (start_x + (j+1)*cell_w + 10, start_y))
        for i, row in enumerate(rows):
            self.screen.blit(self.font_small.render(row, True, CYAN), (start_x, start_y + (i+1)*cell_h + 5))
            for j, preset in enumerate(self.lissajous_presets[row]):
                bx = start_x + (j+1)*cell_w
                by = start_y + (i+1)*cell_h
                btn = Button(bx, by, cell_w-5, cell_h-5, preset["name"])
                btn.draw(self.screen)
                self.preset_buttons.append((btn, preset))

    # -------------------------------
    # DIBUJAR TODO Y BUCLE
    # -------------------------------
    def draw(self):
        # background gradient
        for y in range(WINDOW_HEIGHT):
            c = int(30 + (50 - 30) * (y / WINDOW_HEIGHT))
            pygame.draw.line(self.screen, (c, c+20, c+50), (0, y), (WINDOW_WIDTH - CONTROL_PANEL_WIDTH, y))

        self.draw_side_view()
        self.draw_top_view()
        self.draw_screen_view()
        self.draw_controls()

        fps = self.clock.get_fps()
        self.screen.blit(self.font_small.render(f"FPS: {fps:.1f}", True, WHITE), (10, 10))
        pygame.display.flip()

    def run(self):
        print("Iniciando simulación CRT")
        while self.running:
            self.handle_events()
            self.update_physics()
            self.draw()
            self.clock.tick(60)
            if self.simulation_speed > 0:
                self.time += 16
        pygame.quit()
        sys.exit()

# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    try:
        sim = CRTSimulation()
        sim.run()
    except Exception as e:
        print("Error en la simulación:", e)
        import traceback
        traceback.print_exc()
        pygame.quit()
        sys.exit(1)
