"""Unit tests for tasks.pcie pure renderers.

These tests must guarantee the managed-block logic NEVER mutates any line of the
existing /boot/firmware/config.txt outside its own markers. The regression
fixture REAL_CONFIG is the live file body from the Pi (snapshot pyinfra/config.txt,
minus the stray shell-prompt line).
"""

from tasks.pcie import (
    BLOCK_BEGIN,
    BLOCK_END,
    _ensure_block,
    _render_block,
    _strip_block,
)

# Live config.txt body from rpi5-4cpu-16gb-home-1 (no managed block yet).
REAL_CONFIG = """\
# For more options and information see
# http://rptl.io/configtxt
# Some settings may impact device functionality. See link above for details

# Uncomment some or all of these to enable the optional hardware interfaces
#dtparam=i2c_arm=on
#dtparam=i2s=on
#dtparam=spi=on

# Enable audio (loads snd_bcm2835)
dtparam=audio=on

# Additional overlays and parameters are documented
# /boot/firmware/overlays/README

# Automatically load overlays for detected cameras
camera_auto_detect=1

# Automatically load overlays for detected DSI displays
display_auto_detect=1

# Automatically load initramfs files, if found
auto_initramfs=1

# Enable DRM VC4 V3D driver
dtoverlay=vc4-kms-v3d
max_framebuffers=2

# Don't have the firmware create an initial video= setting in cmdline.txt.
# Use the kernel's default instead.
disable_fw_kms_setup=1

# Run in 64-bit mode
arm_64bit=1

# Disable compensation for displays with overscan
disable_overscan=1

# Run as fast as firmware / board allows
arm_boost=1

[cm4]
# Enable host mode on the 2711 built-in XHCI USB controller.
# This line should be removed if the legacy DWC2 controller is required
# (e.g. for USB device mode) or if USB support is not required.
otg_mode=1

[cm5]
dtoverlay=dwc2,dr_mode=host

[all]
"""


# ---------- _render_block ----------


def test_render_block_contains_pcie_directives_for_gen3() -> None:
    out = _render_block(3)
    assert "[all]" in out
    assert "dtparam=pciex1" in out
    assert "dtparam=pciex1_gen=3" in out


def test_render_block_gen_is_configurable() -> None:
    assert "dtparam=pciex1_gen=2" in _render_block(2)
    assert "dtparam=pciex1_gen=3" not in _render_block(2)


def test_render_block_wrapped_in_markers() -> None:
    out = _render_block(3)
    assert out.startswith(BLOCK_BEGIN)
    assert BLOCK_END in out


def test_render_block_single_trailing_newline() -> None:
    out = _render_block(3)
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


# ---------- _ensure_block: appending ----------


def test_ensure_block_appends_when_marker_absent() -> None:
    out = _ensure_block(REAL_CONFIG, 3)
    assert BLOCK_BEGIN in out
    assert BLOCK_END in out
    assert "dtparam=pciex1_gen=3" in out


def test_ensure_block_appends_after_existing_content() -> None:
    out = _ensure_block(REAL_CONFIG, 3)
    # Original content is a verbatim prefix (modulo trailing newline normalization).
    assert out.startswith(REAL_CONFIG.rstrip("\n"))


def test_ensure_block_exactly_one_block() -> None:
    out = _ensure_block(REAL_CONFIG, 3)
    assert out.count(BLOCK_BEGIN) == 1
    assert out.count(BLOCK_END) == 1


def test_ensure_block_single_trailing_newline() -> None:
    out = _ensure_block(REAL_CONFIG, 3)
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


# ---------- _ensure_block: idempotency + updates ----------


def test_ensure_block_idempotent() -> None:
    once = _ensure_block(REAL_CONFIG, 3)
    twice = _ensure_block(once, 3)
    assert once == twice


def test_ensure_block_updates_gen_in_place() -> None:
    gen2 = _ensure_block(REAL_CONFIG, 2)
    gen3 = _ensure_block(gen2, 3)
    assert gen3.count(BLOCK_BEGIN) == 1
    assert "dtparam=pciex1_gen=3" in gen3
    assert "dtparam=pciex1_gen=2" not in gen3


# ---------- SAFETY: never break the existing file ----------


def test_strip_round_trips_to_original() -> None:
    # Stripping the block back out yields the original (newline-normalized).
    out = _ensure_block(REAL_CONFIG, 3)
    assert _strip_block(out) == REAL_CONFIG.rstrip("\n") + "\n"


def test_existing_directives_preserved_unmodified() -> None:
    out = _ensure_block(REAL_CONFIG, 3)
    for line in (
        "dtparam=audio=on",
        "arm_64bit=1",
        "arm_boost=1",
        "dtoverlay=vc4-kms-v3d",
        "camera_auto_detect=1",
        "[cm4]",
        "otg_mode=1",
        "[cm5]",
        "dtoverlay=dwc2,dr_mode=host",
    ):
        assert line in out


def test_existing_line_order_unchanged() -> None:
    out = _ensure_block(REAL_CONFIG, 3)
    body = out[: out.index(BLOCK_BEGIN)]
    assert body.index("dtparam=audio=on") < body.index("arm_64bit=1")
    assert body.index("arm_64bit=1") < body.index("[cm4]")
    assert body.index("[cm4]") < body.index("[cm5]")


def test_commented_directives_stay_commented() -> None:
    out = _ensure_block(REAL_CONFIG, 3)
    assert "#dtparam=i2c_arm=on" in out
    assert "#dtparam=spi=on" in out
