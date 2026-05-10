import pygame
import math
import random
import sys
import os
from pygame.locals import *

pygame.init()

try:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
except:
    pass

# --- 16:9 CONFIGURATION ---
INTERNAL_WIDTH = 960  
INTERNAL_HEIGHT = 540
NUM_RAYS = 240 
SCALE = INTERNAL_WIDTH / NUM_RAYS

# Gameplay Constants
FOV = 90
HALF_FOV = math.radians(FOV / 2)
RAD_FOV = math.radians(FOV)
MAX_DEPTH = 800
TILE_SIZE = 100
MAP_SIZE = 21
BATTERY_RESPAWN_DELAY = 30 * 60 
MAX_BATTERIES = 4

master_volume = 1.0
sound_volumes = {
    "footstep": 0.1,
    "ambient": 0.4,
    "locker_open": 0.8,
    "locker_close": 0.8,
    "key_pickup": 0.7,
    "battery_pickup": 0.3,
    "flashlight": 1.0,
    "breathing": 0.6,
    "chase": 0.5,
    "enemy_near": 0.5,
    "enemy_spotted": 0.8
}

# Global dynamic variables
mouse_sensitivity = 0.002
flashlight_on = True
flashlight_battery = 1000
is_fullscreen = False
z_buffer = [MAX_DEPTH] * NUM_RAYS

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (220, 20, 20)
GREEN = (20, 220, 20)
GRAY = (80, 80, 80)
SILVER = (192, 192, 192) 
YELLOW = (255, 255, 0)
PURPLE = (100, 0, 100)
LOCKER_COL = (45, 60, 85) 

flags = DOUBLEBUF | HWSURFACE
screen = pygame.display.set_mode((INTERNAL_WIDTH, INTERNAL_HEIGHT), flags)
game_surface = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = "assets" 

def get_image(filename, fallback_col):
    abs_path = os.path.join(BASE_PATH, ASSET_DIR, *filename.split("/"))
    try:
        if os.path.exists(abs_path):
            img = pygame.image.load(abs_path).convert_alpha()
            return img
    except:
        pass
    surf = pygame.Surface((128, 128), pygame.SRCALPHA)
    surf.fill(fallback_col)
    return surf

SPRITE_ENEMY_FRONT = get_image("Sprites (Final)/enemy_front.png", RED)
SPRITE_ENEMY_BACK  = get_image("Sprites (Final)/enemy_back.png", (150, 0, 0))
SPRITE_BATTERY     = get_image("Sprites (Final)/battery.png", YELLOW)
SPRITE_KEY         = get_image("Sprites (Final)/key.png", SILVER)

# --- AUDIO CONFIGURATION ---
pygame.mixer.init()

def get_sound(filename, volume_key):
    abs_path = os.path.join(BASE_PATH, ASSET_DIR, "sounds", filename)
    try:
        if os.path.exists(abs_path):
            snd = pygame.mixer.Sound(abs_path)
            snd.set_volume(sound_volumes.get(volume_key, 1.0) * master_volume)
            return snd
    except: 
        pass
    return None

SND_WALK = get_sound("footstep.wav", "footstep")
SND_AMBIENT = get_sound("ambient_suspense.wav", "ambient")
SND_LOCKER_OPEN = get_sound("locker_open.wav", "locker_open")
SND_LOCKER_CLOSE = get_sound("locker_close.wav", "locker_close")
SND_KEY = get_sound("key_pickup.wav", "key_pickup")
SND_BATTERY = get_sound("battery_pickup.wav", "battery_pickup")
SND_FL_ON = get_sound("flashlight_on.wav", "flashlight")
SND_FL_OFF = get_sound("flashlight_off.wav", "flashlight")
SND_BREATH = get_sound("breathing.wav", "breathing")
SND_CHASE = get_sound("chase_music.wav", "chase")
SND_ENEMY_NEAR = get_sound("enemy_near.wav", "enemy_near")
SND_ENEMY_SPOTTED = get_sound("enemy_spotted.wav", "enemy_spotted")

CH_WALK = pygame.mixer.Channel(0)
CH_AMBIENT = pygame.mixer.Channel(1)
CH_PROXIMITY = pygame.mixer.Channel(2)
CH_CHASE = pygame.mixer.Channel(3)
CH_ENEMY_PROX = pygame.mixer.Channel(4) 

MENU_MUSIC_PATH = os.path.join(BASE_PATH, ASSET_DIR, "sounds", "menu_theme.mp3")

# --- CLASSES ---

class Battery:
    def __init__(self):
        self.respawn_timer = 0
        self.picked_up = True 
        self.x, self.y = 0, 0
        self.respawn()

    def update(self):
        if self.picked_up:
            self.respawn_timer -= 1
            if self.respawn_timer <= 0: self.respawn()

    def respawn(self):
        while True:
            tx, ty = random.randint(1, MAP_SIZE-2), random.randint(1, MAP_SIZE-2)
            if world_map[ty][tx] == 0:
                new_x, new_y = tx * TILE_SIZE + 50, ty * TILE_SIZE + 50
                dist_to_player = math.hypot(new_x - player.x, new_y - player.y)
                too_close_to_battery = False
                for b in batteries:
                    if b != self and not b.picked_up:
                        if math.hypot(new_x - b.x, new_y - b.y) < 400:
                            too_close_to_battery = True
                            break
                if dist_to_player > 200 and not too_close_to_battery:
                    self.x, self.y = new_x, new_y
                    self.picked_up = False
                    break

class Key:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.picked_up = False

class Locker:
    def __init__(self, tile_x, tile_y, current_map):
        self.tile_x, self.tile_y = tile_x, tile_y
        self.width, self.depth = 60, 15 
        self.x = (tile_x * TILE_SIZE) + (TILE_SIZE - self.width) // 2
        if tile_y > 0 and current_map[tile_y-1][tile_x] == 1: self.y = (tile_y * TILE_SIZE) + 1
        elif tile_y < MAP_SIZE - 1 and current_map[tile_y+1][tile_x] == 1: self.y = (tile_y * TILE_SIZE) + TILE_SIZE - self.depth - 1
        elif tile_x > 0 and current_map[tile_y][tile_x-1] == 1: 
            self.width, self.depth = 15, 60
            self.x = (tile_x * TILE_SIZE) + 1
            self.y = (tile_y * TILE_SIZE) + (TILE_SIZE - self.depth) // 2
        elif tile_x < MAP_SIZE - 1 and current_map[tile_y][tile_x+1] == 1: 
            self.width, self.depth = 15, 60
            self.x = (tile_x * TILE_SIZE) + TILE_SIZE - self.width - 1
            self.y = (tile_y * TILE_SIZE) + (TILE_SIZE - self.depth) // 2
        else: self.y = (tile_y * TILE_SIZE) + (TILE_SIZE - self.depth) // 2
        self.rect = pygame.Rect(self.x, self.y, self.width, self.depth)

class Player:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.reset(x, y)
    def reset(self, x, y):
        self.x, self.y = x, y
        self.angle, self.speed = 4.8, 3
        self.is_hiding, self.exit_pos = False, (x, y)
        self.current_locker, self.keys_collected = None, 0
        
    def move(self, keys):
        if self.is_hiding: return 
        sin_a, cos_a = math.sin(self.angle), math.cos(self.angle)
        dx, dy = 0, 0
        if keys[K_w] or keys[K_UP]: dx, dy = self.speed * cos_a, self.speed * sin_a
        if keys[K_s] or keys[K_DOWN]: dx, dy = -self.speed * cos_a, -self.speed * sin_a
        if keys[K_a] or keys[K_LEFT]: dx, dy = self.speed * sin_a, -self.speed * cos_a
        if keys[K_d] or keys[K_RIGHT]: dx, dy = -self.speed * sin_a, self.speed * cos_a
        if (dx != 0 or dy != 0) and not CH_WALK.get_busy():
            if SND_WALK: CH_WALK.play(SND_WALK)
        margin = 28
        tx_next = int((self.x + dx + (margin if dx>0 else -margin)) // TILE_SIZE)
        ty_next = int((self.y + dy + (margin if dy>0 else -margin)) // TILE_SIZE)
        can_move_x = world_map[int(self.y // TILE_SIZE)][tx_next] == 0
        can_move_y = world_map[ty_next][int(self.x // TILE_SIZE)] == 0
        new_rect_x = pygame.Rect(self.x + dx - 10, self.y - 10, 20, 20)
        new_rect_y = pygame.Rect(self.x - 10, self.y + dy - 10, 20, 20)
        for lock in lockers_list:
            if new_rect_x.colliderect(lock.rect): can_move_x = False
            if new_rect_y.colliderect(lock.rect): can_move_y = False
        if can_move_x: self.x += dx
        if can_move_y: self.y += dy

    def interact(self):
        global flashlight_battery
        if self.is_hiding:
            if SND_LOCKER_CLOSE: SND_LOCKER_CLOSE.play()
            self.x, self.y = self.exit_pos
            self.is_hiding, self.current_locker = False, None
            return None
        for b in batteries:
            if not b.picked_up and math.hypot(self.x - b.x, self.y - b.y) < 60:
                if SND_BATTERY: SND_BATTERY.play()
                b.picked_up, flashlight_battery = True, min(1000, flashlight_battery + 350)
                b.respawn_timer = BATTERY_RESPAWN_DELAY
                return "PICKED_BATTERY"
        tx, ty = int(self.x // TILE_SIZE), int(self.y // TILE_SIZE)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                nx, ny = tx + dx, ty + dy
                if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and world_map[ny][nx] == 3:
                    if math.hypot(self.x - (nx * TILE_SIZE + 50), self.y - (ny * TILE_SIZE + 50)) < 120:
                        return "WIN" if self.keys_collected >= 15 else "LOCKED"
        for lock in lockers_list:
            if math.hypot(self.x - (lock.x + lock.width/2), self.y - (lock.y + lock.depth/2)) < 65:
                if SND_LOCKER_OPEN: SND_LOCKER_OPEN.play()
                self.exit_pos, self.is_hiding, self.current_locker = (self.x, self.y), True, lock
                self.x, self.y = lock.x + lock.width/2, lock.y + lock.depth/2
                return "HIDDEN"
        return None

class Enemy:
    def __init__(self, x, y):
        self.start_x, self.start_y = x, y
        self.last_dx, self.last_dy = 0, 0
        self.reset()
    def reset(self):
        self.x, self.y = self.start_x, self.start_y
        self.speed_wander, self.speed_chase = 0.8, 1.2
        self.detection_range, self.is_chasing = 600, False
        self.wander_angle = random.uniform(0, math.pi * 2)
    def update(self, player):
        dx_p, dy_p = player.x - self.x, player.y - self.y
        dist = math.hypot(dx_p, dy_p)
        can_see = False
        if not player.is_hiding and flashlight_on and dist < self.detection_range:
            angle_to_player = math.atan2(dy_p, dx_p)
            can_see = True
            for d in range(0, int(dist), 25):
                tx, ty = int((self.x + d * math.cos(angle_to_player)) // TILE_SIZE), int((self.y + d * math.sin(angle_to_player)) // TILE_SIZE)
                if 0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE:
                    if world_map[ty][tx] in [1, 3]: 
                        can_see = False
                        break
        ex, ey = 0, 0
        if can_see:
            if not self.is_chasing: 
                if SND_ENEMY_SPOTTED: SND_ENEMY_SPOTTED.play()
            self.is_chasing = True
            angle = math.atan2(dy_p, dx_p)
            ex, ey = self.speed_chase * math.cos(angle), self.speed_chase * math.sin(angle)
        else:
            self.is_chasing = False
            ex, ey = self.speed_wander * math.cos(self.wander_angle), self.speed_wander * math.sin(self.wander_angle)
        margin = 15
        moved_x, moved_y = False, False
        if world_map[int(self.y // TILE_SIZE)][int((self.x + ex + (margin if ex>0 else -margin)) // TILE_SIZE)] == 0: 
            self.x += ex
            moved_x = True
        if world_map[int((self.y + ey + (margin if ey>0 else -margin)) // TILE_SIZE)][int(self.x // TILE_SIZE)] == 0: 
            self.y += ey
            moved_y = True
        else: self.wander_angle = random.uniform(0, math.pi * 2)
        self.last_dx, self.last_dy = (ex if moved_x else 0), (ey if moved_y else 0)
        return dist 

# --- WORLD MAP & SETUP ---

world_map = [
    [1,1,1,1,1,1,1,1,1,1,3,1,1,1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1,1,1,0,1,1,1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1,1,1,0,1,1,1,1,1,1,1,1,1,1],
    [1,0,0,0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,2,0,1],
    [1,0,1,1,0,1,0,1,1,1,1,1,1,1,0,1,1,1,1,0,1],
    [1,0,1,2,0,1,0,0,0,1,0,0,0,1,0,1,0,0,0,0,1],
    [1,0,1,1,1,1,1,1,0,1,0,1,0,1,0,1,0,1,1,1,1],
    [1,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,1,0,0,1],
    [1,1,1,1,1,0,1,1,1,1,1,1,1,1,1,1,0,1,2,1,1],
    [1,0,0,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,1,0,1,0,1,0,1,1,2,1,1,0,1,1,1,1,1,0,1],
    [1,0,1,0,0,0,0,0,1,0,0,0,1,0,1,0,0,0,0,0,1],
    [1,0,1,1,1,1,1,1,1,0,1,0,1,0,1,0,1,1,1,0,1],
    [1,0,0,0,2,1,0,0,0,0,1,0,0,0,0,0,1,2,1,0,1],
    [1,1,1,0,1,1,0,1,1,1,1,1,1,1,1,0,1,0,1,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0,0,0,0,1],
    [1,0,1,1,1,1,1,1,1,1,0,1,0,1,1,1,1,1,1,0,1],
    [1,0,0,0,0,2,0,0,0,1,0,1,0,0,0,0,0,0,0,0,1],
    [1,1,1,1,1,0,1,1,1,1,0,1,1,1,1,1,0,1,1,1,1],
    [1,2,0,0,0,0,0,0,2,1,0,1,2,0,0,0,0,0,0,2,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
]

lockers_list, locker_lookup = [], {}
for row_idx, row in enumerate(world_map):
    for col_idx, tile in enumerate(row):
        if tile == 2:
            l = Locker(col_idx, row_idx, world_map)
            lockers_list.append(l)
            locker_lookup[(col_idx, row_idx)] = l
            world_map[row_idx][col_idx] = 0 # FIXED: Only set locker tile to 0

player = Player(1050, 1950)
enemies = [Enemy(150, 350), Enemy(1950, 350), Enemy(1050, 950)]
batteries = []
for _ in range(MAX_BATTERIES):
    batteries.append(Battery())

def generate_keys():
    new_keys = []
    while len(new_keys) < 15:
        tx, ty = random.randint(1, MAP_SIZE-2), random.randint(1, MAP_SIZE-2)
        if world_map[ty][tx] == 0:
            kx, ky = tx * TILE_SIZE + 50, ty * TILE_SIZE + 50
            too_close_to_key = any(math.hypot(kx - k.x, ky - k.y) < 300 for k in new_keys)
            too_close_to_battery = any(math.hypot(kx - b.x, ky - b.y) < 200 for b in batteries)
            if not too_close_to_key and not too_close_to_battery:
                new_keys.append(Key(kx, ky))
    return new_keys

keys_list = generate_keys()
clock = pygame.time.Clock()
font_sm = pygame.font.Font(None, 36)
font_lg = pygame.font.Font(None, 74)

# --- ENGINE FUNCTIONS ---

def cast_ray(px, py, pa, ra):
    cos_a, sin_a = math.cos(ra), math.sin(ra)
    x_map, y_map = int(px // TILE_SIZE), int(py // TILE_SIZE)
    delta_dist_x, delta_dist_y = abs(1 / (cos_a + 1e-10)), abs(1 / (sin_a + 1e-10))
    if cos_a < 0: step_x, side_dist_x = -1, (px / TILE_SIZE - x_map) * delta_dist_x
    else: step_x, side_dist_x = 1, (x_map + 1.0 - px / TILE_SIZE) * delta_dist_x
    if sin_a < 0: step_y, side_dist_y = -1, (py / TILE_SIZE - y_map) * delta_dist_y
    else: step_y, side_dist_y = 1, (y_map + 1.0 - py / TILE_SIZE) * delta_dist_y
    wall_hit, dist_travelled, tile_type, side = False, 0, 1, 0
    while not wall_hit and dist_travelled < MAX_DEPTH:
        if (x_map, y_map) in locker_lookup:
            lock = locker_lookup[(x_map, y_map)]
            if not (player.is_hiding and player.current_locker == lock):
                for i in range(0, TILE_SIZE, 5): 
                    rx, ry = px + cos_a * (dist_travelled + i), py + sin_a * (dist_travelled + i)
                    if lock.rect.collidepoint(rx, ry): return (dist_travelled+i) * math.cos(ra-pa), (x_map,y_map), 0, (dist_travelled+i), 2
        if side_dist_x < side_dist_y: dist_travelled, side_dist_x, x_map, side = side_dist_x * TILE_SIZE, side_dist_x + delta_dist_x, x_map + step_x, 0
        else: dist_travelled, side_dist_y, y_map, side = side_dist_y * TILE_SIZE, side_dist_y + delta_dist_y, y_map + step_y, 1
        if 0 <= x_map < MAP_SIZE and 0 <= y_map < MAP_SIZE:
            if world_map[y_map][x_map] in [1, 3]: wall_hit, tile_type = True, world_map[y_map][x_map]
        else: break
    wall_dist = (side_dist_x - delta_dist_x) if side == 0 else (side_dist_y - delta_dist_y)
    return wall_dist * TILE_SIZE * math.cos(ra - pa), (x_map, y_map), side, wall_dist * TILE_SIZE, tile_type

def draw_sprites(surface):
    all_sprites = []
    for e in enemies:
        v_player_x, v_player_y = player.x - e.x, player.y - e.y
        dot_to_player = (e.last_dx * v_player_x) + (e.last_dy * v_player_y)
        img = SPRITE_ENEMY_FRONT if dot_to_player >= 0 else SPRITE_ENEMY_BACK
        all_sprites.append({'x': e.x, 'y': e.y, 'img': img, 'type': 'E'})
    for b in batteries:
        if not b.picked_up: all_sprites.append({'x': b.x, 'y': b.y, 'img': SPRITE_BATTERY, 'type': 'B'})
    for k in keys_list:
        if not k.picked_up: all_sprites.append({'x': k.x, 'y': k.y, 'img': SPRITE_KEY, 'type': 'K'})
    all_sprites.sort(key=lambda s: math.hypot(player.x - s['x'], player.y - s['y']), reverse=True)
    bob_time = pygame.time.get_ticks() * 0.005
    for s in all_sprites:
        dx, dy = s['x'] - player.x, s['y'] - player.y
        dist = math.hypot(dx, dy)
        if dist > 800 or dist < 10: continue
        theta = math.atan2(dy, dx) - player.angle
        while theta > math.pi: theta -= 2*math.pi
        while theta < -math.pi: theta += 2*math.pi
        if abs(theta) < HALF_FOV + 0.5: 
            proj_dist = dist * math.cos(theta)
            wall_h = 30000 / (proj_dist + 0.0001)
            middle_x = INTERNAL_WIDTH / 2 + theta * INTERNAL_WIDTH / RAD_FOV
            lf = max(0, 1 - (dist/400)**2) if flashlight_on else 0
            it = int(255 * lf)
            if s['type'] == 'E':
                s_width, s_height = int(wall_h * 1.0), int(wall_h * 1.4)
                y_pos = (INTERNAL_HEIGHT / 2) - (s_height / 2)
            else:
                s_width, s_height = int(wall_h * 0.25), int(wall_h * 0.25)
                y_pos = (INTERNAL_HEIGHT / 2) + (wall_h * 0.5) - s_height - (math.sin(bob_time) * (wall_h * 0.05))
            ray_idx = int(middle_x / SCALE)
            if 0 <= ray_idx < NUM_RAYS and dist < z_buffer[ray_idx]:
                scaled_img = pygame.transform.scale(s['img'], (max(1, s_width), max(1, s_height)))
                scaled_img.fill((it, it, it), special_flags=pygame.BLEND_RGB_MULT)
                surface.blit(scaled_img, (middle_x - s_width/2, y_pos))

def update_audio(state):
    if enemies:
        closest_dist = min([math.hypot(player.x - e.x, player.y - e.y) for e in enemies])
    else:
        closest_dist = 9999

    any_chasing = any(e.is_chasing for e in enemies)
    
    if state == "GAME":
        if closest_dist > 500:
            if SND_BREATH and not CH_PROXIMITY.get_busy(): 
                CH_PROXIMITY.play(SND_BREATH, loops=-1)
            CH_PROXIMITY.set_volume(sound_volumes.get("breathing", 0.6) * master_volume)
            CH_ENEMY_PROX.fadeout(500) 
        else:
            CH_PROXIMITY.fadeout(500) 
            if not any_chasing:
                if SND_ENEMY_NEAR and not CH_ENEMY_PROX.get_busy():
                    CH_ENEMY_PROX.play(SND_ENEMY_NEAR, loops=-1)
                CH_ENEMY_PROX.set_volume(sound_volumes.get("enemy_near", 0.5) * master_volume)
            else:
                CH_ENEMY_PROX.fadeout(500) 
    else:
        CH_PROXIMITY.stop()
        CH_ENEMY_PROX.stop()

    if any_chasing and not player.is_hiding and state == "GAME":
        if SND_CHASE and not CH_CHASE.get_busy(): 
            CH_CHASE.play(SND_CHASE, loops=-1)
    else: 
        CH_CHASE.fadeout(1000)

# --- MAIN LOOP ---

def main():
    global flashlight_on, flashlight_battery, is_fullscreen, screen, mouse_sensitivity, z_buffer, keys_list
    
    state = "MENU"
    previous_state = "MENU"
    game_started = False
    running = True
    dragging = False

    # FIXED: Added safety for music loading
    try:
        if os.path.exists(MENU_MUSIC_PATH):
            pygame.mixer.music.load(MENU_MUSIC_PATH)
            pygame.mixer.music.set_volume(0.1)
            pygame.mixer.music.play(-1)
    except:
        pass
        
    while running:
        clock.tick(60)
        keys = pygame.key.get_pressed()
        ww, wh = screen.get_size()
        sf = min(ww/960, wh/540)
        ox, oy = (ww - int(960*sf))//2, (wh - int(540*sf))//2
        mx, my = pygame.mouse.get_pos()
        imx, imy = (mx - ox)/sf, (my - oy)/sf

        for event in pygame.event.get():
            if event.type == QUIT: running = False
            if event.type == MOUSEBUTTONDOWN:
                if state == "MENU":
                    if 380 < imx < 580:
                        if 260 < imy < 300: 
                            state, game_started = "GAME", True
                            pygame.mixer.music.fadeout(1000)
                            if SND_AMBIENT: CH_AMBIENT.play(SND_AMBIENT, loops=-1)
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                            pygame.mouse.get_rel() # FIXED: Clear rel movement
                        elif 310 < imy < 350: 
                            previous_state = "MENU"
                            state = "OPTIONS"
                        elif 360 < imy < 400: running = False

                elif state == "PAUSE":
                    if 380 < imx < 580:
                        if 230 < imy < 270: 
                            state = "GAME"
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                            pygame.mouse.get_rel()
                            pygame.mixer.music.stop()
                            if SND_AMBIENT: CH_AMBIENT.play(SND_AMBIENT, loops=-1)
                        elif 280 < imy < 320: 
                            previous_state = "PAUSE"
                            state = "OPTIONS"
                        elif 330 < imy < 370: 
                            state, game_started = "MENU", False
                            pygame.mixer.music.play(-1)
                        elif 380 < imy < 420: 
                            running = False

                elif state == "OPTIONS":
                    if 380 < imx < 580 and 260 < imy < 280: dragging = True
                    elif 380 < imx < 580 and 340 < imy < 380: state = previous_state
                
                elif state == "DEAD":
                    if 380 < imx < 580:
                        if 230 < imy < 270: 
                            player.reset(1050, 1950)
                            for e in enemies: e.reset()
                            keys_list = generate_keys()
                            for b in batteries: b.respawn()
                            flashlight_battery, flashlight_on, state = 1000, True, "GAME"
                            pygame.mouse.set_visible(False)
                            pygame.event.set_grab(True)
                            pygame.mouse.get_rel()
                            if SND_AMBIENT: CH_AMBIENT.play(SND_AMBIENT, -1)
                        elif 280 < imy < 320: 
                            previous_state = "DEAD"
                            state = "OPTIONS"
                        elif 330 < imy < 370: 
                            state, game_started = "MENU", False
                            pygame.mixer.music.play(-1)
                        elif 380 < imy < 420: 
                            running = False

                elif state == "WIN" and 380 < imx < 580 and 280 < imy < 320:
                    player.reset(1050, 1950)
                    for e in enemies: e.reset()
                    keys_list = generate_keys()
                    for b in batteries: b.respawn()
                    flashlight_battery, flashlight_on, state = 1000, True, "GAME"
                    pygame.mouse.set_visible(False)
                    pygame.event.set_grab(True)
                    pygame.mouse.get_rel()
                    if SND_AMBIENT: CH_AMBIENT.play(SND_AMBIENT, -1)
             
            if event.type == MOUSEBUTTONUP: dragging = False
            
            if event.type == KEYDOWN:
                if event.key == K_BACKQUOTE:
                    is_fullscreen = not is_fullscreen
                    if is_fullscreen:
                        screen = pygame.display.set_mode((0, 0), flags | FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode((INTERNAL_WIDTH, INTERNAL_HEIGHT), flags)
                
                if event.key == K_ESCAPE and state == "GAME": 
                    state = "PAUSE"
                    pygame.mouse.set_visible(True)
                    pygame.event.set_grab(False)
                    CH_AMBIENT.stop()
                    CH_CHASE.stop()
                    pygame.mixer.music.play(-1)
                elif event.key == K_ESCAPE and state == "PAUSE":
                    state = "GAME"
                    pygame.mouse.set_visible(False)
                    pygame.event.set_grab(True)
                    pygame.mouse.get_rel()
                    pygame.mixer.music.stop()
                    if SND_AMBIENT: CH_AMBIENT.play(SND_AMBIENT, loops=-1)
    
                if state == "GAME":
                    if event.key == K_f: 
                        flashlight_on = not flashlight_on
                        if flashlight_on and SND_FL_ON: SND_FL_ON.play()
                        elif not flashlight_on and SND_FL_OFF: SND_FL_OFF.play()
                    if event.key == K_e:
                        res = player.interact()
                        if res == "WIN": 
                            state = "WIN"
                            pygame.mouse.set_visible(True)
                            pygame.event.set_grab(False)
                            CH_AMBIENT.stop()
        
        if state == "GAME":
            if pygame.event.get_grab():
                rx, _ = pygame.mouse.get_rel()
                player.angle += rx * mouse_sensitivity
            player.move(keys)
            for e in enemies:
                d = e.update(player)
                if d < 45 and not player.is_hiding:
                    state = "DEAD"
                    pygame.mouse.set_visible(True)
                    pygame.event.set_grab(False)
                    CH_AMBIENT.stop()
            
            for b in batteries: b.update()
            for k in [k for k in keys_list if not k.picked_up]:
                if math.hypot(player.x - k.x, player.y - k.y) < 45:
                    if SND_KEY: SND_KEY.play()
                    k.picked_up, player.keys_collected = True, player.keys_collected + 1
    
            if flashlight_on:
                flashlight_battery -= 0.15
                if flashlight_battery <= 0: flashlight_battery, flashlight_on = 0, False
            
            update_audio(state)

            game_surface.fill(BLACK)
            sa = player.angle - HALF_FOV
            for r in range(NUM_RAYS):
                ra = sa + r * RAD_FOV / NUM_RAYS
                d, t, side, rd, tt = cast_ray(player.x, player.y, player.angle, ra)
                z_buffer[r] = rd
                h = 42000 / (max(1, d) + 0.0001) # FIXED: Safety max
                it = 255 / (1 + d*d*0.00003)
                bc = (it*0.35, it*0.35, it*0.35) if tt == 3 else (LOCKER_COL[0]*it/255, LOCKER_COL[1]*it/255, LOCKER_COL[2]*it/255) if tt == 2 else (it*0.4*(1 if side==0 else 0.7), it*0.2*(1 if side==0 else 0.7), it*0.2*(1 if side==0 else 0.7))
                lf = max(0, 1 - (d/380)**2) if flashlight_on else 0
                pygame.draw.rect(game_surface, tuple(int(c * lf) for c in bc), (int(r * SCALE), 270 - h/2, math.ceil(SCALE)+1, h))
            draw_sprites(game_surface)
            
            if player.is_hiding:
                vignette = pygame.Surface((960, 540), pygame.SRCALPHA)
                pygame.draw.rect(vignette, (0,0,0,200), (0,0,960,120))
                pygame.draw.rect(vignette, (0,0,0,200), (0,420,960,120))
                game_surface.blit(vignette, (0,0))
                pr = font_sm.render("[E] EXIT LOCKER", True, YELLOW)
                game_surface.blit(pr, pr.get_rect(center=(480, 480)))
            else:
                current_prompt = None
                tx, ty = int(player.x // TILE_SIZE), int(player.y // TILE_SIZE)
                near_door = False
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        nx, ny = tx + dx, ty + dy
                        if 0 <= nx < MAP_SIZE and 0 <= ny < MAP_SIZE and world_map[ny][nx] == 3:
                            if math.hypot(player.x - (nx * TILE_SIZE + 50), player.y - (ny * TILE_SIZE + 50)) < 120:
                                near_door = True
                                break
                if near_door:
                    if player.keys_collected < 15:
                        current_prompt = font_sm.render(f"COLLECT ALL 15 KEYS ({player.keys_collected}/15)", True, RED)
                    else:
                        current_prompt = font_sm.render("[E] ESCAPE", True, GREEN)
                if not current_prompt:
                    for b in batteries:
                        if not b.picked_up and math.hypot(player.x - b.x, player.y - b.y) < 70:
                            current_prompt = font_sm.render("[E] TAKE BATTERY", True, YELLOW)
                            break
                if not current_prompt:
                    for lock in lockers_list:
                        if math.hypot(player.x - (lock.x + lock.width/2), player.y - (lock.y + lock.depth/2)) < 75:
                            current_prompt = font_sm.render("[E] HIDE IN LOCKER", True, WHITE)
                            break
                if current_prompt:
                    game_surface.blit(current_prompt, current_prompt.get_rect(center=(480, 480)))
            
            pygame.draw.circle(game_surface, YELLOW if flashlight_on else (30,30,30), (50,50), 20)
            pygame.draw.rect(game_surface, GREEN if flashlight_battery > 250 else RED, (30,80, max(0, int(flashlight_battery/10)), 10))
            game_surface.blit(font_sm.render(f"KEYS: {player.keys_collected}/15", True, SILVER if player.keys_collected < 15 else GREEN), (30, 100))
         
        elif state == "MENU":
            game_surface.fill(BLACK)
            title = font_lg.render("HIDE & SEEK", True, RED)
            game_surface.blit(title, title.get_rect(center=(480, 150)))
            for i, tx in enumerate(["CONTINUE" if game_started else "START GAME", "OPTIONS", "EXIT"]):
                y = 280 + (i * 50)
                btn = font_sm.render(tx, True, WHITE if (380 < imx < 580 and y-20 < imy < y+20) else GRAY)
                game_surface.blit(btn, btn.get_rect(center=(480, y)))

        elif state == "PAUSE":
            game_surface.fill(BLACK)
            title = font_lg.render("PAUSED", True, WHITE)
            game_surface.blit(title, title.get_rect(center=(480, 150)))
            for i, tx in enumerate(["CONTINUE", "OPTIONS", "MAIN MENU", "EXIT"]):
                y = 250 + (i * 50)
                btn = font_sm.render(tx, True, WHITE if (380 < imx < 580 and y-20 < imy < y+20) else GRAY)
                game_surface.blit(btn, btn.get_rect(center=(480, y)))

        elif state == "OPTIONS":
            game_surface.fill(BLACK)
            title = font_lg.render("OPTIONS", True, WHITE)
            game_surface.blit(title, title.get_rect(center=(480, 150)))
            st = font_sm.render("Sensitivity", True, WHITE)
            game_surface.blit(st, st.get_rect(center=(480, 240)))
            pygame.draw.rect(game_surface, GRAY, (380, 260, 200, 20))
            sx = 380 + (mouse_sensitivity - 0.0005) / 0.0095 * 200
            pygame.draw.circle(game_surface, WHITE, (int(sx), 270), 10)
            back = font_sm.render("BACK", True, WHITE if (380 < imx < 580 and 340 < imy < 380) else GRAY)
            game_surface.blit(back, back.get_rect(center=(480, 360)))
            if dragging: 
                mouse_sensitivity = max(0.0005, min(0.01, 0.0005 + ((imx - 380) / 200) * 0.0095))

        elif state == "DEAD":
            game_surface.fill(BLACK)
            t = font_lg.render("YOU DIED", True, RED)
            game_surface.blit(t, t.get_rect(center=(480, 150)))
            for i, tx in enumerate(["RESTART", "OPTIONS", "MAIN MENU", "EXIT"]):
                y = 250 + (i * 50)
                btn = font_sm.render(tx, True, WHITE if (380 < imx < 580 and y-20 < imy < y+20) else GRAY)
                game_surface.blit(btn, btn.get_rect(center=(480, y)))

        elif state == "WIN":
            game_surface.fill((20, 50, 20))
            t = font_lg.render("YOU ESCAPED!", True, GREEN)
            game_surface.blit(t, t.get_rect(center=(480, 200)))
            r = font_sm.render("PLAY AGAIN", True, WHITE if (380 < imx < 580 and 280 < imy < 320) else GRAY)
            game_surface.blit(r, r.get_rect(center=(480, 300)))

        screen.blit(pygame.transform.scale(game_surface, (int(960*sf), int(540*sf))), (ox, oy))
        pygame.display.flip()
    pygame.quit()

if __name__ == "__main__": 
    main()