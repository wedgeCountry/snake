"""Verify the gesture->world transform (mirrors static/main.js + view.js).

Basis is derived from the camera position looking at the origin, exactly as
the View does via getWorldDirection(). Invariants for any camera yaw:
- swiping screen-down moves the snake toward the viewer (world +camera side)
- swiping screen-right moves along the camera's visual right
"""

import math

import pytest


def ground_basis(cx, cz):
    fx, fz = -cx, -cz
    length = math.hypot(fx, fz) or 1
    forward = (fx / length, fz / length)
    right = (-forward[1], forward[0])
    return right, forward


def swipe_to_world(dx, dy, cx, cz):
    right, forward = ground_basis(cx, cz)
    return right[0] * dx - forward[0] * dy, right[1] * dx - forward[1] * dy


def direction_of(wx, wz):
    if abs(wx) > abs(wz):
        return "right" if wx > 0 else "left"
    return "forward" if wz > 0 else "back"


def cam_at_angle(deg, radius=20.0):
    a = math.radians(deg)
    return radius * math.sin(a), radius * math.cos(a)


@pytest.mark.parametrize("deg", [0, 30, 45, 90, 135, 180, 270])
def test_swipe_down_moves_toward_viewer(deg):
    cx, cz = cam_at_angle(deg)
    wx, wz = swipe_to_world(0, 100, cx, cz)
    assert wx * cx + wz * cz > 0  # same side as the camera = toward viewer


@pytest.mark.parametrize("deg", [0, 30, 45, 90, 135, 180, 270])
def test_swipe_right_moves_along_visual_right(deg):
    cx, cz = cam_at_angle(deg)
    wx, wz = swipe_to_world(100, 0, cx, cz)
    right = ground_basis(cx, cz)[0]
    assert wx * right[0] + wz * right[1] > 0


def test_default_45_degree_camera_snaps_to_axes():
    cx, cz = cam_at_angle(45)
    assert direction_of(*swipe_to_world(0, 100, cx, cz)) == "forward"
    assert direction_of(*swipe_to_world(100, 0, cx, cz)) == "right"
    assert direction_of(*swipe_to_world(0, -100, cx, cz)) == "back"
    assert direction_of(*swipe_to_world(-100, 0, cx, cz)) == "left"


def test_30_degree_camera_snaps_to_axes():
    cx, cz = cam_at_angle(30)
    assert direction_of(*swipe_to_world(0, 100, cx, cz)) == "forward"
    assert direction_of(*swipe_to_world(100, 0, cx, cz)) == "right"
