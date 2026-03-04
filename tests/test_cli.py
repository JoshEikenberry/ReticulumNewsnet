from cli.main import build_parser


def test_parser_post():
    parser = build_parser()
    args = parser.parse_args(["post", "test.general", "--subject", "Hello"])
    assert args.command == "post"
    assert args.newsgroup == "test.general"
    assert args.subject == "Hello"


def test_parser_list():
    parser = build_parser()
    args = parser.parse_args(["list", "test.general"])
    assert args.command == "list"
    assert args.newsgroup == "test.general"


def test_parser_list_all():
    parser = build_parser()
    args = parser.parse_args(["list"])
    assert args.command == "list"
    assert args.newsgroup is None


def test_parser_read():
    parser = build_parser()
    args = parser.parse_args(["read", "abc123"])
    assert args.command == "read"
    assert args.message_id == "abc123"


def test_parser_groups():
    parser = build_parser()
    args = parser.parse_args(["groups"])
    assert args.command == "groups"


def test_parser_peers():
    parser = build_parser()
    args = parser.parse_args(["peers"])
    assert args.command == "peers"


def test_parser_identity():
    parser = build_parser()
    args = parser.parse_args(["identity"])
    assert args.command == "identity"


def test_parser_sync():
    parser = build_parser()
    args = parser.parse_args(["sync"])
    assert args.command == "sync"


def test_parser_filter_add_blacklist():
    parser = build_parser()
    args = parser.parse_args(["filter", "add", "--blacklist", "--author", "bad_hash"])
    assert args.filter_command == "add"
    assert args.blacklist is True
    assert args.author == "bad_hash"


def test_parser_filter_add_whitelist_group():
    parser = build_parser()
    args = parser.parse_args(["filter", "add", "--whitelist", "--group", "tech.*"])
    assert args.filter_command == "add"
    assert args.whitelist is True
    assert args.group == "tech.*"


def test_parser_filter_list():
    parser = build_parser()
    args = parser.parse_args(["filter", "list"])
    assert args.filter_command == "list"


def test_parser_filter_remove():
    parser = build_parser()
    args = parser.parse_args(["filter", "remove", "5"])
    assert args.filter_command == "remove"
    assert args.filter_id == 5
