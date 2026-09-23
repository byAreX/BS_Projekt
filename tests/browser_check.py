"""Run against the preview server at 127.0.0.1:8765."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

output = Path(__file__).resolve().parents[1] / 'artifacts'
output.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':800, 'height':480}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:8765')
    page.wait_for_timeout(1200)
    page.screenshot(path=str(output / 'boot.png'))
    expect(page.locator('#boot')).to_be_hidden(timeout=5000)
    expect(page.locator('#mode')).to_have_text('VORSCHAU')
    page.screenshot(path=str(output / 'home.png'))
    page.locator('#open-settings').click()
    expect(page.locator('#pair')).to_be_disabled()
    page.screenshot(path=str(output / 'bluetooth.png'))
    page.locator('[data-tab="display"]').click()
    page.locator('[data-theme="light"]').click()
    expect(page.locator('#display')).to_have_class('light')
    page.reload()
    expect(page.locator('#display')).to_have_class('light')
    page.locator('#skip-boot').click()
    page.locator('#open-settings').click()
    page.locator('[data-tab="display"]').click()
    page.screenshot(path=str(output / 'display.png'))
    page.locator('[data-theme="dark"]').click()
    page.keyboard.press('Escape')
    page.locator('#open-carplay').click()
    expect(page.locator('#launch')).to_be_disabled()
    page.keyboard.press('Escape')
    page.locator('#replay').click()
    expect(page.locator('#boot')).to_be_visible()
    page.locator('#skip-boot').click()
    page.goto('http://127.0.0.1:8765/?boot=skip')
    expect(page.locator('#boot')).to_be_hidden()
    expect(page.locator('#home')).to_be_visible()
    expect(page.locator('#open-settings')).to_be_enabled()
    page.locator('#open-settings').click()
    expect(page.locator('#settings')).to_be_visible()
    page.keyboard.press('Escape')
    page.locator('#replay').click()
    expect(page.locator('#boot')).to_be_visible()
    page.locator('#skip-boot').click()
    for width, height in [(800,480),(1000,600),(390,844)]:
        page.set_viewport_size({'width':width,'height':height})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.locator('#open-settings').bounding_box()['height'] >= 44
    assert not errors, errors
    browser.close()
    print('Browser checks passed: boot, menu, settings, persistence, preview, native-boot handoff, responsive layout.')
