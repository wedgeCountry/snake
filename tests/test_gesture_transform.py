"""Verify the gesture->world transform math (mirrors static/main.js + view.js)
for arbitrary camera yaw angles: a swipe along the cube's visual edge must
map to the correct world axis for any rotation."""

import math


def ground_basis(yaw):
    # camera looks along -Z rotated by yaw around Y (three.js convention)
    fx, fz = -math.sin(yaw), -math.cos(yaw)
    length = math.hypot(fx, fz) or 1
    forward = (fx / length, fz / length)
    right = (-forward[1], forward[0])
    return right, forward


def swipe_to_world(dx, dy, yaw):
    right, forward = ground_basis(yaw)
    wx = right[0] * dx - forward[0] * dy
    wz = right[1] * dx - forward[1] * dy
    return wx, wz


def direction_of(wx, wz):
    if abs(wx) > abs(wz):
        return "right" if wx > 0 else "left"
    return "forward" if wz > 0 else "back"


# camera yaw 45° (current default diagonal view), screen-down swipe = +y
# must map to "forward" (toward viewer, +z-ish in world after transform)
import pytest


@pytest.mark.parametrize("yaw_deg", [0, 30, 45, 90, 135, 180, 270])
def test_swipe_along_visual_forward_maps_to_forward(yaw_deg):
    yaw = math.radians(yaw_deg)
    wx, wz = swipe_to_world(0, 100, yaw)
    assert direction_of(wx, wz) == "forward"


@pytest.mark.parametrize("yaw_deg", [0, 30, 45, 90, 135, 180, 270])
def test_swipe_along_visual_right_maps_to_right(yaw_deg):
    yaw = math.radians(yaw_deg)
    wx, wz = swipe_to_world(100, 0, yaw)
    assert direction_of(wx, wz) == "right"


@pytest.mark.parametrize("yaw_deg", [0, 30, 45, 90, 135, 180, 270])
def test_swipe_up_maps_to_back(yaw_deg):
    yaw = math.radians(yaw_deg)
    wx, wz = swipe_to_world(0, -100, yaw)
    assert direction_of(wx, wz) == "back"


def test_45_degree_matches_old_hardcoded_formula():
    # at yaw=45°, old code wx=dx+dy, wz=dy-dx must agree with the general one
    for dx, dy in [(50, 10), (-30, 80), (0, 100), (100, 0)]:
        yaw = math.radians(45)
        wx, wz = swipe_to_world(dx, dy, yaw)
        assert (round(wx), round(wz)) == (round(dx + dy), round(dy - dx)) or \
               direction_of(wx, wz) == direction_of(dx + dy, dy - dx)
