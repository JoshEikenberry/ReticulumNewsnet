import pytest

from newsnet.filters import FilterEngine, TextFilterStore


@pytest.fixture
def filter_store(tmp_path):
    store = TextFilterStore(tmp_path)
    store.ensure_files()
    return store


def test_text_filter_store_ensure_files(tmp_path):
    store = TextFilterStore(tmp_path)
    store.ensure_files()
    assert (tmp_path / "authors.txt").exists()
    assert (tmp_path / "newsgroups.txt").exists()
    assert (tmp_path / "words.txt").exists()


def test_text_filter_store_add_and_list(filter_store):
    filter_store.add_filter("author", "blacklist", "spammer123")
    filter_store.add_filter("word", "whitelist", "python")
    filters = filter_store.list_filters()
    assert len(filters) == 2
    assert filters[0] == {"filter_type": "author", "filter_mode": "blacklist", "pattern": "spammer123"}
    assert filters[1] == {"filter_type": "word", "filter_mode": "whitelist", "pattern": "python"}


def test_text_filter_store_list_by_type(filter_store):
    filter_store.add_filter("author", "blacklist", "bad1")
    filter_store.add_filter("word", "blacklist", "spam")
    assert len(filter_store.list_filters_by_type("author")) == 1
    assert len(filter_store.list_filters_by_type("word")) == 1


def test_text_filter_store_remove(filter_store):
    filter_store.add_filter("author", "blacklist", "bad1")
    filter_store.add_filter("author", "whitelist", "friend1")
    filter_store.remove_filter("author", "bad1")
    filters = filter_store.list_filters_by_type("author")
    assert len(filters) == 1
    assert filters[0]["pattern"] == "friend1"


def test_text_filter_store_comments_and_blanks(tmp_path):
    """Comments and blank lines should be preserved and ignored during parsing."""
    store = TextFilterStore(tmp_path)
    authors = tmp_path / "authors.txt"
    authors.write_text("# A comment\n\nblock:spammer\n\n# Another comment\nallow:friend\n")
    filters = store.list_filters_by_type("author")
    assert len(filters) == 2
    assert filters[0] == {"filter_type": "author", "filter_mode": "blacklist", "pattern": "spammer"}
    assert filters[1] == {"filter_type": "author", "filter_mode": "whitelist", "pattern": "friend"}


def test_text_filter_store_default_block(tmp_path):
    """Lines without a prefix default to block mode."""
    store = TextFilterStore(tmp_path)
    words = tmp_path / "words.txt"
    words.write_text("spam\n")
    filters = store.list_filters_by_type("word")
    assert len(filters) == 1
    assert filters[0]["filter_mode"] == "blacklist"
    assert filters[0]["pattern"] == "spam"


def test_text_filter_store_remove_preserves_comments(tmp_path):
    """Removing a filter should preserve comments and other entries."""
    store = TextFilterStore(tmp_path)
    authors = tmp_path / "authors.txt"
    authors.write_text("# Header\nblock:bad1\nallow:friend\nblock:bad2\n")
    store.remove_filter("author", "bad1")
    content = authors.read_text()
    assert "# Header" in content
    assert "bad1" not in content
    assert "friend" in content
    assert "bad2" in content


def make_article_dict(**overrides):
    base = {
        "author_hash": "author_aaa",
        "newsgroup": "test.general",
        "subject": "Test Subject",
        "body": "Test body content",
    }
    base.update(overrides)
    return base


def test_no_filters_passes_everything():
    engine = FilterEngine([])
    article = make_article_dict()
    assert engine.should_keep(article) is True


def test_author_blacklist():
    filters = [{"filter_type": "author", "filter_mode": "blacklist", "pattern": "bad_author"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(author_hash="bad_author")) is False
    assert engine.should_keep(make_article_dict(author_hash="good_author")) is True


def test_author_whitelist():
    filters = [{"filter_type": "author", "filter_mode": "whitelist", "pattern": "friend1"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(author_hash="friend1")) is True
    assert engine.should_keep(make_article_dict(author_hash="stranger")) is False


def test_newsgroup_blacklist():
    filters = [{"filter_type": "newsgroup", "filter_mode": "blacklist", "pattern": "spam.ads"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(newsgroup="spam.ads")) is False
    assert engine.should_keep(make_article_dict(newsgroup="tech.linux")) is True


def test_newsgroup_blacklist_glob():
    filters = [{"filter_type": "newsgroup", "filter_mode": "blacklist", "pattern": "spam.*"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(newsgroup="spam.ads")) is False
    assert engine.should_keep(make_article_dict(newsgroup="spam.scam.pills")) is False
    assert engine.should_keep(make_article_dict(newsgroup="tech.linux")) is True


def test_newsgroup_whitelist_glob():
    filters = [{"filter_type": "newsgroup", "filter_mode": "whitelist", "pattern": "tech.*"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(newsgroup="tech.linux")) is True
    assert engine.should_keep(make_article_dict(newsgroup="music.jazz")) is False


def test_word_blacklist_in_body():
    filters = [{"filter_type": "word", "filter_mode": "blacklist", "pattern": "viagra"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(body="Buy cheap viagra now!")) is False
    assert engine.should_keep(make_article_dict(body="A normal post")) is True


def test_word_blacklist_in_subject():
    filters = [{"filter_type": "word", "filter_mode": "blacklist", "pattern": "viagra"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(subject="Viagra deals")) is False


def test_word_blacklist_case_insensitive():
    filters = [{"filter_type": "word", "filter_mode": "blacklist", "pattern": "SPAM"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(body="This is spam")) is False
    assert engine.should_keep(make_article_dict(body="This is Spam")) is False


def test_word_whitelist():
    filters = [{"filter_type": "word", "filter_mode": "whitelist", "pattern": "python"}]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(body="I love python")) is True
    assert engine.should_keep(make_article_dict(body="I love javascript")) is False


def test_whitelist_priority_over_blacklist():
    filters = [
        {"filter_type": "author", "filter_mode": "whitelist", "pattern": "friend1"},
        {"filter_type": "author", "filter_mode": "blacklist", "pattern": "friend1"},
    ]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(author_hash="friend1")) is True


def test_combined_filters():
    filters = [
        {"filter_type": "newsgroup", "filter_mode": "whitelist", "pattern": "tech.*"},
        {"filter_type": "word", "filter_mode": "blacklist", "pattern": "spam"},
    ]
    engine = FilterEngine(filters)
    assert engine.should_keep(make_article_dict(newsgroup="tech.linux", body="Good stuff")) is True
    assert engine.should_keep(make_article_dict(newsgroup="tech.linux", body="Buy spam")) is False
    assert engine.should_keep(make_article_dict(newsgroup="music.jazz", body="Good stuff")) is False
