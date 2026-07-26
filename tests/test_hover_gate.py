#!/usr/bin/env python3
"""Radial menu opening with an option already selected (issue #60).

The menu window is clamped on-screen, so opening near a monitor edge leaves the
ring centre away from the pointer. Captured from a real KDE Wayland session:

    KDE placement: logical (3652,262) -> Qt (4420, 322) origin (4098, 0)
    kde_mon={'x': 3072, 'y': 0, 'width': 1080, 'height': 1920, 'name': 'DP-1'}

The pointer was at y=262 but the window had to clamp its top to 0, putting the
ring centre at y=322. That is 60 physical pixels, and at the 1920/1440 ring
scale exactly 45 logical ones: the boundary of the centre zone. The first hover
sample therefore fell in the top slice with no user movement at all.

Run: python3 -m pytest tests/test_hover_gate.py -q
"""

import sys

# overlay_constants uses flat imports (matching the installed layout), so put
# the overlay dir itself on the path.
sys.path.insert(0, "overlay")

from overlay_constants import (
    CENTER_ZONE_RADIUS,
    HOVER_ARM_DISTANCE,
    hover_gate,
    hover_is_armed,
)

RING_SCALE = 1920 / 1440  # DP-1 in the captured session
# Pointer offset from the ring centre, logical ring pixels, as logged above.
CLAMPED_OPEN = (0, (262 - 322) / RING_SCALE)


def test_clamped_open_lands_outside_the_centre_zone():
    # Without the gate this offset alone is enough to highlight a slice:
    # _poll_cursor and mouseMoveEvent both treat `distance < center_radius`
    # as "no slice", and 45.0 is not < 45.
    assert abs(CLAMPED_OPEN[1]) >= CENTER_ZONE_RADIUS


def test_first_sample_never_arms():
    assert not hover_is_armed(None, *CLAMPED_OPEN)


def test_press_jitter_stays_disarmed():
    dx, dy = CLAMPED_OPEN
    assert not hover_is_armed(CLAMPED_OPEN, dx + 3, dy - 2)


def test_deliberate_move_arms():
    dx, dy = CLAMPED_OPEN
    assert hover_is_armed(CLAMPED_OPEN, dx + 25, dy)


def test_threshold_is_the_arming_distance():
    assert hover_is_armed((0, 0), HOVER_ARM_DISTANCE, 0)
    assert not hover_is_armed((0, 0), HOVER_ARM_DISTANCE - 0.01, 0)


def test_diagonal_jitter_uses_euclidean_distance():
    # 8,8 is 11.3px away: inside the threshold even though each axis is not.
    assert not hover_is_armed((0, 0), 8, 8)


def test_the_first_sample_of_each_source_only_anchors():
    anchors, armed = {}, set()
    assert not hover_gate(anchors, armed, "poll", *CLAMPED_OPEN)
    assert anchors["poll"] == CLAMPED_OPEN
    assert not armed


def test_a_source_stays_armed_once_it_has_moved():
    anchors, armed = {"mouse": (0, 0)}, set()
    assert hover_gate(anchors, armed, "mouse", 30, 0)
    # Back near the anchor: already committed, so hover keeps working.
    assert hover_gate(anchors, armed, "mouse", 1, 0)


def test_one_source_arming_does_not_arm_another():
    # The daemon reports offsets from the press point, so a firm click drags
    # past the threshold there while the Qt sample still carries the clamp
    # offset. Arming must not leak across, or the clamped open is preselected
    # anyway - the exact bug this gate exists to prevent.
    anchors, armed = {"daemon": (0, 0)}, set()
    assert hover_gate(anchors, armed, "daemon", 0, -HOVER_ARM_DISTANCE)
    assert armed == {"daemon"}
    assert not hover_gate(anchors, armed, "poll", *CLAMPED_OPEN)
