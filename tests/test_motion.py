import math
from cat_art import CatRig

def test_transitions_remain_continuous_and_finite():
    rig = CatRig()
    previous = rig.pose.facing
    for action in ('idle', 'chase', 'cuddle', 'eat', 'sleep', 'poop', 'held'):
        for i in range(240):
            rig.advance(1 / 60, 200 if action == 'chase' else 0, -1 if i % 120 < 60 else 1, action, (1, -1))
            assert abs(rig.pose.facing - previous) < .35
            previous = rig.pose.facing
            assert all(math.isfinite(value) for value in vars(rig.pose).values())
            assert all(math.isfinite(value) for value in rig.tail + rig.tail_velocity)
            assert all(abs(value) < 15 for value in rig.tail_velocity)

def test_motion_uses_elapsed_time_instead_of_frame_count():
    sixty, thirty = CatRig(), CatRig()
    for _ in range(600): sixty.advance(1/60, 160, -1, 'chase')
    for _ in range(300): thirty.advance(1/30, 160, -1, 'chase')
    assert abs(sixty.pose.clock - thirty.pose.clock) < 1e-9
    assert abs(sixty.pose.facing - thirty.pose.facing) < 1e-9
    assert abs(sixty.pose.phase - thirty.pose.phase) < .15

def test_pause_does_not_make_rig_explode():
    rig = CatRig()
    rig.advance(600, 1000, -1, 'cuddle')
    assert rig.pose.clock <= .05
    assert all(math.isfinite(value) for value in rig.tail)

def test_sleep_and_cuddle_blend_back_to_neutral():
    rig = CatRig()
    for _ in range(240): rig.advance(1/60, 0, 1, 'cuddle')
    assert rig.pose.cuddle > .999
    for _ in range(240): rig.advance(1/60, 0, 1, 'sleep')
    assert rig.pose.sleep > .999 and rig.pose.cuddle < .001
    for _ in range(240): rig.advance(1/60, 0, 1, 'idle')
    assert rig.pose.sleep < .001


def test_hiss_arches_and_recovers():
    rig = CatRig('tabby')
    for _ in range(240): rig.advance(1/60, 0, 1, 'hiss')
    assert rig.pose.hiss > .99
    # Tail points up while frightened.
    assert all(angle < -.9 for angle in rig.tail)
    for _ in range(240): rig.advance(1/60, 0, 1, 'idle')
    assert rig.pose.hiss < .01


def test_every_breed_has_a_complete_palette():
    from cat_art import BREEDS, ADOPTABLE
    required = {'zh', 'en', 'fur', 'outline', 'patches', 'stripes', 'legs', 'paw', 'tail', 'face',
                'face_marks', 'ear', 'eyes', 'muzzle', 'nose', 'mouth', 'whisker', 'sheen'}
    for name in ['black', 'white', 'tabby', 'orange', 'siamese', 'ragdoll']:
        assert name in ADOPTABLE
    for name, spec in BREEDS.items():
        assert required <= set(spec), name
        assert len(spec['eyes']) == 2
    assert CatRig('unknown').breed == 'calico'


def test_hiss_styles_reshuffle_smoothly():
    from cat_art import HISS_STYLES
    from PyQt5.QtGui import QImage, QPainter
    rig = CatRig('orange')
    seen = set()
    for i in range(60 * 40):
        rig.advance(1 / 60, 0, 1, 'hiss')
        seen.add(rig.style)
        assert abs(sum(rig.style_weights.values()) - 1) < .05
        assert all(math.isfinite(v) for v in rig.tail + list(rig.style_weights.values()))
    assert len(seen) >= 3 and seen <= set(HISS_STYLES)
    for style in HISS_STYLES:
        fixed = CatRig('tabby', hiss_style=style)
        for _ in range(90): fixed.advance(1 / 60, 0, 1, 'hiss')
        assert fixed.style == style and fixed.w(style) > .9
