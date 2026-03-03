from newsnet.filters import FilterEngine


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
