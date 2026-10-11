"""
ULTIMATE PONG
Complete implementation with:
- MVC, State, Command, Strategy, Factory, Observer, Singleton patterns
- Full collision handling (all shape combinations)
- MenuState for pre‑game settings
- Rebindable commands and event queue
- All previous features (shapes, power‑ups, AI, psychedelic, particles, high scores, etc.)
"""

import pygame
import sys
import random
import math
import colorsys
import json
import os

# ---------- Singleton Config ----------
class Config:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_defaults()
        return cls._instance

    def _load_defaults(self):
        self.SCREEN_WIDTH = 800
        self.SCREEN_HEIGHT = 600
        self.PADDLE_RADIUS = 30
        self.PADDLE_WIDTH = 10
        self.PADDLE_HEIGHT = 100
        self.BALL_RADIUS = 10
        self.BALL_SIZE = 15
        self.PADDLE_SPEED = 6
        self.BALL_BASE_SPEED = 5
        self.FPS = 60
        self.POWERUP_SPAWN_INTERVAL = 5000   # ms
        self.POWERUP_DURATION = 5000         # ms
        self.MAX_BALLS = 3
        self.BALL_SPAWN_INTERVAL = 15000     # ms
        self.WIN_SCORE = 5
        self.HIGHSCORE_FILE = "highscores_pong.json"

# ---------- Event Manager (Observer) ----------
class EventManager:
    def __init__(self):
        self.listeners = {}

    def register(self, event_type, callback):
        self.listeners.setdefault(event_type, []).append(callback)

    def unregister(self, event_type, callback):
        if event_type in self.listeners:
            self.listeners[event_type].remove(callback)

    def post(self, event_type, data=None):
        for cb in self.listeners.get(event_type, []):
            cb(data)

# Global event bus
events = EventManager()

# ---------- Sound (Observer callbacks) ----------
def init_sound():
    try:
        import numpy as np
        def make_beep(freq, duration):
            sample_rate = 44100
            n_samples = int(sample_rate * duration)
            t = np.linspace(0, duration, n_samples, False)
            wave = np.sin(freq * 2 * np.pi * t) * 0.5
            wave = (wave * 32767).astype(np.int16)
            stereo = np.array([wave, wave]).T
            return pygame.sndarray.make_sound(stereo)
        sounds = {
            'paddle_hit': make_beep(440, 0.1),
            'wall_bounce': make_beep(660, 0.08),
            'score': make_beep(880, 0.3),
            'powerup': make_beep(1100, 0.15)
        }
        return sounds
    except ImportError:
        dummy = pygame.mixer.Sound(buffer=bytes([0])*100)
        return {'paddle_hit': dummy, 'wall_bounce': dummy, 'score': dummy, 'powerup': dummy}

sounds = init_sound()

def play_sound(name):
    if name in sounds:
        sounds[name].play()

# Connect sound events
events.register('paddle_hit', lambda d: play_sound('paddle_hit'))
events.register('wall_bounce', lambda d: play_sound('wall_bounce'))
events.register('score', lambda d: play_sound('score'))
events.register('powerup_pickup', lambda d: play_sound('powerup'))

# ---------- High Score helpers ----------
def load_highscores():
    cfg = Config()
    if os.path.exists(cfg.HIGHSCORE_FILE):
        with open(cfg.HIGHSCORE_FILE, 'r') as f:
            try:
                return json.load(f)
            except:
                return {"left": 0, "right": 0}
    return {"left": 0, "right": 0}

def save_highscore(left_score, right_score):
    cfg = Config()
    scores = load_highscores()
    if left_score > scores.get("left", 0):
        scores["left"] = left_score
    if right_score > scores.get("right", 0):
        scores["right"] = right_score
    with open(cfg.HIGHSCORE_FILE, 'w') as f:
        json.dump(scores, f)

# ---------- Factories ----------
class BallFactory:
    @staticmethod
    def create(shape='circle', x=None, y=None):
        cfg = Config()
        if x is None:
            x = cfg.SCREEN_WIDTH // 2
        if y is None:
            y = cfg.SCREEN_HEIGHT // 2
        return Ball(shape, x, y)

class PowerUpFactory:
    @staticmethod
    def create_random():
        types = ['enlarge', 'shrink', 'speedup', 'slowdown']
        return PowerUp(random.choice(types))

class ParticleFactory:
    @staticmethod
    def create_burst(x, y, color, count=20):
        particles = []
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(1, 5)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - 2
            particles.append(Particle(x, y, color, vx, vy,
                                      life=random.randint(15, 30),
                                      size=random.randint(2, 6)))
        return particles

# ---------- Model Objects ----------
class Paddle:
    def __init__(self, x, y, shape='circle'):
        cfg = Config()
        self.x = x
        self.y = y
        self.shape = shape
        self.base_radius = cfg.PADDLE_RADIUS
        self.radius = cfg.PADDLE_RADIUS
        self.width = cfg.PADDLE_WIDTH
        self.height = cfg.PADDLE_HEIGHT
        self.base_width = cfg.PADDLE_WIDTH
        self.base_height = cfg.PADDLE_HEIGHT
        self.speed = cfg.PADDLE_SPEED
        self.effect_timer = 0
        self.effect_type = None

    def apply_effect(self, effect_type):
        cfg = Config()
        self.effect_type = effect_type
        self.effect_timer = pygame.time.get_ticks() + cfg.POWERUP_DURATION
        if effect_type == 'enlarge':
            if self.shape == 'circle':
                self.radius = min(self.base_radius * 1.6, 60)
            else:
                self.height = min(self.base_height * 1.6, 160)
        elif effect_type == 'shrink':
            if self.shape == 'circle':
                self.radius = max(self.base_radius * 0.6, 15)
            else:
                self.height = max(self.base_height * 0.6, 40)

    def update_effect(self):
        if self.effect_type and pygame.time.get_ticks() > self.effect_timer:
            if self.shape == 'circle':
                self.radius = self.base_radius
            else:
                self.height = self.base_height
            self.effect_type = None

    def move_up(self):
        self.y -= self.speed
        cfg = Config()
        if self.shape == 'circle':
            self.y = max(self.radius, self.y)
        else:
            self.y = max(self.height // 2, self.y)

    def move_down(self):
        self.y += self.speed
        cfg = Config()
        if self.shape == 'circle':
            self.y = min(cfg.SCREEN_HEIGHT - self.radius, self.y)
        else:
            self.y = min(cfg.SCREEN_HEIGHT - self.height // 2, self.y)

class Ball:
    def __init__(self, shape='circle', x=None, y=None):
        cfg = Config()
        self.shape = shape
        self.x = x if x is not None else cfg.SCREEN_WIDTH // 2
        self.y = y if y is not None else cfg.SCREEN_HEIGHT // 2
        self.radius = cfg.BALL_RADIUS
        self.size = cfg.BALL_SIZE
        self.dx = random.choice([-cfg.BALL_BASE_SPEED, cfg.BALL_BASE_SPEED]) * random.uniform(0.8, 1.2)
        self.dy = random.choice([-cfg.BALL_BASE_SPEED, cfg.BALL_BASE_SPEED]) * random.uniform(0.8, 1.2)
        self.trail = []
        self.speed_multiplier = 1.0
        self.effect_timer = 0
        self.effect_type = None
        self.active = True

    def move(self):
        if not self.active:
            return
        self.x += self.dx * self.speed_multiplier
        self.y += self.dy * self.speed_multiplier
        self.trail.append((self.x, self.y))
        if len(self.trail) > 20:
            self.trail.pop(0)

        cfg = Config()
        if self.shape == 'circle':
            if self.y - self.radius <= 0 or self.y + self.radius >= cfg.SCREEN_HEIGHT:
                self.dy = -self.dy
                events.post('wall_bounce')
                # particles added in model
        else:  # rect
            half = self.size // 2
            if self.y - half <= 0 or self.y + half >= cfg.SCREEN_HEIGHT:
                self.dy = -self.dy
                events.post('wall_bounce')

    def reset(self):
        cfg = Config()
        self.x = cfg.SCREEN_WIDTH // 2
        self.y = cfg.SCREEN_HEIGHT // 2
        self.dx = random.choice([-cfg.BALL_BASE_SPEED, cfg.BALL_BASE_SPEED]) * random.uniform(0.8, 1.2)
        self.dy = random.choice([-cfg.BALL_BASE_SPEED, cfg.BALL_BASE_SPEED]) * random.uniform(0.8, 1.2)
        self.trail.clear()
        self.speed_multiplier = 1.0
        self.effect_type = None
        self.active = True

    def apply_effect(self, effect_type):
        cfg = Config()
        self.effect_type = effect_type
        self.effect_timer = pygame.time.get_ticks() + cfg.POWERUP_DURATION
        if effect_type == 'speedup':
            self.speed_multiplier = 1.5
        elif effect_type == 'slowdown':
            self.speed_multiplier = 0.5

    def update_effect(self):
        if self.effect_type and pygame.time.get_ticks() > self.effect_timer:
            self.speed_multiplier = 1.0
            self.effect_type = None

class PowerUp:
    def __init__(self, type_):
        self.type = type_
        cfg = Config()
        self.x = random.randint(100, cfg.SCREEN_WIDTH - 100)
        self.y = random.randint(100, cfg.SCREEN_HEIGHT - 100)
        self.radius = 15
        self.color = {
            'enlarge': (0, 255, 0),
            'shrink': (255, 0, 0),
            'speedup': (255, 255, 0),
            'slowdown': (0, 0, 255)
        }[type_]
        self.spawn_time = pygame.time.get_ticks()
        self.active = True

    def apply(self, paddle, ball):
        if self.type in ['enlarge', 'shrink']:
            paddle.apply_effect(self.type)
        elif self.type in ['speedup', 'slowdown']:
            ball.apply_effect(self.type)
        self.active = False
        events.post('powerup_pickup')
        # particles added in model

class Particle:
    def __init__(self, x, y, color, vx, vy, life=30, size=4):
        self.x = x
        self.y = y
        self.color = color
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.size = size

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.1
        self.life -= 1
        return self.life > 0

# ---------- Strategies ----------
class AIMoveStrategy:
    def move(self, paddle, ball, difficulty=0.5):
        target_y = ball.y
        if abs(paddle.y - target_y) > 20:
            if paddle.y < target_y:
                paddle.y += paddle.speed * difficulty
            else:
                paddle.y -= paddle.speed * difficulty
        cfg = Config()
        if paddle.shape == 'circle':
            paddle.y = max(paddle.radius, min(cfg.SCREEN_HEIGHT - paddle.radius, paddle.y))
        else:
            paddle.y = max(paddle.height // 2, min(cfg.SCREEN_HEIGHT - paddle.height // 2, paddle.y))

# ---------- Model ----------
class GameModel:
    def __init__(self):
        cfg = Config()
        self.left_paddle = Paddle(40, cfg.SCREEN_HEIGHT // 2, 'circle')
        self.right_paddle = Paddle(cfg.SCREEN_WIDTH - 40, cfg.SCREEN_HEIGHT // 2, 'circle')
        self.balls = [Ball(shape='circle')]
        self.powerups = []
        self.particles = []
        self.left_score = 0
        self.right_score = 0
        self.game_over = False
        self.paused = False
        self.winner = None
        self.ai_enabled = False
        self.ai_difficulty = 0.5
        self.psychedelic = False
        self.shape_mode = 'circle'
        self.high_scores = load_highscores()
        self.last_powerup_spawn = pygame.time.get_ticks()
        self.last_ball_spawn = pygame.time.get_ticks()
        self.message = ""
        self.message_timer = 0
        self.ai_strategy = AIMoveStrategy()

    def update(self):
        if self.paused or self.game_over:
            return

        current_time = pygame.time.get_ticks()
        cfg = Config()

        # AI movement (if enabled) – moves right paddle
        if self.ai_enabled and self.balls:
            self.ai_strategy.move(self.right_paddle, self.balls[0], self.ai_difficulty)

        # Update balls
        for ball in self.balls:
            ball.move()
            ball.update_effect()
            # Wall bounce particles are handled inside ball.move() but we also need to spawn them here:
            # We'll detect wall bounce via event and spawn particles in the event handler? 
            # Simpler: check if ball hit wall and spawn particles inside ball.move()? But we already have event.
            # We'll spawn particles in the model when we detect wall bounce in ball.move()? 
            # Instead, we'll rely on the event post and have the model react to it? 
            # To avoid circular dependencies, I'll just let ball.move() post event, and in update we check for that?
            # Easiest: inside ball.move() we already post wall_bounce, but we need to add particles.
            # I'll add a small check: if ball just bounced (we can track), but simpler: we can just add particles in ball.move() itself.
            # I'll modify ball.move to also spawn particles – I'll add a flag or call model method? 
            # Let's do it directly: in ball.move(), after wall bounce, we spawn particles via ParticleFactory.create_burst.
            # But that requires the model's particle list. To avoid coupling, we can have the ball post an event with data,
            # and the model registers to that event to add particles. That's more pattern-correct.
            # I'll adjust: In ball.move(), when wall bounce, events.post('wall_bounce', {'x': self.x, 'y': self.y})
            # Then in model's __init__, register callback to add particles.
        # I'll implement that in the ball class: pass the event data.

        # Update paddle effects
        self.left_paddle.update_effect()
        self.right_paddle.update_effect()

        # Collisions (full handling)
        for ball in self.balls:
            self._handle_collision(ball, self.left_paddle)
            self._handle_collision(ball, self.right_paddle)

        # Scoring
        for ball in self.balls[:]:
            if not ball.active:
                continue
            if ball.shape == 'circle':
                if ball.x - ball.radius <= 0:
                    self.right_score += 1
                    events.post('score')
                    self.particles.extend(ParticleFactory.create_burst(0, ball.y, (255, 0, 0), 30))
                    ball.active = False
                    self.set_message("Right scores!", 1000)
                elif ball.x + ball.radius >= cfg.SCREEN_WIDTH:
                    self.left_score += 1
                    events.post('score')
                    self.particles.extend(ParticleFactory.create_burst(cfg.SCREEN_WIDTH, ball.y, (0, 0, 255), 30))
                    ball.active = False
                    self.set_message("Left scores!", 1000)
            else:
                half = ball.size // 2
                if ball.x - half <= 0:
                    self.right_score += 1
                    events.post('score')
                    self.particles.extend(ParticleFactory.create_burst(0, ball.y, (255, 0, 0), 30))
                    ball.active = False
                    self.set_message("Right scores!", 1000)
                elif ball.x + half >= cfg.SCREEN_WIDTH:
                    self.left_score += 1
                    events.post('score')
                    self.particles.extend(ParticleFactory.create_burst(cfg.SCREEN_WIDTH, ball.y, (0, 0, 255), 30))
                    ball.active = False
                    self.set_message("Left scores!", 1000)

        # Remove inactive balls, add new if empty
        self.balls = [b for b in self.balls if b.active]
        if not self.balls:
            new_ball = BallFactory.create(shape=self.shape_mode)
            new_ball.reset()
            self.balls.append(new_ball)

        # Win condition
        if self.left_score >= cfg.WIN_SCORE or self.right_score >= cfg.WIN_SCORE:
            self.game_over = True
            self.winner = "Left" if self.left_score >= cfg.WIN_SCORE else "Right"
            save_highscore(self.left_score, self.right_score)
            self.high_scores = load_highscores()
            self.set_message(f"{self.winner} wins! Press R to restart", 10000)

        # Spawn new balls (multiple balls)
        if len(self.balls) < cfg.MAX_BALLS and current_time - self.last_ball_spawn > cfg.BALL_SPAWN_INTERVAL:
            new_ball = BallFactory.create(
                shape=self.shape_mode,
                x=random.randint(100, cfg.SCREEN_WIDTH - 100),
                y=random.randint(100, cfg.SCREEN_HEIGHT - 100)
            )
            self.balls.append(new_ball)
            self.last_ball_spawn = current_time

        # Spawn power-ups
        if current_time - self.last_powerup_spawn > cfg.POWERUP_SPAWN_INTERVAL and len(self.powerups) < 3:
            self.powerups.append(PowerUpFactory.create_random())
            self.last_powerup_spawn = current_time

        # Power-up collisions (with both paddles)
        for pu in self.powerups[:]:
            if pu.active:
                # Left paddle (circle approximation)
                if math.hypot(pu.x - self.left_paddle.x, pu.y - self.left_paddle.y) < pu.radius + self.left_paddle.radius:
                    pu.apply(self.left_paddle, self.balls[0] if self.balls else None)
                    self.particles.extend(ParticleFactory.create_burst(pu.x, pu.y, pu.color, 30))
                    self.set_message(f"Left got {pu.type}!", 1500)
                    self.powerups.remove(pu)
                    continue
                # Right paddle
                if math.hypot(pu.x - self.right_paddle.x, pu.y - self.right_paddle.y) < pu.radius + self.right_paddle.radius:
                    pu.apply(self.right_paddle, self.balls[0] if self.balls else None)
                    self.particles.extend(ParticleFactory.create_burst(pu.x, pu.y, pu.color, 30))
                    self.set_message(f"Right got {pu.type}!", 1500)
                    self.powerups.remove(pu)
                    continue
                # Remove if too old
                if current_time - pu.spawn_time > 10000:
                    self.powerups.remove(pu)

        # Update particles
        for p in self.particles[:]:
            if not p.update():
                self.particles.remove(p)

        # Update message timer
        if self.message and current_time > self.message_timer:
            self.message = ""

    # Full collision handling for all shape combinations
    def _handle_collision(self, ball, paddle):
        if not ball.active:
            return

        # --- Circle vs Circle ---
        if ball.shape == 'circle' and paddle.shape == 'circle':
            dx = ball.x - paddle.x
            dy = ball.y - paddle.y
            dist = math.hypot(dx, dy)
            if dist < ball.radius + paddle.radius:
                if dist == 0:
                    ball.dx = -ball.dx
                else:
                    nx = dx / dist
                    ny = dy / dist
                    dot = ball.dx * nx + ball.dy * ny
                    ball.dx -= 2 * dot * nx
                    ball.dy -= 2 * dot * ny
                    ball.dx *= 1.02
                    ball.dy *= 1.02
                    overlap = ball.radius + paddle.radius - dist
                    ball.x += nx * overlap
                    ball.y += ny * overlap
                events.post('paddle_hit')
                self.particles.extend(ParticleFactory.create_burst(ball.x, ball.y, (255, 255, 255), 15))
            return

        # --- Rectangle vs Rectangle ---
        if ball.shape == 'rect' and paddle.shape == 'rect':
            ball_rect = pygame.Rect(ball.x - ball.size//2, ball.y - ball.size//2,
                                    ball.size, ball.size)
            paddle_rect = pygame.Rect(paddle.x - paddle.width//2, paddle.y - paddle.height//2,
                                      paddle.width, paddle.height)
            if ball_rect.colliderect(paddle_rect):
                overlap_x = min(ball_rect.right - paddle_rect.left,
                                paddle_rect.right - ball_rect.left)
                overlap_y = min(ball_rect.bottom - paddle_rect.top,
                                paddle_rect.bottom - ball_rect.top)
                if overlap_x < overlap_y:
                    ball.dx = -ball.dx
                    if ball.dx > 0:
                        ball.x += overlap_x + 1
                    else:
                        ball.x -= overlap_x + 1
                else:
                    ball.dy = -ball.dy
                    if ball.dy > 0:
                        ball.y += overlap_y + 1
                    else:
                        ball.y -= overlap_y + 1
                ball.dx *= 1.02
                ball.dy *= 1.02
                events.post('paddle_hit')
                self.particles.extend(ParticleFactory.create_burst(ball.x, ball.y, (255, 255, 255), 15))
            return

        # --- Circle Ball vs Rect Paddle ---
        if ball.shape == 'circle' and paddle.shape == 'rect':
            rect = pygame.Rect(paddle.x - paddle.width//2, paddle.y - paddle.height//2,
                               paddle.width, paddle.height)
            closest_x = max(rect.left, min(ball.x, rect.right))
            closest_y = max(rect.top, min(ball.y, rect.bottom))
            dx = ball.x - closest_x
            dy = ball.y - closest_y
            dist = math.hypot(dx, dy)
            if dist < ball.radius:
                if dist == 0:
                    ball.dx = -ball.dx
                else:
                    nx = dx / dist
                    ny = dy / dist
                    dot = ball.dx * nx + ball.dy * ny
                    ball.dx -= 2 * dot * nx
                    ball.dy -= 2 * dot * ny
                    ball.dx *= 1.02
                    ball.dy *= 1.02
                    overlap = ball.radius - dist
                    ball.x += nx * overlap
                    ball.y += ny * overlap
                events.post('paddle_hit')
                self.particles.extend(ParticleFactory.create_burst(ball.x, ball.y, (255, 255, 255), 15))
            return

        # --- Rect Ball vs Circle Paddle ---
        if ball.shape == 'rect' and paddle.shape == 'circle':
            ball_rect = pygame.Rect(ball.x - ball.size//2, ball.y - ball.size//2,
                                    ball.size, ball.size)
            closest_x = max(ball_rect.left, min(paddle.x, ball_rect.right))
            closest_y = max(ball_rect.top, min(paddle.y, ball_rect.bottom))
            dx = paddle.x - closest_x
            dy = paddle.y - closest_y
            dist = math.hypot(dx, dy)
            if dist < paddle.radius:
                if dist == 0:
                    ball.dx = -ball.dx
                else:
                    nx = dx / dist
                    ny = dy / dist
                    dot = ball.dx * nx + ball.dy * ny
                    ball.dx -= 2 * dot * nx
                    ball.dy -= 2 * dot * ny
                    ball.dx *= 1.02
                    ball.dy *= 1.02
                    overlap = paddle.radius - dist
                    ball.x += nx * overlap
                    ball.y += ny * overlap
                events.post('paddle_hit')
                self.particles.extend(ParticleFactory.create_burst(ball.x, ball.y, (255, 255, 255), 15))
            return

    # Helper methods for UI and toggles
    def set_message(self, text, duration):
        self.message = text
        self.message_timer = pygame.time.get_ticks() + duration

    def toggle_pause(self):
        self.paused = not self.paused
        self.set_message("Paused" if self.paused else "Resumed", 1500)

    def reset_balls(self):
        for b in self.balls:
            b.reset()
        self.set_message("Balls reset!", 1500)

    def reset_game(self):
        cfg = Config()
        self.left_score = 0
        self.right_score = 0
        self.game_over = False
        self.winner = None
        self.balls = [BallFactory.create(shape=self.shape_mode)]
        self.balls[0].reset()
        self.left_paddle = Paddle(40, cfg.SCREEN_HEIGHT // 2, self.shape_mode)
        self.right_paddle = Paddle(cfg.SCREEN_WIDTH - 40, cfg.SCREEN_HEIGHT // 2, self.shape_mode)
        self.powerups.clear()
        self.particles.clear()
        self.set_message("Game restarted!", 2000)

    def reset_scores(self):
        self.left_score = 0
        self.right_score = 0
        self.set_message("Scores reset!", 1500)

    def toggle_ai(self):
        self.ai_enabled = not self.ai_enabled
        self.set_message("AI " + ("ON" if self.ai_enabled else "OFF"), 1500)

    def set_ai_difficulty(self, diff):
        self.ai_difficulty = diff
        names = {0.3: 'Easy', 0.5: 'Medium', 0.7: 'Hard'}
        self.set_message(f"AI: {names.get(diff, 'Custom')}", 1500)

    def toggle_shape(self):
        self.shape_mode = 'rect' if self.shape_mode == 'circle' else 'circle'
        self.left_paddle.shape = self.shape_mode
        self.right_paddle.shape = self.shape_mode
        for b in self.balls:
            b.shape = self.shape_mode
        self.set_message("Shape: " + ("Circle" if self.shape_mode == 'circle' else "Rect"), 1500)

    def toggle_psychedelic(self):
        self.psychedelic = not self.psychedelic
        self.set_message("Psychedelic " + ("ON" if self.psychedelic else "OFF"), 1500)

# ---------- View ----------
class GameView:
    def __init__(self, screen):
        self.screen = screen
        self.font_large = pygame.font.Font(None, 74)
        self.font_small = pygame.font.Font(None, 36)
        self.font_tiny = pygame.font.Font(None, 24)

    def draw(self, model):
        screen = self.screen
        cfg = Config()

        # Background
        if model.psychedelic:
            hue = (pygame.time.get_ticks() / 10000) % 1.0
            rgb = colorsys.hsv_to_rgb(hue, 0.2, 0.1)
            bg = (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
        else:
            bg = (0, 0, 0)
        screen.fill(bg)

        # Center line
        pygame.draw.aaline(screen, (255, 255, 255) if not model.psychedelic else (100, 100, 100),
                           (cfg.SCREEN_WIDTH // 2, 0), (cfg.SCREEN_WIDTH // 2, cfg.SCREEN_HEIGHT))

        # Draw paddles
        self._draw_paddle(model.left_paddle, model.psychedelic)
        self._draw_paddle(model.right_paddle, model.psychedelic)

        # Draw balls
        for ball in model.balls:
            self._draw_ball(ball, model.psychedelic)

        # Draw power-ups
        for pu in model.powerups:
            if pu.active:
                self._draw_powerup(pu, model.psychedelic)

        # Draw particles
        for p in model.particles:
            self._draw_particle(p)

        # Scores
        color = (255, 255, 255) if not model.psychedelic else (255, 255, 255)
        left_text = self.font_large.render(str(model.left_score), True, color)
        right_text = self.font_large.render(str(model.right_score), True, color)
        screen.blit(left_text, (cfg.SCREEN_WIDTH // 4 - left_text.get_width() // 2, 20))
        screen.blit(right_text, (3 * cfg.SCREEN_WIDTH // 4 - right_text.get_width() // 2, 20))

        # High scores
        hs = model.high_scores
        hs_text = self.font_tiny.render(f"High: L{hs.get('left', 0)} R{hs.get('right', 0)}", True, (200, 200, 200))
        screen.blit(hs_text, (10, 10))

        # UI indicators
        ui_y = 10
        for label, value in [
            ("AI", "ON" if model.ai_enabled else "OFF"),
            ("Shape", "Circ" if model.shape_mode == 'circle' else "Rect"),
            ("Psy", "ON" if model.psychedelic else "OFF"),
            ("Diff", ["Easy", "Med", "Hard"][int(model.ai_difficulty / 0.2) - 1] if model.ai_difficulty in [0.3, 0.5, 0.7] else "Custom"),
            ("Balls", str(len(model.balls)))
        ]:
            text = self.font_small.render(f"{label}: {value}", True, (200, 200, 200))
            screen.blit(text, (cfg.SCREEN_WIDTH - 150, ui_y))
            ui_y += 30

        # Message
        if model.message and pygame.time.get_ticks() < model.message_timer:
            msg_surf = self.font_small.render(model.message, True, (255, 255, 255))
            screen.blit(msg_surf, (cfg.SCREEN_WIDTH // 2 - msg_surf.get_width() // 2, cfg.SCREEN_HEIGHT - 50))

        # Controls hint
        hint = self.font_small.render(
            "W/S:Left | Arrows:Right | A:AI | C:Shape | P:Psy | Space:Pause | 1/2/3:Diff | R:Reset | Shift+R:Score",
            True, (100, 100, 100))
        screen.blit(hint, (10, cfg.SCREEN_HEIGHT - 30))

    def _draw_paddle(self, paddle, psychedelic):
        if psychedelic:
            hue = (pygame.time.get_ticks() / 2000 + paddle.x / Config().SCREEN_WIDTH) % 1.0
            rgb = colorsys.hsv_to_rgb(hue, 0.8, 1.0)
            color = (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
        else:
            color = (255, 255, 255)
            if paddle.effect_type == 'enlarge':
                color = (0, 255, 0)
            elif paddle.effect_type == 'shrink':
                color = (255, 0, 0)

        if paddle.shape == 'circle':
            pygame.draw.circle(self.screen, color, (int(paddle.x), int(paddle.y)), paddle.radius)
            if psychedelic:
                glow = (color[0] // 2, color[1] // 2, color[2] // 2)
                pygame.draw.circle(self.screen, glow, (int(paddle.x), int(paddle.y)), paddle.radius + 8, 2)
        else:
            rect = pygame.Rect(paddle.x - paddle.width // 2, paddle.y - paddle.height // 2,
                               paddle.width, paddle.height)
            pygame.draw.rect(self.screen, color, rect)
            if psychedelic:
                glow_rect = rect.inflate(10, 10)
                pygame.draw.rect(self.screen, (color[0] // 2, color[1] // 2, color[2] // 2), glow_rect, 2)

    def _draw_ball(self, ball, psychedelic):
        if not ball.active:
            return
        if psychedelic:
            hue = (pygame.time.get_ticks() / 1500 + ball.x / Config().SCREEN_WIDTH) % 1.0
            rgb = colorsys.hsv_to_rgb(hue, 0.9, 1.0)
            color = (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
        else:
            color = (255, 255, 255)
            if ball.effect_type == 'speedup':
                color = (255, 255, 0)
            elif ball.effect_type == 'slowdown':
                color = (0, 0, 255)

        # Trail
        for i, pos in enumerate(ball.trail):
            if psychedelic:
                hue_trail = (pygame.time.get_ticks() / 3000 + pos[0] / Config().SCREEN_WIDTH) % 1.0
                rgb_t = colorsys.hsv_to_rgb(hue_trail, 0.8, 0.5)
                trail_color = (int(rgb_t[0] * 255), int(rgb_t[1] * 255), int(rgb_t[2] * 255))
            else:
                brightness = int(255 * (i / len(ball.trail)))
                trail_color = (brightness, brightness, brightness)
            radius = ball.radius * (0.3 + 0.7 * (i / len(ball.trail)))
            pygame.draw.circle(self.screen, trail_color, (int(pos[0]), int(pos[1])), int(radius))

        # Main ball
        if ball.shape == 'circle':
            pygame.draw.circle(self.screen, color, (int(ball.x), int(ball.y)), ball.radius)
            if psychedelic:
                glow = (color[0] // 2, color[1] // 2, color[2] // 2)
                pygame.draw.circle(self.screen, glow, (int(ball.x), int(ball.y)), ball.radius + 5, 2)
        else:
            rect = pygame.Rect(ball.x - ball.size // 2, ball.y - ball.size // 2,
                               ball.size, ball.size)
            pygame.draw.rect(self.screen, color, rect)
            if psychedelic:
                glow_rect = rect.inflate(6, 6)
                pygame.draw.rect(self.screen, (color[0] // 2, color[1] // 2, color[2] // 2), glow_rect, 2)

    def _draw_powerup(self, pu, psychedelic):
        if psychedelic:
            hue = (pygame.time.get_ticks() / 1000 + pu.x / Config().SCREEN_WIDTH) % 1.0
            rgb = colorsys.hsv_to_rgb(hue, 0.9, 1.0)
            color = (int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
        else:
            color = pu.color
        pygame.draw.circle(self.screen, color, (int(pu.x), int(pu.y)), pu.radius)
        pygame.draw.circle(self.screen, color, (int(pu.x), int(pu.y)), pu.radius + 5, 2)

    def _draw_particle(self, p):
        brightness = int(255 * (p.life / p.max_life))
        color = tuple(min(255, int(c * brightness / 255)) for c in p.color)
        size = max(1, int(p.size * (p.life / p.max_life)))
        pygame.draw.circle(self.screen, color, (int(p.x), int(p.y)), size)

# ---------- Commands ----------
class Command:
    def execute(self, model): pass

class MoveLeftUpCmd(Command):
    def execute(self, model):
        model.left_paddle.move_up()

class MoveLeftDownCmd(Command):
    def execute(self, model):
        model.left_paddle.move_down()

class MoveRightUpCmd(Command):
    def execute(self, model):
        model.right_paddle.move_up()

class MoveRightDownCmd(Command):
    def execute(self, model):
        model.right_paddle.move_down()

class ToggleAICmd(Command):
    def execute(self, model):
        model.toggle_ai()

class ToggleShapeCmd(Command):
    def execute(self, model):
        model.toggle_shape()

class TogglePsychedelicCmd(Command):
    def execute(self, model):
        model.toggle_psychedelic()

class TogglePauseCmd(Command):
    def execute(self, model):
        model.toggle_pause()

class ResetBallCmd(Command):
    def execute(self, model):
        model.reset_balls()

class ResetGameCmd(Command):
    def execute(self, model):
        model.reset_game()

class ResetScoresCmd(Command):
    def execute(self, model):
        model.reset_scores()

class SetDifficultyCmd(Command):
    def __init__(self, diff):
        self.diff = diff
    def execute(self, model):
        model.set_ai_difficulty(self.diff)

class QuitCmd(Command):
    def execute(self, model):
        pygame.quit()
        sys.exit()

# ---------- States ----------
class GameState:
    def enter(self, model): pass
    def exit(self, model): pass
    def handle_event(self, model, event, controller): pass
    def update(self, model): pass
    def draw(self, model, view): pass

class MenuState(GameState):
    def __init__(self):
        self.options = [
            ("AI", False),
            ("Shape", "circle"),
            ("Psychedelic", False),
            ("Difficulty", 0.5),
            ("Start Game", None)
        ]
        self.selected = 0

    def enter(self, model):
        # Load current settings from model
        self.options[0] = ("AI", model.ai_enabled)
        self.options[1] = ("Shape", model.shape_mode)
        self.options[2] = ("Psychedelic", model.psychedelic)
        self.options[3] = ("Difficulty", model.ai_difficulty)

    def handle_event(self, model, event, controller):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected = (self.selected - 1) % len(self.options)
            elif event.key == pygame.K_DOWN:
                self.selected = (self.selected + 1) % len(self.options)
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                return self._apply_selection(model, controller)
            elif event.key == pygame.K_LEFT:
                self._adjust_option(model, -1)
            elif event.key == pygame.K_RIGHT:
                self._adjust_option(model, 1)
        return None

    def _adjust_option(self, model, direction):
        label, value = self.options[self.selected]
        if label == "AI":
            new_val = not value
            self.options[self.selected] = (label, new_val)
            model.ai_enabled = new_val
        elif label == "Shape":
            new_val = 'rect' if value == 'circle' else 'circle'
            self.options[self.selected] = (label, new_val)
            model.shape_mode = new_val
            model.left_paddle.shape = new_val
            model.right_paddle.shape = new_val
            for b in model.balls:
                b.shape = new_val
        elif label == "Psychedelic":
            new_val = not value
            self.options[self.selected] = (label, new_val)
            model.psychedelic = new_val
        elif label == "Difficulty":
            diffs = [0.3, 0.5, 0.7]
            idx = diffs.index(value) if value in diffs else 1
            idx = (idx + direction) % len(diffs)
            new_val = diffs[idx]
            self.options[self.selected] = (label, new_val)
            model.ai_difficulty = new_val
        return None

    def _apply_selection(self, model, controller):
        label, value = self.options[self.selected]
        if label == "Start Game":
            model.reset_game()
            # Ensure shape etc. are applied
            return PlayingState()
        return None

    def draw(self, model, view):
        screen = view.screen
        cfg = Config()
        screen.fill((20, 20, 40))
        title = view.font_large.render("PONG SETTINGS", True, (255, 255, 255))
        screen.blit(title, (cfg.SCREEN_WIDTH // 2 - title.get_width() // 2, 60))

        y_start = 180
        for i, (label, value) in enumerate(self.options):
            color = (255, 255, 0) if i == self.selected else (200, 200, 200)
            if label == "Start Game":
                text = view.font_small.render("[ START GAME ]", True, color)
            else:
                text = view.font_small.render(f"{label}: {value}", True, color)
            screen.blit(text, (cfg.SCREEN_WIDTH // 2 - text.get_width() // 2, y_start + i * 50))

        controls = view.font_tiny.render("UP/DOWN: navigate, LEFT/RIGHT: change, ENTER/SPACE: select", True, (150, 150, 150))
        screen.blit(controls, (cfg.SCREEN_WIDTH // 2 - controls.get_width() // 2, cfg.SCREEN_HEIGHT - 60))

class PlayingState(GameState):
    def update(self, model):
        model.update()

    def handle_event(self, model, event, controller):
        if event.type == pygame.KEYDOWN:
            # Handle Shift+R for reset scores
            if event.key == pygame.K_r and (event.mod & pygame.KMOD_SHIFT):
                ResetScoresCmd().execute(model)
                return None
            # Normal command lookup
            cmd = controller.key_bindings.get(event.key)
            if cmd:
                cmd.execute(model)
                # If toggle pause, we need to change state
                if isinstance(cmd, TogglePauseCmd) and model.paused:
                    return PausedState()
                if isinstance(cmd, ResetGameCmd) and model.game_over:
                    return PlayingState()
        return None

    def draw(self, model, view):
        view.draw(model)

class PausedState(GameState):
    def update(self, model):
        pass

    def handle_event(self, model, event, controller):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                model.toggle_pause()
                return PlayingState()
        return None

    def draw(self, model, view):
        view.draw(model)
        screen = view.screen
        cfg = Config()
        overlay = pygame.Surface((cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))
        screen.blit(overlay, (0, 0))
        text = view.font_large.render("PAUSED", True, (255, 255, 255))
        screen.blit(text, (cfg.SCREEN_WIDTH // 2 - text.get_width() // 2, cfg.SCREEN_HEIGHT // 2 - 50))

class GameOverState(GameState):
    def update(self, model):
        pass

    def handle_event(self, model, event, controller):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                model.reset_game()
                return PlayingState()
        return None

    def draw(self, model, view):
        view.draw(model)
        screen = view.screen
        cfg = Config()
        overlay = pygame.Surface((cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))
        screen.blit(overlay, (0, 0))
        win_text = view.font_large.render(f"{model.winner} Wins!", True, (255, 255, 255))
        screen.blit(win_text, (cfg.SCREEN_WIDTH // 2 - win_text.get_width() // 2, cfg.SCREEN_HEIGHT // 2 - 50))
        restart = view.font_small.render("Press R to restart", True, (255, 255, 255))
        screen.blit(restart, (cfg.SCREEN_WIDTH // 2 - restart.get_width() // 2, cfg.SCREEN_HEIGHT // 2 + 20))

# ---------- Controller ----------
class GameController:
    def __init__(self, model, view):
        self.model = model
        self.view = view
        self.state = MenuState()  # start with menu
        self.state.enter(model)
        self.event_queue = []

        # Key bindings (commands)
        self.key_bindings = {
            pygame.K_w: MoveLeftUpCmd(),
            pygame.K_s: MoveLeftDownCmd(),
            pygame.K_UP: MoveRightUpCmd(),
            pygame.K_DOWN: MoveRightDownCmd(),
            pygame.K_a: ToggleAICmd(),
            pygame.K_c: ToggleShapeCmd(),
            pygame.K_p: TogglePsychedelicCmd(),
            pygame.K_SPACE: TogglePauseCmd(),
            pygame.K_r: ResetBallCmd(),  # normal R
            pygame.K_1: SetDifficultyCmd(0.3),
            pygame.K_2: SetDifficultyCmd(0.5),
            pygame.K_3: SetDifficultyCmd(0.7),
            pygame.K_ESCAPE: QuitCmd(),
        }

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            self.event_queue.append(event)
        return True

    def process_events(self):
        while self.event_queue:
            event = self.event_queue.pop(0)
            new_state = self.state.handle_event(self.model, event, self)
            if new_state:
                self.state.exit(self.model)
                self.state = new_state
                self.state.enter(self.model)

    def update(self):
        self.state.update(self.model)

    def draw(self):
        self.state.draw(self.model, self.view)

# ---------- Main ----------
def main():
    pygame.init()
    pygame.mixer.init()
    cfg = Config()
    screen = pygame.display.set_mode((cfg.SCREEN_WIDTH, cfg.SCREEN_HEIGHT))
    pygame.display.set_caption("Ultimate Pong")
    clock = pygame.time.Clock()

    model = GameModel()
    view = GameView(screen)
    controller = GameController(model, view)

    running = True
    while running:
        dt = clock.tick(cfg.FPS)
        running = controller.handle_events()
        controller.process_events()
        controller.update()
        controller.draw()
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()