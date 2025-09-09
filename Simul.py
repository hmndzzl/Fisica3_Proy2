import pygame
import numpy as np
import math
import sys
from collections import deque

# Inicializar pygame
pygame.init()

# Constantes físicas
ELECTRON_CHARGE = 1.602e-19  # Coulombs
ELECTRON_MASS = 9.109e-31   # kg
SCREEN_SIZE = 0.20          # 20 cm (según especificaciones: decenas de cm)
PLATE_SEPARATION = 0.02     # 2 cm separación entre placas
PLATE_LENGTH = 0.05         # 5 cm longitud de placas
PLATE_WIDTH = 0.03          # 3 cm ancho de placas
DISTANCE_TO_SCREEN = 0.15   # 15 cm distancia a la pantalla
DISTANCE_BETWEEN_PLATES = 0.03  # 3 cm entre placas V y H
DISTANCE_GUN_TO_PLATES = 0.05   # 5 cm del cañón a las placas

# Configuración de la ventana
WINDOW_WIDTH = 1650
WINDOW_HEIGHT = 800
CONTROL_PANEL_WIDTH = 500

# Colores
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
ELECTRON_BEAM = (0, 255, 255)  # Color cyan para el haz
CYAN = (0, 255, 255)

class Slider:
    """Clase para crear controles deslizantes"""
    def __init__(self, x, y, width, height, min_val, max_val, initial_val, label, unit=""):
        self.rect = pygame.Rect(x, y, width, height)
        self.min_val = min_val
        self.max_val = max_val
        self.val = initial_val
        self.label = label
        self.unit = unit
        self.dragging = False
        self.font = pygame.font.Font(None, 18)
        
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            rel_x = event.pos[0] - self.rect.x
            rel_x = max(0, min(rel_x, self.rect.width))
            self.val = self.min_val + (rel_x / self.rect.width) * (self.max_val - self.min_val)
    
    def draw(self, screen):
        # Dibujar barra del slider
        pygame.draw.rect(screen, GRAY, self.rect, 2)
        
        # Calcular posición del handle
        handle_pos = int((self.val - self.min_val) / (self.max_val - self.min_val) * self.rect.width)
        handle_rect = pygame.Rect(self.rect.x + handle_pos - 5, self.rect.y - 3, 10, self.rect.height + 6)
        pygame.draw.rect(screen, GREEN, handle_rect)
        
        # Dibujar etiqueta y valor
        if self.unit:
            label_text = self.font.render(f"{self.label}: {self.val:.1f} {self.unit}", True, WHITE)
        else:
            label_text = self.font.render(f"{self.label}: {self.val:.1f}", True, WHITE)
        screen.blit(label_text, (self.rect.x, self.rect.y - 20))

class Button:
    """Clase para botones"""
    def __init__(self, x, y, width, height, text, active=False):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.active = active
        self.font = pygame.font.Font(None, 20)
        
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                return True
        return False
    
    def draw(self, screen):
        color = GREEN if self.active else GRAY
        pygame.draw.rect(screen, color, self.rect)
        pygame.draw.rect(screen, WHITE, self.rect, 2)
        
        text_color = BLACK if self.active else WHITE
        text_surface = self.font.render(self.text, True, text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        screen.blit(text_surface, text_rect)

class Electron:
    """Clase que representa un electrón y su comportamiento"""
    def __init__(self):
        self.reset()
        
    def reset(self):
        # Posición inicial en el cañón de electrones
        self.x = 0.0
        self.y = 0.0
        self.z = 0.001  # Justo después del cañón
        self.vx = 0.0
        self.vy = 0.0
        self.vz = 0.0
        self.path = deque(maxlen=1000)  # Trayectoria completa
        self.initial_acceleration_done = False
        
    def update(self, dt, acceleration_voltage, vertical_voltage, horizontal_voltage):
        """Actualizar posición y velocidad del electrón usando física correcta"""
        # Aceleración inicial una sola vez
        if not self.initial_acceleration_done and abs(acceleration_voltage) > 0:
            # v = sqrt(2*q*V/m) - Ecuación de energía cinética
            self.vz = math.sqrt(2 * ELECTRON_CHARGE * abs(acceleration_voltage) / ELECTRON_MASS)
            self.initial_acceleration_done = True
        
        # Regiones críticas
        vertical_plate_start = DISTANCE_GUN_TO_PLATES
        vertical_plate_end = vertical_plate_start + PLATE_LENGTH
        horizontal_plate_start = vertical_plate_end + DISTANCE_BETWEEN_PLATES
        horizontal_plate_end = horizontal_plate_start + PLATE_LENGTH
        
        # Campo en placas verticales (deflexión Y)
        if vertical_plate_start <= self.z <= vertical_plate_end and abs(self.y) < PLATE_SEPARATION/2:
            electric_field_y = vertical_voltage / PLATE_SEPARATION
            force_y = -ELECTRON_CHARGE * electric_field_y  # e- tiene carga negativa
            acceleration_y = force_y / ELECTRON_MASS
            self.vy += acceleration_y * dt
            
        # Campo en placas horizontales (deflexión X)
        if horizontal_plate_start <= self.z <= horizontal_plate_end and abs(self.x) < PLATE_SEPARATION/2:
            electric_field_x = horizontal_voltage / PLATE_SEPARATION
            force_x = -ELECTRON_CHARGE * electric_field_x
            acceleration_x = force_x / ELECTRON_MASS
            self.vx += acceleration_x * dt
            
        # Actualizar posición usando cinemática
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        
        # Guardar trayectoria
        self.path.append((self.x, self.y, self.z))
        
    def has_hit_screen(self):
        """Verificar si el electrón ha llegado a la pantalla"""
        screen_distance = (DISTANCE_GUN_TO_PLATES + PLATE_LENGTH + 
                          DISTANCE_BETWEEN_PLATES + PLATE_LENGTH + DISTANCE_TO_SCREEN)
        return self.z >= screen_distance
        
    def get_screen_position(self):
        """Obtener posición donde golpea la pantalla"""
        return (self.x, self.y)
        
    def is_within_screen_bounds(self):
        """Verificar límites de la pantalla"""
        return (abs(self.x) <= SCREEN_SIZE/2 and abs(self.y) <= SCREEN_SIZE/2)

class CRTSimulation:
    """Clase principal de la simulación CRT"""
    def __init__(self):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Simulación CRT - Universidad del Valle de Guatemala - Laboratorio Física 3")
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Variables de control
        self.mode = 'manual'  # 'manual' o 'lissajous'
        self.time = 0
        self.electron = Electron()
        self.screen_traces = deque(maxlen=5000)  # Más trazas para mejor persistencia
        self.simulation_speed = 1
        self.beam_visible = True
        
        # Fuentes
        self.font_title = pygame.font.Font(None, 28)
        self.font_label = pygame.font.Font(None, 20)
        self.font_small = pygame.font.Font(None, 16)
        
        self.setup_controls()
        
    def setup_controls(self):
        """Configurar controles deslizantes y botones según especificaciones"""
        control_x = WINDOW_WIDTH - CONTROL_PANEL_WIDTH + 20
        
        # Sliders
        self.sliders = {
            'acceleration_voltage': Slider(control_x, 90, 250, 15, 500, 5000, 2000, "Voltaje Aceleración", "V"),
            'persistence': Slider(control_x, 135, 250, 15, 50, 2000, 500, "Persistencia", "ms"),
            
            # Modo manual - Voltajes de placas
            'vertical_voltage': Slider(control_x, 265, 250, 15, -300, 300, 0, "Voltaje Placas Verticales", "V"),
            'horizontal_voltage': Slider(control_x, 310, 250, 15, -300, 300, 0, "Voltaje Placas Horizontales", "V"),
            
            # Modo Lissajous
            'vert_amplitude': Slider(control_x, 265, 250, 15, 50, 300, 150, "Amplitud Vertical", "V"),
            'vert_frequency': Slider(control_x, 310, 250, 15, 0.1, 10.0, 1.0, "Frecuencia Vertical", "Hz"),
            'vert_phase': Slider(control_x, 355, 250, 15, 0, 360, 0, "Fase Vertical", "°"),
            
            'horiz_amplitude': Slider(control_x, 400, 250, 15, 50, 300, 150, "Amplitud Horizontal", "V"),
            'horiz_frequency': Slider(control_x, 445, 250, 15, 0.1, 10.0, 1.5, "Frecuencia Horizontal", "Hz"),
            'horiz_phase': Slider(control_x, 490, 250, 15, 0, 360, 90, "Fase Horizontal", "°")
        }
        
        # Botones
        self.buttons = {
            'manual': Button(control_x, 185, 80, 25, "Manual", True),
            'lissajous': Button(control_x + 85, 185, 80, 25, "Lissajous", False),
            'clear': Button(control_x, 550, 80, 25, "Limpiar", False),
            'pause': Button(control_x + 85, 550, 80, 25, "Pausa", False),
            'beam_toggle': Button(control_x + 170, 550, 80, 25, "Haz ON", True)
            
        }
        self.buttons['preset_lissajous'] = Button(control_x + 170, 185, 150, 25, "Tabla Lissajous", False)

        # Tabla de presets Lissajous (freq_x, freq_y, phase)
        self.lissajous_presets = {
            "1:1": [
                {"name": "δ=0°",   "fv": 1.0, "fh": 1.0, "phase":   0},
                {"name": "δ=45°",  "fv": 1.0, "fh": 1.0, "phase":  45},
                {"name": "δ=90°",  "fv": 1.0, "fh": 1.0, "phase":  90},
                {"name": "δ=135°", "fv": 1.0, "fh": 1.0, "phase": 135},
                {"name": "δ=180°", "fv": 1.0, "fh": 1.0, "phase": 180},
            ],
            "1:2": [  # ωx:ωy = 1:2  → horiz=1, vert=2
                {"name": "δ=0°",   "fv": 2.0, "fh": 1.0, "phase":   90},
                {"name": "δ=45°",  "fv": 2.0, "fh": 1.0, "phase":  45},
                {"name": "δ=90°",  "fv": 2.0, "fh": 1.0, "phase":  0},
                {"name": "δ=135°", "fv": 2.0, "fh": 1.0, "phase": 135},
                {"name": "δ=180°", "fv": 2.0, "fh": 1.0, "phase": 270},
            ],
            "1:3": [  # ωx:ωy = 1:3  → horiz=1, vert=3
                {"name": "δ=0°",   "fv": 3.0, "fh": 1.0, "phase":   180},
                {"name": "δ=45°",  "fv": 3.0, "fh": 1.0, "phase":  135},
                {"name": "δ=90°",  "fv": 3.0, "fh": 1.0, "phase":  90},
                {"name": "δ=135°", "fv": 3.0, "fh": 1.0, "phase": 45},
                {"name": "δ=180°", "fv": 3.0, "fh": 1.0, "phase": 0},
            ],
            "2:3": [  # ωx:ωy = 2:3  → horiz=2, vert=3
                {"name": "δ=0°",   "fv": 3.0, "fh": 2.0, "phase":   45},
                {"name": "δ=45°",  "fv": 3.0, "fh": 2.0, "phase":  0},
                {"name": "δ=90°",  "fv": 3.0, "fh": 2.0, "phase":  135},
                {"name": "δ=135°", "fv": 3.0, "fh": 2.0, "phase": 180},
                {"name": "δ=180°", "fv": 3.0, "fh": 2.0, "phase": 135},
            ],
        }
        self.show_presets = False
        self.preset_buttons = []
    
    def handle_events(self):
        """Manejar eventos de pygame"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            # Teclas de control
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
                    
            # Manejar sliders
            for slider in self.sliders.values():
                slider.handle_event(event)
                
            # Manejar botones
            if self.buttons['manual'].handle_event(event):
                self.mode = 'manual'
                self.buttons['manual'].active = True
                self.buttons['lissajous'].active = False
                
            if self.buttons['lissajous'].handle_event(event):
                self.mode = 'lissajous'
                self.buttons['manual'].active = False
                self.buttons['lissajous'].active = True

            # abrir/cerrar menú de presets (solo disponible en modo lissajous)
            if self.mode == 'lissajous' and self.buttons['preset_lissajous'].handle_event(event):
                self.show_presets = not self.show_presets

            # si el menú está abierto, manejar clics sobre los botones de la tabla
            if self.mode == 'lissajous' and self.show_presets:
                for btn, preset in self.preset_buttons:
                    if btn.handle_event(event):
                        # aplicar preset: fh = frecuencia horizontal (ωx), fv = vertical (ωy)
                        self.sliders['horiz_frequency'].val = preset['fh']
                        self.sliders['vert_frequency'].val = preset['fv']

                        # δ como diferencia de fase entre vertical y horizontal
                        self.sliders['horiz_phase'].val = 0.0
                        self.sliders['vert_phase'].val = preset.get('phase', 0.0)

                        # Guardar preset activo
                        self.active_preset = preset

                        # Reinicio inmediato de simulación
                        self.electron.reset()
                        self.screen_traces.clear()
                        self.time = 0.0  # reiniciar tiempo simulado

                        # cerrar menú
                        self.show_presets = False
                        break
                
            if self.buttons['clear'].handle_event(event):
                self.screen_traces.clear()
                
            if self.buttons['pause'].handle_event(event):
                self.simulation_speed = 0 if self.simulation_speed > 0 else 1
                self.buttons['pause'].text = "Reanudar" if self.simulation_speed == 0 else "Pausa"
                
            if self.buttons['beam_toggle'].handle_event(event):
                self.beam_visible = not self.beam_visible
                self.buttons['beam_toggle'].text = "Haz ON" if self.beam_visible else "Haz OFF"
                self.buttons['beam_toggle'].active = self.beam_visible
                
    def get_voltages(self):
        """Calcular voltajes de placas según modo"""
        if self.mode == 'manual':
            return self.sliders['vertical_voltage'].val, self.sliders['horizontal_voltage'].val
        else:
            # tiempo simulado en segundos
            t = self.time / 1000.0  

            # amplitudes
            Ah = self.sliders['horiz_amplitude'].val
            Av = self.sliders['vert_amplitude'].val

            # frecuencias
            fh = self.sliders['horiz_frequency'].val
            fv = self.sliders['vert_frequency'].val

            # diferencia de fase δ (aplicada solo en Y)
            delta = (self.sliders['vert_phase'].val - self.sliders['horiz_phase'].val) * math.pi / 180

            # Voltajes tipo Lissajous
            horiz_v = Ah * math.sin(2 * math.pi * fh * t)
            vert_v  = Av * math.sin(2 * math.pi * fv * t + delta)

            return vert_v, horiz_v
            
    def update_physics(self):
        """Actualizar la física de la simulación (con presets Lissajous correctos)"""
        if self.simulation_speed == 0:
            return

        # Avanzar el tiempo de simulación en ms
        self.time += self.clock.get_time() * self.simulation_speed

        # Paso de integración en segundos
        dt = 2e-9  
        vertical_voltage, horizontal_voltage = self.get_voltages()

        # Iterar en pequeños pasos para simular movimiento continuo
        for _ in range(100):
            self.electron.update(
                dt,
                self.sliders['acceleration_voltage'].val,
                vertical_voltage,
                horizontal_voltage
            )
            # Cuando el electrón golpea la pantalla
            if self.electron.has_hit_screen():
                if self.electron.is_within_screen_bounds():
                    screen_pos = self.electron.get_screen_position()
                    brightness = min(1.0, self.sliders['acceleration_voltage'].val / 4000.0)

                    self.screen_traces.append({
                        'x': screen_pos[0],
                        'y': screen_pos[1],
                        'time': self.time,
                        'brightness': brightness
                    })

                # Reinicio limpio para que use siempre los últimos parámetros
                self.electron.reset()
                
    def draw_side_view(self):
        """Dibujar vista lateral (deflexión vertical)"""
        view_rect = pygame.Rect(50, 50, 500, 300)
        # Fondo y borde
        pygame.draw.rect(self.screen, BLACK, view_rect)
        pygame.draw.rect(self.screen, WHITE, view_rect, 2)
        
        # Título
        title = self.font_label.render("Vista Lateral (Deflexión Vertical)", True, GREEN)
        self.screen.blit(title, (view_rect.x + 10, view_rect.y - 30))
        
        # Geometría y elementos
        # Cañón de electrones
        gun_rect = pygame.Rect(view_rect.x + 20, view_rect.y + 140, 40, 20)
        pygame.draw.rect(self.screen, GRAY, gun_rect)
        gun_text = self.font_small.render("Cañón", True, WHITE)
        self.screen.blit(gun_text, (gun_rect.x, gun_rect.y - 15))
        
        # Placas verticales (color por signo de voltaje)
        vertical_voltage, _ = self.get_voltages()
        plate_color_top = RED if vertical_voltage > 0 else BLUE if vertical_voltage < 0 else GRAY
        plate_color_bottom = BLUE if vertical_voltage > 0 else RED if vertical_voltage < 0 else GRAY
        
        # Placa superior
        top_plate = pygame.Rect(view_rect.x + 100, view_rect.y + 100, 80, 8)
        pygame.draw.rect(self.screen, plate_color_top, top_plate)
        if vertical_voltage != 0:
            sign_top = "+" if vertical_voltage > 0 else "-"
            sign_text = self.font_small.render(sign_top, True, WHITE)
            self.screen.blit(sign_text, (top_plate.x + 35, top_plate.y - 15))
        
        # Placa inferior
        bottom_plate = pygame.Rect(view_rect.x + 100, view_rect.y + 192, 80, 8)
        pygame.draw.rect(self.screen, plate_color_bottom, bottom_plate)
        if vertical_voltage != 0:
            sign_bottom = "-" if vertical_voltage > 0 else "+"
            sign_text = self.font_small.render(sign_bottom, True, WHITE)
            self.screen.blit(sign_text, (bottom_plate.x + 35, bottom_plate.y + 10))
        
        # Etiqueta placas
        plate_text = self.font_small.render("Placas V", True, WHITE)
        self.screen.blit(plate_text, (view_rect.x + 120, view_rect.y + 75))
        
        # Pantalla (lateral)
        screen_rect = pygame.Rect(view_rect.x + 450, view_rect.y + 50, 20, 200)
        pygame.draw.rect(self.screen, DARK_GRAY, screen_rect)
        screen_text = self.font_small.render("Pantalla", True, WHITE)
        self.screen.blit(screen_text, (screen_rect.x - 10, screen_rect.y - 15))
        
        # ---------------- Escalado físico -> píxeles ----------------
        # Distancia física total desde el cañón hasta la pantalla (m)
        physical_screen_distance = (DISTANCE_GUN_TO_PLATES + PLATE_LENGTH +
                                    DISTANCE_BETWEEN_PLATES + PLATE_LENGTH + DISTANCE_TO_SCREEN)
        margin_left = 70
        usable_width = view_rect.width - margin_left - 20  # margen derecho
        scale_z = usable_width / physical_screen_distance   # px por metro en z (dinámico)
        scale_y = (view_rect.height - 40) / SCREEN_SIZE    # px por metro en y
        center_y = view_rect.y + view_rect.height // 2
        gun_center = (gun_rect.x + gun_rect.width, gun_rect.y + gun_rect.height // 2)

        # Haz desde el cañón hasta la posición actual (clampada a la pantalla física)
        if self.beam_visible and self.electron.path:
            cur_x, cur_y, cur_z = self.electron.path[-1]
            z_vis = min(cur_z, physical_screen_distance)
            ex = view_rect.x + margin_left + z_vis * scale_z
            ey = center_y - cur_y * scale_y
            # Dibujar el haz siempre que alguna porción caiga dentro del rect
            beam_end = (int(ex), int(ey))
            pygame.draw.line(self.screen, ELECTRON_BEAM, gun_center, beam_end, 3)
            pygame.draw.line(self.screen, WHITE, gun_center, beam_end, 1)

        if len(self.electron.path) > 1:
            points = []
            for (px, py, pz) in self.electron.path:
                x_px = view_rect.x + 70 + pz * scale_z
                y_px = center_y - py * scale_y
                if view_rect.collidepoint(x_px, y_px):
                    points.append((int(x_px), int(y_px)))
            
            if len(points) > 1:
                pygame.draw.lines(self.screen, TRACE_GREEN, False, points, 2)

        # Electrón actual (si está dentro)
        if self.electron.path:
            cur_x, cur_y, cur_z = self.electron.path[-1]
            ex = view_rect.x + margin_left + min(cur_z, physical_screen_distance) * scale_z
            ey = center_y - cur_y * scale_y
            pygame.draw.circle(self.screen, YELLOW, (int(ex), int(ey)), 4)

        # Información
        deflection_text = f"Deflexión Y: {self.electron.y * 1000:.2f} mm" 
        voltage_text = f"Voltaje V: {vertical_voltage:.1f} V" 
        info1 = self.font_small.render(deflection_text, True, WHITE) 
        info2 = self.font_small.render(voltage_text, True, WHITE) 
        self.screen.blit(info1, (view_rect.x + 10, view_rect.y + view_rect.height - 55)) 
        self.screen.blit(info2, (view_rect.x + 10, view_rect.y + view_rect.height - 35))
        
    def draw_top_view(self):
        """Dibujar vista superior (deflexión horizontal)"""
        view_rect = pygame.Rect(575, 50, 500, 300)
        pygame.draw.rect(self.screen, BLACK, view_rect)
        pygame.draw.rect(self.screen, WHITE, view_rect, 2)
        
        # Título
        title = self.font_label.render("Vista Superior (Deflexión Horizontal)", True, GREEN)
        self.screen.blit(title, (view_rect.x + 10, view_rect.y - 30))
        
        # Cañón
        gun_rect = pygame.Rect(view_rect.x + 20, view_rect.y + 140, 40, 20)
        pygame.draw.rect(self.screen, GRAY, gun_rect)
        gun_text = self.font_small.render("Cañón", True, WHITE)
        self.screen.blit(gun_text, (gun_rect.x, gun_rect.y - 15))
        
        # Placas horizontales
        _, horizontal_voltage = self.get_voltages()
        plate_color_left = RED if horizontal_voltage > 0 else BLUE if horizontal_voltage < 0 else GRAY
        plate_color_right = BLUE if horizontal_voltage > 0 else RED if horizontal_voltage < 0 else GRAY
        
        left_plate = pygame.Rect(view_rect.x + 200, view_rect.y + 110, 8, 80)
        pygame.draw.rect(self.screen, plate_color_left, left_plate)
        if horizontal_voltage != 0:
            sign_left = "+" if horizontal_voltage > 0 else "-"
            sign_text = self.font_small.render(sign_left, True, WHITE)
            self.screen.blit(sign_text, (left_plate.x - 15, left_plate.y + 35))
        
        right_plate = pygame.Rect(view_rect.x + 272, view_rect.y + 110, 8, 80)
        pygame.draw.rect(self.screen, plate_color_right, right_plate)
        if horizontal_voltage != 0:
            sign_right = "-" if horizontal_voltage > 0 else "+"
            sign_text = self.font_small.render(sign_right, True, WHITE)
            self.screen.blit(sign_text, (right_plate.x + 15, right_plate.y + 35))
        
        plate_text = self.font_small.render("Placas H", True, WHITE)
        self.screen.blit(plate_text, (view_rect.x + 220, view_rect.y + 80))
        
        # Pantalla
        screen_rect = pygame.Rect(view_rect.x + 450, view_rect.y + 50, 20, 200)
        pygame.draw.rect(self.screen, DARK_GRAY, screen_rect)
        screen_text = self.font_small.render("Pantalla", True, WHITE)
        self.screen.blit(screen_text, (screen_rect.x - 10, screen_rect.y - 15))
        
        # Escalado físico -> píxeles (mismo physical_screen_distance)
        physical_screen_distance = (DISTANCE_GUN_TO_PLATES + PLATE_LENGTH +
                                    DISTANCE_BETWEEN_PLATES + PLATE_LENGTH + DISTANCE_TO_SCREEN)
        margin_left = 70
        usable_width = view_rect.width - margin_left - 20
        scale_z = usable_width / physical_screen_distance
        scale_x = (view_rect.height - 40) / SCREEN_SIZE
        center_y = view_rect.y + view_rect.height // 2
        gun_center = (gun_rect.x + gun_rect.width, gun_rect.y + gun_rect.height // 2)

        # Haz (clampado a pantalla)
        if self.beam_visible and self.electron.path:
            cur_x, cur_y, cur_z = self.electron.path[-1]
            z_vis = min(cur_z, physical_screen_distance)
            ex = view_rect.x + margin_left + z_vis * scale_z
            ey = center_y - cur_x * scale_x
            pygame.draw.line(self.screen, ELECTRON_BEAM, gun_center, (int(ex), int(ey)), 3)
            pygame.draw.line(self.screen, WHITE, gun_center, (int(ex), int(ey)), 1)
        
        if len(self.electron.path) > 1:
            points = []
            for (px, py, pz) in self.electron.path:
                x_px = view_rect.x + 70 + pz * scale_z
                y_px = center_y - px * scale_x  # X en vista superior
                if view_rect.collidepoint(x_px, y_px):
                    points.append((int(x_px), int(y_px)))
            
            if len(points) > 1:
                pygame.draw.lines(self.screen, TRACE_GREEN, False, points, 2)

        # Electrón actual
        if self.electron.path:
            cur_x, cur_y, cur_z = self.electron.path[-1]
            ex = view_rect.x + margin_left + min(cur_z, physical_screen_distance) * scale_z
            ey = center_y - cur_x * scale_x
            pygame.draw.circle(self.screen, YELLOW, (int(ex), int(ey)), 4)
                
        # Información
        deflection_text = f"Deflexión X: {self.electron.x * 1000:.2f} mm"
        voltage_text = f"Voltaje H: {horizontal_voltage:.1f} V"
        info1 = self.font_small.render(deflection_text, True, WHITE)
        info2 = self.font_small.render(voltage_text, True, WHITE)
        self.screen.blit(info1, (view_rect.x + 10, view_rect.y + view_rect.height - 55))
        self.screen.blit(info2, (view_rect.x + 10, view_rect.y + view_rect.height - 35))

    def draw_screen_view(self):
        """Dibujar pantalla del CRT según especificaciones"""
        view_rect = pygame.Rect(240, 385, 650, 400)
        pygame.draw.rect(self.screen, BLACK, view_rect)
        pygame.draw.rect(self.screen, WHITE, view_rect, 2)
        
        # Título
        title = self.font_label.render("PANTALLA - Aquí impactan los electrones", True, GREEN)
        self.screen.blit(title, (view_rect.x + 10, view_rect.y - 20))
        
        # Grid de referencia
        grid_spacing = 50
        for i in range(grid_spacing, view_rect.width, grid_spacing):
            pygame.draw.line(self.screen, DARK_GRAY, 
                           (view_rect.x + i, view_rect.y), 
                           (view_rect.x + i, view_rect.y + view_rect.height))
        for i in range(grid_spacing, view_rect.height, grid_spacing):
            pygame.draw.line(self.screen, DARK_GRAY, 
                           (view_rect.x, view_rect.y + i), 
                           (view_rect.x + view_rect.width, view_rect.y + i))
        
        # Centro con cruz
        center_x = view_rect.x + view_rect.width // 2
        center_y = view_rect.y + view_rect.height // 2
        pygame.draw.line(self.screen, WHITE, (center_x - 20, center_y), (center_x + 20, center_y), 2)
        pygame.draw.line(self.screen, WHITE, (center_x, center_y - 20), (center_x, center_y + 20), 2)
        
        # Trazas con persistencia
        persistence = self.sliders['persistence'].val
        current_time = self.time
        
        # escalas para mapear coordenadas físicas (m) a pixeles
        scale_x = (view_rect.width - 40) / SCREEN_SIZE
        scale_y = (view_rect.height - 40) / SCREEN_SIZE
        
        for trace in self.screen_traces:
            age = current_time - trace['time']
            if age < persistence * 2:
                alpha = max(0.1, 1 - age / (persistence * 2))
                
                screen_x = center_x + (trace['x'] * scale_x)
                screen_y = center_y - (trace['y'] * scale_y)  # Y invertido
                
                if view_rect.collidepoint(screen_x, screen_y):
                    brightness = trace.get('brightness', 1.0)
                    intensity = int(255 * alpha * brightness)
                    color = (0, intensity, int(intensity * 0.8))
                    
                    size = max(2, int(7 * alpha * brightness))
                    pygame.draw.circle(self.screen, color, (int(screen_x), int(screen_y)), size)

        # Electrón actual proyectado en la pantalla (x,y)
        if self.electron.path:
            cur_x, cur_y, _ = self.electron.path[-1]
            screen_x = center_x + cur_x * scale_x
            screen_y = center_y - cur_y * scale_y
            if view_rect.collidepoint(screen_x, screen_y):
                pygame.draw.circle(self.screen, YELLOW, (int(screen_x), int(screen_y)), 4)

    def draw_controls(self):
        """Dibujar panel de controles y botones"""
        control_rect = pygame.Rect(WINDOW_WIDTH - CONTROL_PANEL_WIDTH, 0, CONTROL_PANEL_WIDTH, WINDOW_HEIGHT)
        pygame.draw.rect(self.screen, (20, 20, 40), control_rect)
        pygame.draw.line(self.screen, WHITE, (control_rect.x, 0), (control_rect.x, WINDOW_HEIGHT), 2)

        # Título del panel
        title = self.font_title.render("Controles", True, GREEN)
        self.screen.blit(title, (control_rect.x + 20, 20))

        # Sección de modo
        mode_text = self.font_label.render("Modo de Control", True, WHITE)
        self.screen.blit(mode_text, (control_rect.x + 20, 165))

        # Botones de modo
        self.buttons['manual'].draw(self.screen)
        self.buttons['lissajous'].draw(self.screen)
        
        # Controles básicos
        basic_text = self.font_label.render("Controles Básicos", True, WHITE)
        self.screen.blit(basic_text, (control_rect.x + 20, 50))
        self.sliders['acceleration_voltage'].draw(self.screen)
        self.sliders['persistence'].draw(self.screen)

        # Controles específicos del modo
        if self.mode == 'manual':
            manual_text = self.font_label.render("Control Manual", True, WHITE)
            self.screen.blit(manual_text, (control_rect.x + 20, 225))
            self.sliders['vertical_voltage'].draw(self.screen)
            self.sliders['horizontal_voltage'].draw(self.screen)
        else:
            liss_text = self.font_label.render("Figuras de Lissajous", True, WHITE)
            self.screen.blit(liss_text, (control_rect.x + 20, 225))
            self.sliders['vert_amplitude'].draw(self.screen)
            self.sliders['vert_frequency'].draw(self.screen)
            self.sliders['vert_phase'].draw(self.screen)
            self.sliders['horiz_amplitude'].draw(self.screen)
            self.sliders['horiz_frequency'].draw(self.screen)
            self.sliders['horiz_phase'].draw(self.screen)
            self.buttons['preset_lissajous'].draw(self.screen)
            if self.show_presets:
                rows = list(self.lissajous_presets.keys())
                cols = ["0°", "45°", "90°", "135°", "180°"]

                cell_w = 80
                cell_h = 30
                start_x = control_rect.x + 20
                start_y = 600

                # Fondo del menú
                menu_w = cell_w * (len(cols) + 1) + 20
                menu_h = cell_h * (len(rows) + 1) + 20
                menu_rect = pygame.Rect(start_x - 10, start_y - 10, menu_w, menu_h)
                pygame.draw.rect(self.screen, DARK_GRAY, menu_rect)
                pygame.draw.rect(self.screen, WHITE, menu_rect, 2)

                # Título
                title = self.font_label.render("Tabla de Presets Lissajous", True, YELLOW)
                self.screen.blit(title, (start_x, start_y - 25))

                # Reiniciar botones
                self.preset_buttons = []

                # Dibujar cabecera de fases
                for j, col in enumerate(cols):
                    label = self.font_small.render(col, True, CYAN)
                    self.screen.blit(label, (start_x + (j+1)*cell_w + 10, start_y))

                # Dibujar filas y celdas
                for i, row in enumerate(rows):
                    # Etiqueta de frecuencia
                    label = self.font_small.render(row, True, CYAN)
                    self.screen.blit(label, (start_x, start_y + (i+1)*cell_h + 5))

                    # Botones de presets
                    for j, preset in enumerate(self.lissajous_presets[row]):
                        btn_x = start_x + (j+1)*cell_w
                        btn_y = start_y + (i+1)*cell_h
                        btn = Button(btn_x, btn_y, cell_w-5, cell_h-5, preset["name"])
                        btn.draw(self.screen)
                        self.preset_buttons.append((btn, preset))

        # Botones de control
        control_buttons_text = self.font_label.render("Controles", True, WHITE)
        self.screen.blit(control_buttons_text, (control_rect.x + 20, 525))
        self.buttons['clear'].draw(self.screen)
        self.buttons['pause'].draw(self.screen)
        self.buttons['beam_toggle'].draw(self.screen)

        # Información adicional (espaciados para evitar solapes)
        info_y = 620
        status = "PAUSADO" if self.simulation_speed == 0 else "EJECUTANDO"
        vertical_voltage, horizontal_voltage = self.get_voltages()
        info_texts = [
            f"Estado: {status}",
            f"Tiempo: {self.time/1000:.1f}s",
            f"Modo: {self.mode.capitalize()}",
            f"V_vert: {vertical_voltage:.1f}V",
            f"V_horiz: {horizontal_voltage:.1f}V"
        ]
        for i, text in enumerate(info_texts):
            color = GREEN if i == 1 and status == "EJECUTANDO" else LIGHT_GRAY
            if i == 1 and status == "PAUSADO":
                color = RED
            surface = self.font_small.render(text, True, color)
            self.screen.blit(surface, (control_rect.x + 20, info_y + i * 16))

        # Ayuda de teclado
        help_y = info_y + len(info_texts) * 16 + 10
        help_texts = [
            "Teclas:",
            "ESPACIO: Pausa/Resume",
            "C: Limpiar pantalla",
            "R: Reset electrón",
            "B: Haz ON/OFF"
        ]
        for i, text in enumerate(help_texts):
            color = YELLOW if i == 0 else LIGHT_GRAY
            surface = self.font_small.render(text, True, color)
            self.screen.blit(surface, (control_rect.x + 20, help_y + i * 12))

    def draw(self):
        """Dibujar toda la interfaz"""
        # Fondo gradiente
        for y in range(WINDOW_HEIGHT):
            color_intensity = int(30 + (50 - 30) * (y / WINDOW_HEIGHT))
            color = (color_intensity, color_intensity + 20, color_intensity + 50)
            pygame.draw.line(self.screen, color, (0, y), (WINDOW_WIDTH - CONTROL_PANEL_WIDTH, y))

        # Vistas
        self.draw_side_view()
        self.draw_top_view()
        self.draw_screen_view()

        # Controles
        self.draw_controls()

        # FPS
        fps = self.clock.get_fps()
        fps_text = self.font_small.render(f"FPS: {fps:.1f}", True, WHITE)
        self.screen.blit(fps_text, (10, 10))

        # Actualizar pantalla
        pygame.display.flip()

    def run(self):
        """Bucle principal de la simulación"""
        print("=" * 60)
        print("SIMULACIÓN CRT - UNIVERSIDAD DEL VALLE DE GUATEMALA")
        print("Laboratorio de Física 3 - Proyecto #2")
        print("Simulación del Tubo de Rayos Catódicos")
        print("=" * 60)
        print("\nCaracterísticas de la simulación:")
        print("- Deflexión vertical y horizontal independientes")
        print("- Modo manual y figuras de Lissajous")
        print("- Física realista basada en ecuaciones de movimiento")
        print("- Visualización 3D con vistas lateral y superior")
        print("- Pantalla con efecto de persistencia")
        print("- HAZ LÁSER visible en todas las vistas")
        print("\nInicializando simulación...")

        while self.running:
            self.handle_events()
            self.update_physics()
            self.draw()
            self.clock.tick(60)
            if self.simulation_speed > 0:
                self.time += 16  # 16ms por frame

        pygame.quit()
        sys.exit()

# Punto de entrada principal
if __name__ == "__main__":
    try:
        simulation = CRTSimulation()
        simulation.run()
    except Exception as e:
        print(f"\nError en la simulación: {e}")
        import traceback
        traceback.print_exc()
        pygame.quit()
        sys.exit(1)