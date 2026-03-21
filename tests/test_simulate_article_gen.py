# tests/test_simulate_article_gen.py
from tools.simulate.article_gen import ArticleGenerator
from tools.simulate.models import SimulationConfig


def test_generate_returns_tuple():
    cfg = SimulationConfig(newsgroups=2, body_words_min=5, body_words_max=10, thread_prob=0.0)
    gen = ArticleGenerator(cfg)
    newsgroup, subject, body, references = gen.generate([])
    assert isinstance(newsgroup, str)
    assert isinstance(subject, str)
    assert isinstance(body, str)
    assert references == []


def test_generate_newsgroup_is_valid():
    cfg = SimulationConfig(newsgroups=3)
    gen = ArticleGenerator(cfg)
    valid = cfg.newsgroup_names()
    for _ in range(20):
        newsgroup, _, _, _ = gen.generate([])
        assert newsgroup in valid


def test_generate_body_length_within_range():
    cfg = SimulationConfig(body_words_min=10, body_words_max=20, thread_prob=0.0)
    gen = ArticleGenerator(cfg)
    for _ in range(10):
        _, _, body, _ = gen.generate([])
        word_count = len(body.split())
        assert 10 <= word_count <= 20, f"body had {word_count} words"


def test_generate_root_post_when_no_existing():
    cfg = SimulationConfig(thread_prob=1.0)  # always reply if possible
    gen = ArticleGenerator(cfg)
    _, _, _, refs = gen.generate([])  # no existing articles
    assert refs == []  # can't reply to nothing


def test_generate_reply_when_thread_prob_one():
    cfg = SimulationConfig(thread_prob=1.0)
    gen = ArticleGenerator(cfg)
    existing = [{"message_id": "mid-abc", "newsgroup": "sim.group-0"}]
    _, _, _, refs = gen.generate(existing)
    assert refs == ["mid-abc"]


def test_generate_no_reply_when_thread_prob_zero():
    cfg = SimulationConfig(thread_prob=0.0)
    gen = ArticleGenerator(cfg)
    existing = [{"message_id": "mid-abc", "newsgroup": "sim.group-0"}]
    _, _, _, refs = gen.generate(existing)
    assert refs == []


def test_weighted_newsgroup_distribution():
    """Heavy weight on group-0 should mean it appears much more often."""
    cfg = SimulationConfig(newsgroups=2, group_weights=[100.0, 1.0], thread_prob=0.0)
    gen = ArticleGenerator(cfg)
    results = [gen.generate([])[0] for _ in range(200)]
    group0_count = results.count("sim.group-0")
    assert group0_count > 150, f"expected >150 hits for group-0, got {group0_count}"
