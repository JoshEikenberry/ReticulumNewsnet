"""TUI frontend for reticulum-newsnet using Textual."""

from __future__ import annotations

import json
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Select,
    Static,
    TextArea,
)


def _build_thread_order(articles: list[dict]) -> list[tuple[dict, int]]:
    """Sort articles into threaded display order with indent depth.

    Returns list of (article_dict, depth) tuples.
    """
    by_id = {a["message_id"]: a for a in articles}
    children: dict[str | None, list[str]] = {None: []}
    for a in articles:
        children.setdefault(a["message_id"], [])

    for a in articles:
        refs_raw = a.get("references") or "[]"
        if isinstance(refs_raw, str):
            refs = json.loads(refs_raw)
        else:
            refs = refs_raw
        # Use the last reference as the direct parent
        parent = refs[-1] if refs else None
        # Only thread under parent if parent is in this group's article set
        if parent and parent in by_id:
            children.setdefault(parent, []).append(a["message_id"])
        else:
            children[None].append(a["message_id"])

    result: list[tuple[dict, int]] = []

    def walk(mid: str, depth: int):
        if mid in by_id:
            result.append((by_id[mid], depth))
            for child_id in children.get(mid, []):
                walk(child_id, depth + 1)

    for root_id in children.get(None, []):
        walk(root_id, 0)

    return result


class ComposeScreen(Screen):
    """Screen for composing a new article."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        reply_newsgroup: str = "",
        reply_subject: str = "",
        reply_references: list[str] | None = None,
        quoted_text: str = "",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._reply_newsgroup = reply_newsgroup
        self._reply_subject = reply_subject
        self._reply_references = reply_references or []
        self._quoted_text = quoted_text

    def compose(self) -> ComposeResult:
        title = "Reply" if self._reply_references else "Compose New Article"
        yield Header(show_clock=False)
        yield Label(title, id="compose-title")
        yield Label("Newsgroup:")
        yield Input(placeholder="e.g. test.general", id="newsgroup-input")
        yield Label("Subject:")
        yield Input(placeholder="Article subject", id="subject-input")
        yield Label("Body:")
        yield TextArea(id="body-input")
        yield Static("[Enter] in subject to jump to body | [Ctrl+S] to post | [Escape] to cancel", id="compose-help")
        yield Footer()

    def on_mount(self) -> None:
        ng_input = self.query_one("#newsgroup-input", Input)
        subj_input = self.query_one("#subject-input", Input)

        if self._reply_newsgroup:
            ng_input.value = self._reply_newsgroup
            ng_input.disabled = True
            subj_input.value = self._reply_subject
            if self._quoted_text:
                self.query_one("#body-input", TextArea).text = self._quoted_text
            subj_input.focus()
        else:
            ng_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "newsgroup-input":
            self.query_one("#subject-input", Input).focus()
        elif event.input.id == "subject-input":
            self.query_one("#body-input", TextArea).focus()

    def key_ctrl_s(self) -> None:
        newsgroup = self.query_one("#newsgroup-input", Input).value.strip()
        subject = self.query_one("#subject-input", Input).value.strip()
        body = self.query_one("#body-input", TextArea).text.strip()

        if not newsgroup or not subject:
            self.notify("Newsgroup and subject are required", severity="error")
            return

        node = self.app._node
        node.post(newsgroup, subject, body, self._reply_references)
        self.notify(f"Posted to {newsgroup}")
        self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.pop_screen()


class AddFilterScreen(Screen):
    """Screen for adding a new filter."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Label("Add Filter", id="filter-form-title")
        yield Label("Type:")
        yield Select(
            [("Author", "author"), ("Newsgroup", "newsgroup"), ("Word", "word")],
            id="filter-type-select",
            value="author",
        )
        yield Label("Mode:")
        yield Select(
            [("Block", "blacklist"), ("Allow", "whitelist")],
            id="filter-mode-select",
            value="blacklist",
        )
        yield Label("Pattern:")
        yield Input(placeholder="e.g. spammer123 or spam.*", id="filter-pattern-input")
        yield Static("[Ctrl+S] to save | [Escape] to cancel", id="filter-form-help")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#filter-pattern-input", Input).focus()

    def key_ctrl_s(self) -> None:
        filter_type = self.query_one("#filter-type-select", Select).value
        filter_mode = self.query_one("#filter-mode-select", Select).value
        pattern = self.query_one("#filter-pattern-input", Input).value.strip()

        if not pattern:
            self.notify("Pattern is required", severity="error")
            return

        self.app._node.filter_store.add_filter(filter_type, filter_mode, pattern)
        self.notify(f"Added {filter_mode} {filter_type} filter: {pattern}")
        self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.pop_screen()


class FilterScreen(Screen):
    """Screen for viewing and managing filters."""

    BINDINGS = [
        Binding("a", "add_filter", "Add"),
        Binding("d", "delete_filter", "Delete"),
        Binding("delete", "delete_filter", "Delete"),
        Binding("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Label("Filters", id="filter-title")
        yield DataTable(id="filter-table")
        yield Static("[a] Add | [d/Delete] Remove | [Escape] Back", id="filter-help")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#filter-table", DataTable)
        table.add_columns("Type", "Mode", "Pattern")
        table.cursor_type = "row"
        self._load_filters()

    def _load_filters(self) -> None:
        table = self.query_one("#filter-table", DataTable)
        table.clear()
        self._filters = self.app._node.filter_store.list_filters()
        for f in self._filters:
            table.add_row(f["filter_type"], f["filter_mode"], f["pattern"])

    def on_screen_resume(self) -> None:
        self._load_filters()

    def action_add_filter(self) -> None:
        self.app.push_screen(AddFilterScreen())

    def action_delete_filter(self) -> None:
        table = self.query_one("#filter-table", DataTable)
        if not self._filters:
            return
        row_index = table.cursor_row
        if 0 <= row_index < len(self._filters):
            f = self._filters[row_index]
            self.app._node.filter_store.remove_filter(f["filter_type"], f["pattern"])
            self.notify(f"Removed {f['filter_type']} filter: {f['pattern']}")
            self._load_filters()

    def action_go_back(self) -> None:
        self.app.pop_screen()


class NewsnetApp(App):
    """Newsnet TUI - P2P threaded discussions on Reticulum."""

    CSS_PATH = "app.tcss"
    TITLE = "Newsnet"
    SUB_TITLE = "Reticulum P2P News"

    BINDINGS = [
        Binding("p", "post", "Post"),
        Binding("R", "reply", "Reply"),
        Binding("s", "do_sync", "Sync"),
        Binding("a", "do_announce", "Announce"),
        Binding("f", "filters", "Filters"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, node, **kwargs):
        super().__init__(**kwargs)
        self._node = node
        self._current_group: str | None = None
        self._article_ids: list[str] = []
        self._selected_article_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-panels"):
            yield ListView(id="groups-list")
            yield DataTable(id="articles-table")
        yield VerticalScroll(Static("Select a group and article to read.", id="reader-content"), id="reader")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#articles-table", DataTable)
        table.add_columns("Author", "Subject", "Date")
        table.cursor_type = "row"
        self._load_groups()
        self.set_interval(5, self._refresh_data)

    def _load_groups(self) -> None:
        groups_list = self.query_one("#groups-list", ListView)
        groups_list.clear()
        groups = self._node.store.list_newsgroups()
        for group in groups:
            groups_list.append(ListItem(Label(group), name=group))

    def _load_articles(self, newsgroup: str) -> None:
        self._current_group = newsgroup
        table = self.query_one("#articles-table", DataTable)
        table.clear()
        self._article_ids = []

        articles = self._node.store.list_articles(newsgroup=newsgroup)
        threaded = _build_thread_order(articles)
        for a, depth in threaded:
            ts = datetime.fromtimestamp(a["timestamp"]).strftime("%H:%M")
            name = a["display_name"][:12]
            indent = "  " * depth + ("└ " if depth > 0 else "")
            table.add_row(name, indent + a["subject"], ts)
            self._article_ids.append(a["message_id"])

    def _show_article(self, message_id: str) -> None:
        article = self._node.store.get_article(message_id)
        if article is None:
            return

        self._selected_article_id = message_id

        ts = datetime.fromtimestamp(article["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
        refs_raw = article.get("references") or "[]"
        if isinstance(refs_raw, str):
            refs = json.loads(refs_raw)
        else:
            refs = refs_raw

        lines = [
            f"From:    {article['display_name']} ({article['author_hash'][:16]}...)",
            f"Date:    {ts}",
            f"Group:   {article['newsgroup']}",
            f"Subject: {article['subject']}",
        ]
        if refs:
            refs_display = ", ".join(r[:12] + "..." for r in refs)
            lines.append(f"Refs:    {refs_display}")
        lines.append("─" * 50)
        lines.append("")
        lines.append(article["body"])

        reader = self.query_one("#reader-content", Static)
        reader.update("\n".join(lines))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if item.name:
            self._load_articles(item.name)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_index = event.cursor_row
        if 0 <= row_index < len(self._article_ids):
            self._show_article(self._article_ids[row_index])

    def _refresh_data(self) -> None:
        old_groups = set()
        groups_list = self.query_one("#groups-list", ListView)
        for child in groups_list.children:
            if hasattr(child, "name") and child.name:
                old_groups.add(child.name)

        new_groups = set(self._node.store.list_newsgroups())
        if new_groups != old_groups:
            self._load_groups()

        if self._current_group:
            self._load_articles(self._current_group)

        peers = self._node.store.list_peers()
        self.sub_title = f"peers:{len(peers)}"

    def action_post(self) -> None:
        self.push_screen(ComposeScreen())

    def action_reply(self) -> None:
        if not self._selected_article_id:
            self.notify("Select an article first", severity="warning")
            return

        article = self._node.store.get_article(self._selected_article_id)
        if article is None:
            return

        refs_raw = article.get("references") or "[]"
        if isinstance(refs_raw, str):
            refs = json.loads(refs_raw)
        else:
            refs = refs_raw
        refs = refs + [article["message_id"]]

        subject = article["subject"]
        if not subject.startswith("Re: "):
            subject = f"Re: {subject}"

        ts = datetime.fromtimestamp(article["timestamp"]).strftime("%Y-%m-%d %H:%M")
        quoted_lines = [f"> {line}" for line in article["body"].split("\n")]
        quoted_text = (
            "\n\n"
            f"On {ts}, {article['display_name']} wrote:\n"
            + "\n".join(quoted_lines)
            + "\n"
        )

        self.push_screen(ComposeScreen(
            reply_newsgroup=article["newsgroup"],
            reply_subject=subject,
            reply_references=refs,
            quoted_text=quoted_text,
        ))

    def action_do_sync(self) -> None:
        count = self._node.sync_all_peers()
        if count == 0:
            self.notify("No peers to sync with")
        else:
            self.notify(f"Syncing with {count} peer(s)...")

    def action_do_announce(self) -> None:
        self._node.announce()
        self.notify(f"Announced as {self._node.config.display_name}")

    def action_filters(self) -> None:
        self.push_screen(FilterScreen())

    def action_refresh(self) -> None:
        self._refresh_data()
        self.notify("Refreshed")
