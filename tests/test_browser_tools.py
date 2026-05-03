from easy_claw.tools.browser import build_browser_tools


def test_build_browser_tools_skips_browser_when_disabled():
    bundle = build_browser_tools(enabled=False, headless=False)

    assert bundle.tools == []
    assert bundle.cleanup == ()


def test_build_browser_tools_creates_langchain_playwright_tools(monkeypatch):
    captured = {}
    closed = []
    fake_tools = [object(), object()]

    class FakeBrowser:
        def close(self):
            closed.append("closed")

    fake_browser = FakeBrowser()

    def fake_create_browser(*, headless):
        captured["headless"] = headless
        return fake_browser

    class FakeToolkit:
        @classmethod
        def from_browser(cls, *, sync_browser):
            captured["sync_browser"] = sync_browser
            return cls()

        def get_tools(self):
            return fake_tools

    monkeypatch.setattr(
        "easy_claw.tools.browser.create_sync_playwright_browser",
        fake_create_browser,
        raising=False,
    )
    monkeypatch.setattr(
        "easy_claw.tools.browser.PlayWrightBrowserToolkit",
        FakeToolkit,
        raising=False,
    )

    bundle = build_browser_tools(enabled=True, headless=True)

    assert captured == {"headless": True, "sync_browser": fake_browser}
    assert bundle.tools == fake_tools

    bundle.close()

    assert closed == ["closed"]
