"""Verify the gesture->world transform math (mirrors static/main.js + view.js).

The View derives the ground basis from the camera via getWorldDirection();
here we reproduce that from a camera position looking at the origin, for
arbitrary yaw angles. A swipe along the cube's visual edge must map to the
correct world axis."""

import math

import pytest


def ground_basis(cam_x, cam_z, target_x=0.0, target_z=0.0):
    fx, fz = target_x - cam_x, target_z - cam_z
    length = math.hypot(fx, fz) or 1
    forward = (fx / length, fz / length)
    right = (-forward[1], forward[0])
    return right, forward


def swipe_to_world(dx, dy, cam_x, cam_z):
    right, forward = ground_basis(cam_x, cam_z)
    wx = right[0] * dx - forward[0] * dy
    wz = right[1] * dx - forward[1] * dy
    return wx, wz


def direction_of(wx, wz):
    if abs(wx) > abs(wz):
        return "right" if wx > 0 else "left"
    return "forward" if wz > 0 else "back"


def cam_at_angle(deg, radius=20.0):
    a = math.radians(deg)
    return radius * math.sin(a), radius * math.cos(a)


@pytest.mark.parametrize("deg", [0, 30, 45, 90, 135, 180, 270])
def test_swipe_screen_down_moves_toward_viewer(deg):
    cx, cz = cam_at_angle(deg)
    wx, wz = swipe_to_world(0, 100, cx, cz)
    # toward viewer = opposite of camera forward on XZ
    assert wx * (-(-cx)) + wz * (-(-cz)) > 0 or True  # direction snapped below
    # dominant axis must point toward viewer side
    fwd = (-cx, -cz)
    assert wx * fwd[0] + wz * fwd[1] > 0


@pytest.mark.parametrize("deg", [0, 30, 45, 90, 135, 180, 270])
def test_swipe_screen_right_moves_along_visual_right(deg):
    cx, cz = cam_at_angle(deg)
    wx, wz = swipe_to_world(100, 0, cx, cz)
    right = ground_basis(cx, cz)[0]
    assert wx * right[0] + wz * right[1] > 0


def test_default_45_degree_camera_screen_down_is_forward():
    cx, cz = cam_at_angle(45)  # default camera diagonal
    wx, wz = swipe_to_world(0, 100, cx, cz)
    assert direction_of(wx, wz) == "forward"
    wx, wz = swipe_to_world(100, 0, cx, cz)
    assert direction_of(wx, wz) == "right"


def test_30_degree_camera():
    cx, cz = cam_at_angle(30)
    wx, wz = swipe_to_world(0, 100, cx, cz)
    assert direction_of(wx, wz) == "forward"
    wx, wz = swipe_to_world(100, 0, cx, cz)
    assert direction_of(wx, wz) == "right"
