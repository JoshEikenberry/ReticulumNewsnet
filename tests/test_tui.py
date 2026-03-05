"""Tests for the TUI frontend using Textual's async test pilot."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from newsnet.filters import TextFilterStore
from newsnet.store import Store
from tui.app import ComposeScreen, FilterScreen, AddFilterScreen, NewsnetApp


@pytest.fixture
def mock_node(tmp_path):
    """Create a mock Node with a real Store and TextFilterStore for testing."""
    store = Store(tmp_path / "test.db")
    filter_store = TextFilterStore(tmp_path / "filters")
    filter_store.ensure_files()
    node = MagicMock()
    node.store = store
    node.filter_store = filter_store
    node.config.display_name = "TestUser"
    return node


def _insert_article(store, newsgroup, subject, author="Alice", body="Hello", msg_id=None, references=None):
    """Helper to insert an article directly into the store."""
    import json as _json
    ts = time.time()
    mid = msg_id or f"{newsgroup}-{subject}-{ts}"
    store.store_article({
        "message_id": mid,
        "author_hash": "a1b2c3d4e5f6",
        "author_key": b"key",
        "display_name": author,
        "newsgroup": newsgroup,
        "subject": subject,
        "body": body,
        "references": _json.dumps(references or []),
        "timestamp": ts,
        "signature": b"sig",
        "received_at": ts,
    })
    return mid


@pytest.mark.asyncio
async def test_app_mounts(mock_node):
    """App should mount without errors."""
    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        assert app.title == "Newsnet"
        assert app.query_one("#groups-list") is not None
        assert app.query_one("#articles-table") is not None
        assert app.query_one("#reader") is not None


@pytest.mark.asyncio
async def test_groups_populate(mock_node):
    """Groups list should populate from store."""
    _insert_article(mock_node.store, "test.general", "Hello")
    _insert_article(mock_node.store, "tech.linux", "Kernel")

    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        groups_list = app.query_one("#groups-list")
        children = list(groups_list.children)
        names = [c.name for c in children if hasattr(c, "name") and c.name]
        assert "test.general" in names
        assert "tech.linux" in names


@pytest.mark.asyncio
async def test_select_group_loads_articles(mock_node):
    """Selecting a group should load its articles into the DataTable."""
    _insert_article(mock_node.store, "test.general", "First post")
    _insert_article(mock_node.store, "test.general", "Second post")

    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        groups_list = app.query_one("#groups-list")
        # Select the first group
        groups_list.index = 0
        groups_list.action_select_cursor()
        await pilot.pause()

        table = app.query_one("#articles-table")
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_select_article_shows_content(mock_node):
    """Selecting an article should display it in the reader pane."""
    mid = _insert_article(
        mock_node.store, "test.general", "Hello world",
        author="Alice", body="Article body text here"
    )

    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        # Load the group
        app._load_articles("test.general")
        await pilot.pause()

        # Select the article row
        table = app.query_one("#articles-table")
        table.move_cursor(row=0)
        table.action_select_cursor()
        await pilot.pause()

        reader = app.query_one("#reader-content")
        assert "Alice" in reader.content
        assert "Article body text here" in reader.content


@pytest.mark.asyncio
async def test_post_key_opens_compose(mock_node):
    """Pressing 'p' should open the compose screen."""
    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        await pilot.press("p")
        await pilot.pause()
        assert isinstance(app.screen, ComposeScreen)


@pytest.mark.asyncio
async def test_compose_screen_escape(mock_node):
    """Pressing escape on compose screen should return to main."""
    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        await pilot.press("p")
        await pilot.pause()
        assert isinstance(app.screen, ComposeScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, ComposeScreen)


@pytest.mark.asyncio
async def test_sync_action(mock_node):
    """Pressing 's' should trigger sync_all_peers."""
    mock_node.sync_all_peers.return_value = 0

    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        await pilot.press("s")
        await pilot.pause()
        mock_node.sync_all_peers.assert_called_once()


@pytest.mark.asyncio
async def test_announce_action(mock_node):
    """Pressing 'a' should trigger announce."""
    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        await pilot.press("a")
        await pilot.pause()
        mock_node.announce.assert_called_once()


@pytest.mark.asyncio
async def test_reply_opens_prefilled_compose(mock_node):
    """Pressing 'R' with a selected article opens ComposeScreen with pre-filled fields."""
    mid = _insert_article(
        mock_node.store, "test.general", "Hello world",
        author="Alice", body="Original post", msg_id="root123"
    )

    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        app._load_articles("test.general")
        await pilot.pause()

        table = app.query_one("#articles-table")
        table.move_cursor(row=0)
        table.action_select_cursor()
        await pilot.pause()

        await pilot.press("R")
        await pilot.pause()
        assert isinstance(app.screen, ComposeScreen)

        ng_input = app.screen.query_one("#newsgroup-input")
        subj_input = app.screen.query_one("#subject-input")
        body_input = app.screen.query_one("#body-input")
        assert ng_input.value == "test.general"
        assert subj_input.value == "Re: Hello world"
        assert ng_input.disabled is True
        assert app.screen._reply_references == ["root123"]
        assert "> Original post" in body_input.text
        assert "Alice wrote:" in body_input.text


@pytest.mark.asyncio
async def test_reply_no_article_selected(mock_node):
    """Pressing 'R' with no article selected should not open compose."""
    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        await pilot.press("R")
        await pilot.pause()
        assert not isinstance(app.screen, ComposeScreen)


@pytest.mark.asyncio
async def test_threaded_articles_display(mock_node):
    """Articles with references should display with thread indentation."""
    root_id = _insert_article(
        mock_node.store, "test.general", "Root post",
        msg_id="root1", author="Alice"
    )
    time.sleep(0.01)  # ensure ordering
    reply_id = _insert_article(
        mock_node.store, "test.general", "Re: Root post",
        msg_id="reply1", author="Bob", references=["root1"]
    )

    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        app._load_articles("test.general")
        await pilot.pause()

        table = app.query_one("#articles-table")
        assert table.row_count == 2
        # The reply should be indented with └
        assert app._article_ids[0] == "root1"
        assert app._article_ids[1] == "reply1"


@pytest.mark.asyncio
async def test_reader_shows_references(mock_node):
    """Reader pane should show references when present."""
    _insert_article(
        mock_node.store, "test.general", "Re: Hello",
        msg_id="reply1", author="Bob", body="A reply",
        references=["root123"]
    )

    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        app._load_articles("test.general")
        await pilot.pause()

        table = app.query_one("#articles-table")
        table.move_cursor(row=0)
        table.action_select_cursor()
        await pilot.pause()

        reader = app.query_one("#reader-content")
        assert "Refs:" in reader.content
        assert "root123" in reader.content


@pytest.mark.asyncio
async def test_filter_key_opens_filter_screen(mock_node):
    """Pressing 'f' should open the filter screen."""
    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        await pilot.press("f")
        await pilot.pause()
        assert isinstance(app.screen, FilterScreen)


@pytest.mark.asyncio
async def test_filter_screen_displays_filters(mock_node):
    """FilterScreen should display existing filters."""
    mock_node.filter_store.add_filter("author", "blacklist", "spammer")
    mock_node.filter_store.add_filter("word", "whitelist", "python")

    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        await pilot.press("f")
        await pilot.pause()
        assert isinstance(app.screen, FilterScreen)

        table = app.screen.query_one("#filter-table")
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_filter_screen_escape(mock_node):
    """Pressing escape on filter screen should return to main."""
    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        await pilot.press("f")
        await pilot.pause()
        assert isinstance(app.screen, FilterScreen)

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, FilterScreen)


@pytest.mark.asyncio
async def test_filter_screen_add_opens_form(mock_node):
    """Pressing 'a' on FilterScreen should open AddFilterScreen."""
    app = NewsnetApp(mock_node)
    async with app.run_test() as pilot:
        await pilot.press("f")
        await pilot.pause()
        assert isinstance(app.screen, FilterScreen)

        await pilot.press("a")
        await pilot.pause()
        assert isinstance(app.screen, AddFilterScreen)
