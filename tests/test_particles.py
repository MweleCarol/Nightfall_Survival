import random

from pygame import Vector2

from src.world.particles import ParticleSystem


def make() -> ParticleSystem:
    return ParticleSystem(random.Random(1))


def test_burst_adds_the_requested_number_of_particles():
    system = make()
    system.burst(Vector2(100, 100), Vector2(1, 0), 12)
    assert len(system.particles) == 12


def test_the_particle_cap_is_respected():
    system = ParticleSystem(random.Random(1), max_particles=10)
    system.burst(Vector2(0, 0), Vector2(1, 0), 50)
    assert len(system.particles) == 10


def test_a_directed_burst_stays_inside_its_cone():
    system = make()
    system.burst(Vector2(0, 0), Vector2(1, 0), 60, spread=20.0)
    for p in system.particles:
        angle = Vector2(1, 0).angle_to(Vector2(p.vx, p.vy))
        assert abs((angle + 180) % 360 - 180) <= 20.0 + 1e-6


def test_a_burst_without_direction_goes_every_way():
    system = make()
    system.burst(Vector2(0, 0), Vector2(0, 0), 60)
    assert any(p.vx > 0 for p in system.particles) and any(p.vx < 0 for p in system.particles)
    assert any(p.vy > 0 for p in system.particles) and any(p.vy < 0 for p in system.particles)


def test_particles_move_age_and_disappear():
    system = make()
    system.burst(Vector2(0, 0), Vector2(1, 0), 5, life=(0.3, 0.3))
    system.update(0.1)
    assert len(system.particles) == 5 and all(p.x > 0 for p in system.particles)
    system.update(0.5)
    assert system.particles == []


def test_drag_slows_particles_down():
    system = make()
    system.burst(Vector2(0, 0), Vector2(1, 0), 1, speed=(200.0, 200.0), life=(5.0, 5.0), drag=4.0)
    before = abs(system.particles[0].vx)
    system.update(0.1)
    assert abs(system.particles[0].vx) < before