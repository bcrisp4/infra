"""Unit tests for tasks.podman._rewrite_cmdline."""

import pytest

from tasks.podman import _rewrite_cmdline

REAL_PI5_CMDLINE = (
    "console=serial0,115200 console=tty1 root=PARTUUID=a1197ef5-02 rootfstype=ext4 "
    "fsck.repair=yes rootwait cfg80211.ieee80211_regdom=US "
    "ds=nocloud;i=rpi-imager-1779240414845"
)

REAL_PI5_EXPECTED = (
    "console=serial0,115200 console=tty1 root=PARTUUID=a1197ef5-02 rootfstype=ext4 "
    "fsck.repair=yes rootwait cfg80211.ieee80211_regdom=US "
    "ds=nocloud;i=rpi-imager-1779240414845 cgroup_enable=memory\n"
)


@pytest.mark.parametrize(
    ("description", "given", "expected"),
    [
        (
            "already-correct: ensure token present, no drop tokens, order preserved",
            "foo=1 cgroup_enable=memory bar=2",
            "foo=1 cgroup_enable=memory bar=2\n",
        ),
        (
            "drop cgroup_disable=memory at start",
            "cgroup_disable=memory foo=1 cgroup_enable=memory",
            "foo=1 cgroup_enable=memory\n",
        ),
        (
            "drop cgroup_disable=memory in middle",
            "foo=1 cgroup_disable=memory bar=2 cgroup_enable=memory",
            "foo=1 bar=2 cgroup_enable=memory\n",
        ),
        (
            "drop cgroup_disable=memory at end",
            "foo=1 cgroup_enable=memory cgroup_disable=memory",
            "foo=1 cgroup_enable=memory\n",
        ),
        (
            "drop stray cgroup_memory=1 from prior revisions",
            "foo=1 cgroup_memory=1 cgroup_enable=memory",
            "foo=1 cgroup_enable=memory\n",
        ),
        (
            "drop both cgroup_memory=1 and cgroup_disable=memory",
            "foo=1 cgroup_disable=memory cgroup_memory=1 cgroup_enable=memory bar=2",
            "foo=1 cgroup_enable=memory bar=2\n",
        ),
        (
            "append missing cgroup_enable=memory",
            "foo=1 bar=2",
            "foo=1 bar=2 cgroup_enable=memory\n",
        ),
        (
            "collapse multiple internal spaces",
            "foo=1    bar=2  cgroup_enable=memory",
            "foo=1 bar=2 cgroup_enable=memory\n",
        ),
        (
            "tokenize mixed whitespace (tabs + spaces)",
            "foo=1\tbar=2 \t cgroup_enable=memory",
            "foo=1 bar=2 cgroup_enable=memory\n",
        ),
        (
            "trailing newline in input does not produce double newline",
            "foo=1 cgroup_enable=memory\n",
            "foo=1 cgroup_enable=memory\n",
        ),
        (
            "input without trailing newline still produces one",
            "foo=1 cgroup_enable=memory",
            "foo=1 cgroup_enable=memory\n",
        ),
        (
            "empty input yields just the ensure token",
            "",
            "cgroup_enable=memory\n",
        ),
        (
            "whitespace-only input behaves like empty",
            "   \t  \n",
            "cgroup_enable=memory\n",
        ),
        (
            "drop both targets + append ensure",
            "foo=1 cgroup_disable=memory bar=2 cgroup_memory=1",
            "foo=1 bar=2 cgroup_enable=memory\n",
        ),
    ],
)
def test_rewrite_cmdline_cases(description: str, given: str, expected: str) -> None:
    assert _rewrite_cmdline(given) == expected, description


def test_rewrite_cmdline_real_pi5_input() -> None:
    """Exercise the function against the actual cmdline observed on rpi5-4cpu-16gb-home."""
    assert _rewrite_cmdline(REAL_PI5_CMDLINE) == REAL_PI5_EXPECTED


def test_rewrite_cmdline_strips_prior_revision_artifact() -> None:
    """A cmdline.txt previously patched with `cgroup_memory=1 cgroup_enable=memory`
    must be cleaned up: keep cgroup_enable=memory, drop cgroup_memory=1.
    """
    prior_output = (
        "console=serial0,115200 console=tty1 root=PARTUUID=a1197ef5-02 rootfstype=ext4 "
        "fsck.repair=yes rootwait cfg80211.ieee80211_regdom=US "
        "ds=nocloud;i=rpi-imager-1779240414845 cgroup_memory=1 cgroup_enable=memory"
    )
    assert _rewrite_cmdline(prior_output) == REAL_PI5_EXPECTED


@pytest.mark.parametrize(
    "given",
    [
        "foo=1 cgroup_disable=memory bar=2",
        "foo=1 cgroup_enable=memory",
        "foo=1 cgroup_disable=memory cgroup_memory=1 cgroup_enable=memory bar=2",
        "",
        "   \t  ",
        REAL_PI5_CMDLINE,
        "foo=1\tbar=2 \t cgroup_enable=memory",
    ],
)
def test_rewrite_cmdline_idempotent(given: str) -> None:
    """Applying the rewrite twice equals applying it once."""
    once = _rewrite_cmdline(given)
    twice = _rewrite_cmdline(once)
    assert once == twice


@pytest.mark.parametrize(
    "given",
    [
        "foo=1 cgroup_disable=memory bar=2",
        "foo=1 cgroup_memory=1 cgroup_enable=memory",
        REAL_PI5_CMDLINE,
        "",
    ],
)
def test_rewrite_cmdline_output_invariants(given: str) -> None:
    out = _rewrite_cmdline(given)
    assert out.endswith("\n"), "output must terminate with a single newline"
    assert not out.endswith("\n\n"), "output must not have a trailing blank line"
    body = out.rstrip("\n")
    assert "  " not in body, "no double-spaces in output body"
    tokens = body.split()
    assert "cgroup_enable=memory" in tokens, "output must contain cgroup_enable=memory"
    assert "cgroup_disable=memory" not in tokens, "output must not contain cgroup_disable=memory"
    assert "cgroup_memory=1" not in tokens, "output must not contain cgroup_memory=1"
