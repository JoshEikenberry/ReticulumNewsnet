from __future__ import annotations

import argparse
import sys
import json
from datetime import datetime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="newsnet",
        description="Reticulum-Newsnet: P2P threaded discussions",
    )
    parser.add_argument(
        "--config-dir", "-d", default=None,
        help="Custom config directory (for running multiple instances)",
    )
    sub = parser.add_subparsers(dest="command")

    # post
    post_p = sub.add_parser("post", help="Post an article")
    post_p.add_argument("newsgroup", help="Newsgroup to post to")
    post_p.add_argument("--subject", "-s", required=True, help="Article subject")

    # read
    read_p = sub.add_parser("read", help="Read an article")
    read_p.add_argument("message_id", help="Message ID to read")

    # list
    list_p = sub.add_parser("list", help="List articles")
    list_p.add_argument("newsgroup", nargs="?", default=None, help="Filter by newsgroup")

    # groups
    sub.add_parser("groups", help="List known newsgroups")

    # sync
    sub.add_parser("sync", help="Trigger sync with all peers")

    # announce
    sub.add_parser("announce", help="Announce presence to the network")

    # peers
    sub.add_parser("peers", help="List known peers")

    # identity
    sub.add_parser("identity", help="Show your identity")

    # tui
    sub.add_parser("tui", help="Launch interactive TUI")

    # filter
    filter_p = sub.add_parser("filter", help="Manage filters")
    filter_sub = filter_p.add_subparsers(dest="filter_command")

    filter_add = filter_sub.add_parser("add", help="Add a filter")
    filter_add.add_argument("--blacklist", action="store_true")
    filter_add.add_argument("--whitelist", action="store_true")
    filter_add.add_argument("--author", default=None, help="Author identity hash")
    filter_add.add_argument("--group", default=None, help="Newsgroup pattern")
    filter_add.add_argument("--word", default=None, help="Word to filter")

    filter_sub.add_parser("list", help="List filters")

    filter_rm = filter_sub.add_parser("remove", help="Remove a filter")
    filter_rm.add_argument("filter_id", type=int, help="Filter ID to remove")

    return parser


def cmd_post(node, args):
    print("Enter article body (Ctrl+D to finish):")
    body = sys.stdin.read()
    article = node.post(args.newsgroup, args.subject, body.rstrip("\n"), [])
    print(f"Posted: {article.message_id}")


def cmd_read(node, args):
    article = node.store.get_article(args.message_id)
    if article is None:
        print(f"Article not found: {args.message_id}")
        return
    ts = datetime.fromtimestamp(article["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
    print(f"Newsgroup: {article['newsgroup']}")
    print(f"From:      {article['display_name']} ({article['author_hash'][:16]}...)")
    print(f"Date:      {ts}")
    print(f"Subject:   {article['subject']}")
    print(f"ID:        {article['message_id']}")
    refs = json.loads(article["references"]) if article["references"] else []
    if refs:
        print(f"Refs:      {', '.join(refs)}")
    print()
    print(article["body"])


def cmd_list(node, args):
    articles = node.store.list_articles(newsgroup=args.newsgroup)
    if not articles:
        print("No articles found.")
        return
    for a in articles:
        ts = datetime.fromtimestamp(a["timestamp"]).strftime("%Y-%m-%d %H:%M")
        print(f"  {a['message_id'][:12]}  {ts}  {a['newsgroup']:20s}  {a['display_name']:12s}  {a['subject']}")


def cmd_groups(node, args):
    groups = node.store.list_newsgroups()
    if not groups:
        print("No newsgroups found.")
        return
    for g in groups:
        print(f"  {g}")


def cmd_peers(node, args):
    peers = node.store.list_peers()
    if not peers:
        print("No peers found.")
        return
    for p in peers:
        last = datetime.fromtimestamp(p["last_seen"]).strftime("%Y-%m-%d %H:%M") if p["last_seen"] else "never"
        synced = datetime.fromtimestamp(p["last_synced"]).strftime("%Y-%m-%d %H:%M") if p["last_synced"] else "never"
        name = p["display_name"] or "(unknown)"
        print(f"  {p['destination_hash'][:16]}  {name:16s}  seen: {last}  synced: {synced}")


def cmd_identity(node, args):
    print(f"Identity: {node._identity_mgr.hash_hex}")
    print(f"Display:  {node.config.display_name}")


def cmd_filter(node, args):
    if args.filter_command == "add":
        mode = "whitelist" if args.whitelist else "blacklist"
        if args.author:
            ftype, pattern = "author", args.author
        elif args.group:
            ftype, pattern = "newsgroup", args.group
        elif args.word:
            ftype, pattern = "word", args.word
        else:
            print("Specify --author, --group, or --word")
            return
        fid = node.store.add_filter(ftype, mode, pattern)
        print(f"Filter added (id={fid}): {mode} {ftype} '{pattern}'")

    elif args.filter_command == "list":
        filters = node.store.list_filters()
        if not filters:
            print("No filters configured.")
            return
        for f in filters:
            print(f"  [{f['id']}] {f['filter_mode']:10s} {f['filter_type']:10s} {f['pattern']}")

    elif args.filter_command == "remove":
        node.store.remove_filter(args.filter_id)
        print(f"Filter {args.filter_id} removed.")


def cmd_sync(node, args):
    node.announce()
    count = node.sync_all_peers()
    if count == 0:
        print("No peers to sync with.")
    else:
        print(f"Sync initiated with {count} peer(s). Waiting for transfers...")
        import time
        time.sleep(5)
        print("Sync complete.")


def cmd_announce(node, args):
    node.announce()
    print(f"Announced as {node.config.display_name}")


def cmd_tui(node, args):
    from tui.app import NewsnetApp
    app = NewsnetApp(node)
    app.run()


COMMANDS = {
    "post": cmd_post,
    "read": cmd_read,
    "list": cmd_list,
    "groups": cmd_groups,
    "peers": cmd_peers,
    "identity": cmd_identity,
    "filter": cmd_filter,
    "sync": lambda node, args: cmd_sync(node, args),
    "announce": lambda node, args: cmd_announce(node, args),
    "tui": lambda node, args: cmd_tui(node, args),
}


def main():
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    from newsnet.config import NewsnetConfig
    from newsnet.node import Node

    base_config = NewsnetConfig(config_dir_override=args.config_dir)
    config_path = base_config.config_file_path
    if config_path.exists():
        config = NewsnetConfig.from_file(config_path)
        config.config_dir_override = args.config_dir
    else:
        config = base_config

    node = Node(config)
    node.start()

    try:
        COMMANDS[args.command](node, args)
    finally:
        node.shutdown()


if __name__ == "__main__":
    main()
