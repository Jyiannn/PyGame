import pygame
import math
import random
import sys
from pygame.locals import *

pygame.init()

# --- 16:9 CONFIGURATION ---
INTERNAL_WIDTH = 960  
INTERNAL_HEIGHT = 540
NUM_RAYS = 480 
SCALE = INTERNAL_WIDTH / NUM_RAYS
# --------------------------

FOV = 90
HALF_FOV = math.radians(FOV / 2)
RAD_FOV = math.radians(FOV)
MAX_DEPTH = 1600 
TILE_SIZE = 100
MAP_SIZE = 16

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
DARK_GRAY = (10, 10, 10)
GRAY = (60, 60, 60)
YELLOW = (255, 255, 0)
PURPLE = (100, 0, 100)
LOCKER_COL = (45, 60, 85) 

class Locker:
    def __init__(self, tile_x, tile_y, world_map):
        self.tile_x, self.tile_y = tile_x, tile_y
        self.width = 60 
        self.depth = 15 
        
        self.x = (tile_x * TILE_SIZE) + (TILE_SIZE - self.width) // 2
        self.y = (tile_y * TILE_SIZE) + (TILE_SIZE - self.depth) // 2
        
        if tile_y > 0 and world_map[tile_y-1][tile_x] == 1: 
            self.y = (tile_y * TILE_SIZE) + 1
        elif tile_y < MAP_SIZE - 1 and world_map[tile_y+1][tile_x] == 1: 
            self.y = (tile_y * TILE_SIZE) + TILE_SIZE - self.depth - 1
        elif tile_x > 0 and world_map[tile_y][tile_x-1] == 1: 
            self.width, self.depth = 15, 60
            self.x = (tile_x * TILE_SIZE) + 1
            self.y = (tile_y * TILE_SIZE) + (TILE_SIZE - self.depth) // 2
        elif tile_x < MAP_SIZE - 1 and world_map[tile_y][tile_x+1] == 1: 
            self.width, self.depth = 15, 60
            self.x = (tile_x * TILE_SIZE) + TILE_SIZE - self.width - 1
            self.y = (tile_y * TILE_SIZE) + (TILE_SIZE - self.depth) // 2
            
        self.rect = pygame.Rect(self.x, self.y, self.width, self.depth)

class Player:
    def __init__(self, x, y):
        self.reset(x, y)
        
    def reset(self, x, y):
        self.x, self.y = x, y
        self.angle, self.speed = 0, 3
        self.is_hiding = False
        self.exit_pos = (x, y)
        self.current_locker = None
        self.hit_box_size = 20
        
    def move(self, keys):
        if self.is_hiding: return 
        sin_a, cos_a = math.sin(self.angle), math.cos(self.angle)
        dx, dy = 0, 0
        if keys[K_w] or keys[K_UP]: dx, dy = self.speed * cos_a, self.speed * sin_a
        if keys[K_s] or keys[K_DOWN]: dx, dy = -self.speed * cos_a, -self.speed * sin_a
        if keys[K_a] or keys[K_LEFT]: dx, dy = self.speed * sin_a, -self.speed * cos_a
        if keys[K_d] or keys[K_RIGHT]: dx, dy = -self.speed * sin_a, self.speed * cos_a
        
        margin = 15
        new_rect_x = pygame.Rect(self.x + dx - 10, self.y - 10, self.hit_box_size, self.hit_box_size)
        new_rect_y = pygame.Rect(self.x - 10, self.y + dy - 10, self.hit_box_size, self.hit_box_size)
        
        can_move_x = world_map[int(self.y // TILE_SIZE)][int((self.x + dx + (margin if dx>0 else -margin)) // TILE_SIZE)] == 0
        can_move_y = world_map[int((self.y + dy + (margin if dy>0 else -margin)) // TILE_SIZE)][int(self.x // TILE_SIZE)] == 0
        
        for lock in lockers_list:
            if new_rect_x.colliderect(lock.rect): can_move_x = False
            if new_rect_y.colliderect(lock.rect): can_move_y = False

        if can_move_x: self.x += dx
        if can_move_y: self.y += dy

    def interact(self):
        if self.is_hiding:
            self.x, self.y = self.exit_pos
            self.is_hiding = False
            self.current_locker = None
            return
        for lock in lockers_list:
            dist = math.hypot(self.x - (lock.x + lock.width/2), self.y - (lock.y + lock.depth/2))
            if dist < 65:
                self.exit_pos = (self.x, self.y)
                self.is_hiding = True
                self.current_locker = lock
                self.x, self.y = lock.x + lock.width/2, lock.y + lock.depth/2
                break

class Enemy:
    def __init__(self, x, y):
        self.start_x, self.start_y = x, y
        self.reset()
    def reset(self):
        self.x, self.y = self.start_x, self.start_y
        self.speed_wander, self.speed_chase = 0.5, 1.3
        self.detection_range = 600
        self.is_chasing = False
        self.wander_angle = random.uniform(0, math.pi * 2)
    def update(self, player):
        dx, dy = player.x - self.x, player.y - self.y
        dist = math.hypot(dx, dy)
        can_see = False
        if not player.is_hiding and flashlight_on and dist < self.detection_range:
            angle_to_player = math.atan2(dy, dx)
            can_see = True
            for d in range(0, int(dist), 25):
                tx, ty = int(self.x + d * math.cos(angle_to_player)) // TILE_SIZE, int(self.y + d * math.sin(angle_to_player)) // TILE_SIZE
                if world_map[ty][tx] == 1: 
                    can_see = False
                    break
        if can_see:
            self.is_chasing = True
            angle = math.atan2(dy, dx)
            ex, ey = self.speed_chase * math.cos(angle), self.speed_chase * math.sin(angle)
        else:
            self.is_chasing = False
            ex, ey = self.speed_wander * math.cos(self.wander_angle), self.speed_wander * math.sin(self.wander_angle)
        
        margin = 15
        if world_map[int(self.y // TILE_SIZE)][int((self.x + ex + (margin if ex>0 else -margin)) // TILE_SIZE)] == 0:
            self.x += ex
        if world_map[int((self.y + ey + (margin if ey>0 else -margin)) // TILE_SIZE)][int(self.x // TILE_SIZE)] == 0:
            self.y += ey
        else: self.wander_angle = random.uniform(0, math.pi * 2)

world_map = [
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,2,1],
    [1,0,1,1,0,2,1,1,0,0,1,1,0,0,0,1],
    [1,0,1,0,0,0,1,0,0,0,1,0,0,0,0,1],
    [1,2,0,0,1,0,0,0,1,0,0,0,1,1,0,1],
    [1,0,0,0,1,0,1,0,1,0,1,0,0,2,0,1],
    [1,0,1,0,0,0,1,0,2,0,1,0,0,1,0,1],
    [1,0,1,1,0,0,1,1,0,0,1,1,0,1,0,1],
    [1,0,2,0,0,1,0,0,0,1,0,2,0,0,0,1],
    [1,0,1,0,0,0,1,0,0,0,1,0,1,0,0,1],
    [1,0,1,0,1,0,0,0,1,0,0,0,1,0,0,1],
    [1,0,0,0,1,1,1,0,1,1,1,0,1,0,2,1],
    [1,1,1,0,2,0,0,0,0,0,0,0,1,1,0,1],
    [1,0,0,0,1,0,1,1,1,0,1,0,0,0,0,1],
    [1,2,0,0,0,0,0,0,0,0,2,0,0,0,0,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]
]

lockers_list = []
locker_lookup = {}
for row_idx, row in enumerate(world_map):
    for col_idx, tile in enumerate(row):
        if tile == 2:
            l = Locker(col_idx, row_idx, world_map)
            lockers_list.append(l)
            locker_lookup[(col_idx, row_idx)] = l
            world_map[row_idx][col_idx] = 0 

flags = DOUBLEBUF | HWSURFACE
screen = pygame.display.set_mode((INTERNAL_WIDTH, INTERNAL_HEIGHT), flags)
game_surface = pygame.Surface((INTERNAL_WIDTH, INTERNAL_HEIGHT))

player = Player(150, 150)
enemies = [Enemy(500, 300), Enemy(800, 700), Enemy(1200, 500)]
clock = pygame.time.Clock()
font_sm = pygame.font.Font(None, 36)
font_lg = pygame.font.Font(None, 74)

def cast_ray(px, py, pa, ra):
    cos_a, sin_a = math.cos(ra), math.sin(ra)
    x_map, y_map = int(px // TILE_SIZE), int(py // TILE_SIZE)
    delta_dist_x, delta_dist_y = abs(1 / (cos_a + 1e-10)), abs(1 / (sin_a + 1e-10))
    
    if cos_a < 0: step_x, side_dist_x = -1, (px / TILE_SIZE - x_map) * delta_dist_x
    else: step_x, side_dist_x = 1, (x_map + 1.0 - px / TILE_SIZE) * delta_dist_x
    if sin_a < 0: step_y, side_dist_y = -1, (py / TILE_SIZE - y_map) * delta_dist_y
    else: step_y, side_dist_y = 1, (y_map + 1.0 - py / TILE_SIZE) * delta_dist_y
        
    wall_hit, dist_travelled = False, 0
    while not wall_hit and dist_travelled < MAX_DEPTH:
        if (x_map, y_map) in locker_lookup:
            lock = locker_lookup[(x_map, y_map)]
            if not (player.is_hiding and player.current_locker == lock):
                for i in range(0, TILE_SIZE, 5): 
                    rx, ry = px + cos_a * (dist_travelled + i), py + sin_a * (dist_travelled + i)
                    if lock.rect.collidepoint(rx, ry):
                        d = (dist_travelled + i)
                        return d * math.cos(ra - pa), (x_map, y_map), 0, d, 2
        if side_dist_x < side_dist_y:
            dist_travelled, side_dist_x, x_map, side = side_dist_x * TILE_SIZE, side_dist_x + delta_dist_x, x_map + step_x, 0
        else:
            dist_travelled, side_dist_y, y_map, side = side_dist_y * TILE_SIZE, side_dist_y + delta_dist_y, y_map + step_y, 1
        if 0 <= x_map < MAP_SIZE and 0 <= y_map < MAP_SIZE:
            if world_map[y_map][x_map] == 1: wall_hit = True
        else: break
            
    wall_dist = (side_dist_x - delta_dist_x) if side == 0 else (side_dist_y - delta_dist_y)
    return wall_dist * TILE_SIZE * math.cos(ra - pa), (x_map, y_map), side, wall_dist * TILE_SIZE, 1

def draw_sprites(surface):
    enemies.sort(key=lambda e: math.hypot(player.x - e.x, player.y - e.y), reverse=True)
    for e in enemies:
        dx, dy = e.x - player.x, e.y - player.y
        dist = math.hypot(dx, dy)
        if dist > 800 or dist < 10: continue
        theta = math.atan2(dy, dx) - player.angle
        while theta > math.pi: theta -= 2*math.pi
        while theta < -math.pi: theta += 2*math.pi
        if abs(theta) < HALF_FOV + 0.5: 
            size = 15000 / (dist * math.cos(theta) + 0.0001)
            middle_x = INTERNAL_WIDTH/2 + theta * INTERNAL_WIDTH / RAD_FOV
            start_x, color = int(middle_x - (size/4)), RED if e.is_chasing else PURPLE
            lf = max(0.03, 1 - (dist/350)**2) if flashlight_on else 0.03
            final_col = tuple(int(c * lf) for c in color)
            for stripe in range(start_x, int(start_x + int(size/2))):
                ray_idx = int(stripe / SCALE)
                if 0 <= ray_idx < NUM_RAYS and dist < z_buffer[ray_idx]:
                    h_mod = (1.0 - abs((stripe - start_x) / (size/2) - 0.5) * 2) * size
                    pygame.draw.line(surface, final_col, (stripe, INTERNAL_HEIGHT/2 - h_mod/2), (stripe, INTERNAL_HEIGHT/2 + h_mod/2))

def main():
    global flashlight_on, flashlight_battery, is_fullscreen, screen, mouse_sensitivity, z_buffer
    state, game_started, running, dragging_slider = "MENU", False, True, False
    while running:
        clock.tick(60)
        keys = pygame.key.get_pressed()
        win_w, win_h = screen.get_size()
        scale_factor = min(win_w/960, win_h/540)
        off_x, off_y = (win_w - int(960*scale_factor))//2, (win_h - int(540*scale_factor))//2
        mx, my = pygame.mouse.get_pos()
        imx, imy = (mx - off_x)/scale_factor, (my - off_y)/scale_factor

        for event in pygame.event.get():
            if event.type == QUIT: running = False
            if event.type == MOUSEBUTTONDOWN:
                if state == "MENU":
                    if 380 < imx < 580:
                        if 260 < imy < 300: state = "GAME"; game_started = True; pygame.mouse.set_visible(False); pygame.event.set_grab(True)
                        elif 310 < imy < 350: state = "OPTIONS"
                        elif 360 < imy < 400: running = False
                elif state == "OPTIONS" and 380 < imx < 580 and 260 < imy < 280: dragging_slider = True
                elif state == "DEAD" and 380 < imx < 580:
                    if 280 < imy < 320: player.reset(150, 150); [e.reset() for e in enemies]; flashlight_battery, flashlight_on, state = 1000, True, "GAME"; pygame.mouse.set_visible(False); pygame.event.set_grab(True)
                    elif 330 < imy < 370: game_started, state = False, "MENU"
            if event.type == MOUSEBUTTONUP: dragging_slider = False
            if event.type == KEYDOWN:
                if event.key == K_ESCAPE and state == "GAME": state = "MENU"; pygame.mouse.set_visible(True); pygame.event.set_grab(False)
                if state == "GAME":
                    if event.key == K_f: flashlight_on = not flashlight_on # Changed Flashlight to F
                    if event.key == K_e: player.interact()
                if event.key == K_BACKQUOTE: # Changed Fullscreen to ~
                    is_fullscreen = not is_fullscreen
                    screen = pygame.display.set_mode((0,0), flags|FULLSCREEN) if is_fullscreen else pygame.display.set_mode((960, 540), flags)

        if state == "OPTIONS" and dragging_slider: mouse_sensitivity = 0.0005 + max(0, min(1, (imx-380)/200)) * 0.0095

        game_surface.fill(BLACK)
        if state == "GAME":
            rel_x, _ = pygame.mouse.get_rel()
            if pygame.event.get_grab(): player.angle += rel_x * mouse_sensitivity
            player.move(keys)
            for e in enemies: e.update(player)
            if flashlight_on:
                flashlight_battery -= 0.15
                if flashlight_battery <= 0: flashlight_battery, flashlight_on = 0, False
            
            pygame.draw.rect(game_surface, (5, 5, 10), (0, 0, 960, 270))
            pygame.draw.rect(game_surface, (2, 2, 5), (0, 270, 960, 270))
            
            start_angle = player.angle - HALF_FOV
            for r in range(NUM_RAYS):
                ra = start_angle + r * RAD_FOV / NUM_RAYS
                d, t, side, raw_dist, tile_type = cast_ray(player.x, player.y, player.angle, ra)
                z_buffer[r] = raw_dist 
                h, intensity = 21000 / (d + 0.0001), 255 / (1 + d*d*0.00003)
                base_col = (LOCKER_COL[0]*intensity/255, LOCKER_COL[1]*intensity/255, LOCKER_COL[2]*intensity/255) if tile_type == 2 else (intensity*0.4*(1 if side==0 else 0.7), intensity*0.2*(1 if side==0 else 0.7), intensity*0.2*(1 if side==0 else 0.7))
                lf = max(0.05, 1 - (d/380)**2) if flashlight_on else 0.05
                pygame.draw.rect(game_surface, tuple(int(c * lf) for c in base_col), (int(r * SCALE), 270 - h/2, math.ceil(SCALE)+1, h))
            
            draw_sprites(game_surface)
            
            if player.is_hiding:
                vignette = pygame.Surface((960, 540), pygame.SRCALPHA)
                pygame.draw.rect(vignette, (0, 0, 0, 220), (0, 0, 960, 120))
                pygame.draw.rect(vignette, (0, 0, 0, 220), (0, 420, 960, 120))
                game_surface.blit(vignette, (0,0))
                prompt = font_sm.render("[E] EXIT", True, YELLOW)
                game_surface.blit(prompt, prompt.get_rect(center=(480, 480)))
            else:
                for lock in lockers_list:
                    if math.hypot(player.x - (lock.x + lock.width/2), player.y - (lock.y + lock.depth/2)) < 70:
                        prompt = font_sm.render("[E] HIDE", True, WHITE)
                        game_surface.blit(prompt, prompt.get_rect(center=(480, 310)))
                        break
            
            pygame.draw.circle(game_surface, YELLOW if flashlight_on else (30,30,30), (50,50), 20)
            pygame.draw.rect(game_surface, GREEN if flashlight_battery > 250 else RED, (30,80, max(0, int(flashlight_battery/10)), 10))
            if not player.is_hiding:
                for e in enemies:
                    if math.hypot(player.x - e.x, player.y - e.y) < 35:
                        state, game_started = "DEAD", False; pygame.mouse.set_visible(True); pygame.event.set_grab(False)
        
        elif state == "MENU":
            title = font_lg.render("VOID WALKER", True, RED)
            game_surface.blit(title, title.get_rect(center=(480, 150)))
            for i, text in enumerate(["CONTINUE" if game_started else "START GAME", "OPTIONS", "EXIT"]):
                y = 280 + (i * 50)
                txt = font_sm.render(text, True, WHITE if (380 < imx < 580 and y-20 < imy < y+20) else GRAY)
                game_surface.blit(txt, txt.get_rect(center=(480, y)))
        elif state == "DEAD":
            title = font_lg.render("YOU DIED", True, RED)
            game_surface.blit(title, title.get_rect(center=(480, 180)))
            for i, text in enumerate(["RESTART", "MAIN MENU"]):
                y = 300 + (i * 50)
                txt = font_sm.render(text, True, WHITE if (380 < imx < 580 and y-20 < imy < y+20) else GRAY)
                game_surface.blit(txt, txt.get_rect(center=(480, y)))

        screen.blit(pygame.transform.scale(game_surface, (int(960*scale_factor), int(540*scale_factor))), (off_x, off_y))
        pygame.display.flip()
    pygame.quit()

if __name__ == "__main__":
    main()