"""GUI tests: drive the real frontend in a headless Chromium via Playwright.

The first screen is the game-select menu (nothing auto-starts); the test picks
the snake game there, taps the "Start" screen and then presses each button on
the page once after the other. A second test verifies that the game loop really
starts: after tapping start, the snake head must advance (client state via
window.__shell and server state via REST).

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
def browser(server):
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


def _new_page(browser):
    # each test gets its own context, so sessions/cookies stay isolated
    return browser.new_context().new_page()


def _text(pg, selector):
    return pg.locator(selector).text_content().strip()


def _dismiss_overlay_if_shown(pg):
    # a finished game shows the overlay on top of the picker/header; tapping
    # it restarts, so the buttons underneath stay reachable. dispatch pointerdown
    # directly (that is what the app listens to) to avoid click actionability
    # races with the overlay appearing/disappearing mid-test
    if "hidden" not in (pg.locator("#overlay").get_attribute("class") or ""):
        pg.locator("#overlay").dispatch_event("pointerdown")
        pg.wait_for_selector("#overlay.hidden", state="attached", timeout=10000)


def _select_snake_and_start(pg):
    """First screen = game select menu; pick snake, then tap its start screen."""
    pg.wait_for_selector('#gameSelectList button[data-game-id="snake"]', timeout=10000)
    pg.click('#gameSelectList button[data-game-id="snake"]')
    pg.wait_for_function(
        "!document.getElementById('overlay').classList.contains('hidden') && "
        "document.getElementById('ovTitle').textContent.trim() === '3D Snake'",
        timeout=10000, polling=250)
    pg.locator("#overlay").dispatch_event("pointerdown")
    pg.wait_for_selector("#overlay.hidden", state="attached", timeout=10000)


def test_gui_select_snake_start_press_each_button(browser, server):
    page = _new_page(browser)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(server + "/", wait_until="domcontentloaded")
    picker = page.locator("#gamePicker button")
    picker.first.wait_for(timeout=10000)
    assert picker.count() >= 2, "game picker should list collector and snake"

    # 1. first step is "select a game": the select menu is shown, no game starts
    assert page.locator("#gameSelect").is_visible(), "game-select menu is the first screen"
    assert page.evaluate("document.body.classList.contains('no-game')"), \
        "no game selected yet"
    assert page.locator("#gameSelectList button").count() >= 2, \
        "select menu lists collector and snake as cards"
    assert "hidden" in (page.locator("#overlay").get_attribute("class") or ""), \
        "start overlay is hidden while no game is selected"

    # 2. select snake in the game-select menu -> the "Start" screen for snake appears
    page.evaluate("window.__cv = document.getElementById('scene')")
    page.click('#gameSelectList button[data-game-id="snake"]')
    page.wait_for_function(
        "window.__cv !== document.getElementById('scene')", timeout=10000, polling=250)
    page.wait_for_function(
        "!document.getElementById('overlay').classList.contains('hidden') && "
        "document.getElementById('ovTitle').textContent.trim() === '3D Snake'",
        timeout=10000, polling=250)

    # 3. tap the start screen -> the game loop starts, overlay hides
    page.locator("#overlay").dispatch_event("pointerdown")
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
                "window.__cv !== document.getElementById('scene')", timeout=10000, polling=250)
        else:
            el, expected = label
            page.locator(selector).dispatch_event("pointerdown")
            page.wait_for_function(
                f"document.getElementById('{el}').textContent.trim() === '{expected}'",
                timeout=10000, polling=250)

    assert _text(page, "#score").isdigit(), "snake HUD shows a numeric score"
    assert errors == [], f"page errors during GUI test: {errors}"
    page.context.close()


def test_gui_game_loop_starts_after_start(browser, server):
    """After selecting snake and tapping start, the game loop must actually run:
    the client viewmodel receives advancing state (via WebSocket) and the
    server-side session advances too (checked over REST with the page cookies)."""
    page = _new_page(browser)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(
        "window.__wslog = [];"
        "const O = window.WebSocket;"
        "window.WebSocket = function(u, p) { const w = new O(u, p);"
        "  w.addEventListener('open', () => window.__wslog.push('open'));"
        "  w.addEventListener('close', (e) => window.__wslog.push('close:' + e.code));"
        "  w.addEventListener('error', () => window.__wslog.push('error'));"
        "  w.addEventListener('message', () => window.__wslog.push('msg'));"
        "  return w; };"
        "window.WebSocket.prototype = O.prototype;")

    page.goto(server + "/", wait_until="domcontentloaded")
    _select_snake_and_start(page)

    # client side: the shell's viewmodel is running and exposes state
    assert page.evaluate("window.__shell && window.__shell.vm && window.__shell.vm.running === true"), \
        "viewmodel reports running after tapping start"
    page.wait_for_function(
        "!!(window.__shell.vm.state && window.__shell.vm.state.snake && window.__shell.vm.state.snake[0])",
        timeout=10000, polling=250)
    head0 = page.evaluate("JSON.stringify(window.__shell.vm.state.snake[0])")
    # the loop ticks every ~260ms; the head must move within a few seconds.
    # poll from Python (not rAF) so the check also works where rAF is throttled
    deadline = time.time() + 15
    head1 = head0
    while time.time() < deadline:
        head1 = page.evaluate("JSON.stringify(window.__shell.vm.state.snake[0])")
        if head1 != head0:
            break
        time.sleep(0.25)
    assert head1 != head0, \
        f"client game loop did not start: head stuck at {head0} for 15s " \
        f"(ws log: {page.evaluate('window.__wslog.slice(0, 8)')}, " \
        f"polling fallback active: {page.evaluate('!!(window.__shell.vm && window.__shell.vm._timer)')})"
    assert page.evaluate("window.__shell.vm.state.status") == "running", \
        "game still running while the loop advances"

    # server side: same session advances over REST as well
    cookies = {c["name"]: c["value"] for c in page.context.cookies(server)}
    r1 = httpx.get(server + "/api/games/snake/state", cookies=cookies, timeout=5).json()
    time.sleep(1.2)
    r2 = httpx.get(server + "/api/games/snake/state", cookies=cookies, timeout=5).json()
    assert r2["status"] == "running", "server session is running"
    assert r1["state"]["snake"][0] != r2["state"]["snake"][0], \
        f"server loop did not advance the snake: {r1['state']['snake'][0]} -> {r2['state']['snake'][0]}"

    assert errors == [], f"page errors during loop test: {errors}"
    page.context.close()
