"""GUI tests: drive the real frontend in a headless Chromium via Playwright.

The test loads the page, selects the snake game in the game picker (the first
step is "select a game" — nothing auto-starts), taps the "Start" screen and
then presses each button on the page once after the other.

Run with:
    pip install -r requirements.txt -r requirements-gui.txt
    python -m playwright install chromium
    python -m pytest tests/test_gui.py -q
"""

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server.app:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=REPO_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            if httpx.get(base + "/api/games", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        proc.terminate()
        pytest.fail("uvicorn did not come up on " + base)
    yield base
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def page(server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser.new_page()
        browser.close()


def _text(pg, selector):
    return pg.locator(selector).text_content().strip()


def _dismiss_overlay_if_shown(pg):
    # a finished game shows the overlay on top of the picker/header; tapping
    # it restarts, so the buttons underneath stay reachable
    if "hidden" not in (pg.locator("#overlay").get_attribute("class") or ""):
        pg.click("#overlay")
        pg.wait_for_selector("#overlay.hidden", state="attached", timeout=10000)


def test_gui_select_snake_start_press_each_button(page, server):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(server + "/", wait_until="domcontentloaded")
    picker = page.locator("#gamePicker button")
    picker.first.wait_for(timeout=10000)
    assert picker.count() >= 2, "game picker should list collector and snake"

    # 1. first step is "select a game": no game auto-starts, the prompt is shown
    assert "hidden" not in (page.locator("#overlay").get_attribute("class") or ""), \
        "select-a-game prompt should be visible before any game is chosen"
    assert page.evaluate("document.body.classList.contains('no-game')"), \
        "no game selected yet"

    # 2. select snake in the game picker -> the "Start" screen for snake appears
    page.evaluate("window.__cv = document.getElementById('scene')")
    page.click('#gamePicker button[data-game-id="snake"]')
    page.wait_for_function(
        "window.__cv !== document.getElementById('scene')", timeout=10000)
    page.wait_for_function(
        "!document.getElementById('overlay').classList.contains('hidden') && "
        "document.getElementById('ovTitle').textContent.trim() === '3D Snake'",
        timeout=10000)

    # 3. tap the start screen -> the game loop starts, overlay hides
    page.click("#overlay")
    page.wait_for_selector("#overlay.hidden", state="attached", timeout=10000)

    # 4. press each button on the page once after the other; after each press
    # wait until the shell has settled (game switched / label updated).
    # pointerdown is dispatched directly on the button because a game-over
    # overlay may cover the header at any moment and would intercept a
    # physical click; the app listens for pointerdown on these buttons.
    steps = [
        ('#gamePicker button[data-game-id="collector"]', None),
        ('#gamePicker button[data-game-id="snake"]', None),
        ("#modeBtn", ("modeBtn", "Modus: Multi")),
        ("#torusBtn", ("torusBtn", "Torus: Aus")),
    ]
    for selector, label in steps:
        _dismiss_overlay_if_shown(page)
        if label is None:
            page.evaluate("window.__cv = document.getElementById('scene')")
            page.locator(selector).dispatch_event("click")
            page.wait_for_function(
                "window.__cv !== document.getElementById('scene')", timeout=10000)
        else:
            el, expected = label
            page.locator(selector).dispatch_event("pointerdown")
            page.wait_for_function(
                f"document.getElementById('{el}').textContent.trim() === '{expected}'",
                timeout=10000)

    assert _text(page, "#score").isdigit(), "snake HUD shows a numeric score"
    assert errors == [], f"page errors during GUI test: {errors}"
