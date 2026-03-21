from __future__ import annotations
import random
from tools.simulate.models import SimulationConfig

_WORDS = [
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
    "india", "juliet", "kilo", "lima", "mike", "november", "oscar", "papa",
    "quebec", "romeo", "sierra", "tango", "uniform", "victor", "whiskey",
    "xray", "yankee", "zulu", "apple", "banana", "cherry", "dragon",
    "elephant", "falcon", "grape", "harbor", "island", "jungle", "kitten",
    "lemon", "mango", "north", "ocean", "purple", "quiet", "river", "silver",
    "tiger", "under", "violet", "winter", "yellow", "zebra", "anchor", "bridge",
    "castle", "desert", "engine", "forest", "garden", "hammer", "igloo",
    "jacket", "kernel", "ladder", "mirror", "needle", "office", "planet",
    "quartz", "rocket", "sunset", "tunnel", "vacuum", "window", "barrel",
    "candle", "dancer", "empire", "flower", "gadget", "hollow", "impact",
    "jigsaw", "kettle", "lantern", "marble", "narrow", "outlaw", "pencil",
    "quarry", "riddle", "shadow", "timber", "vessel", "walnut", "battle",
    "copper", "dollar", "fabric", "gamble", "handle", "insult", "jargon",
    "launch", "magnet", "napkin", "outlaw", "pencil", "quarry", "rabbit",
    "stable", "trophy", "unlock", "vendor", "walnut", "zealot", "absent",
    "beckon", "carbon", "dagger", "famine", "glitch", "hustle", "invent",
    "jostle", "luster", "mortal", "noodle", "onward", "pardon", "quantum",
    "ramble", "squire", "torque", "update", "velvet", "wander", "bonnet",
    "cobalt", "debris", "frenzy", "gossip", "hurdle", "influx", "jaunty",
    "karate", "lavish", "muffin", "osprey", "ponder", "radish", "turnip",
    "upbeat", "warren", "cactus", "donkey", "finger", "gravel", "hatch",
]


class ArticleGenerator:
    def __init__(self, config: SimulationConfig):
        self._groups = config.newsgroup_names()
        self._weights = config.effective_weights()
        self._body_min = config.body_words_min
        self._body_max = config.body_words_max
        self._thread_prob = config.thread_prob

    def generate(self, existing_articles: list[dict]) -> tuple[str, str, str, list[str]]:
        """Return (newsgroup, subject, body, references).

        existing_articles: list of dicts with at least 'message_id' key.
        """
        newsgroup = random.choices(self._groups, weights=self._weights, k=1)[0]
        subject = " ".join(random.choices(_WORDS, k=random.randint(3, 8)))
        word_count = random.randint(self._body_min, self._body_max)
        words = random.choices(_WORDS, k=word_count)
        # Break into sentences of 8-15 words
        sentences = []
        i = 0
        while i < len(words):
            chunk_size = random.randint(8, 15)
            chunk = words[i:i + chunk_size]
            sentences.append(" ".join(chunk).capitalize() + ".")
            i += chunk_size
        body = " ".join(sentences)

        references: list[str] = []
        if self._thread_prob > 0 and existing_articles and random.random() < self._thread_prob:
            parent = random.choice(existing_articles)
            references = [parent["message_id"]]

        return newsgroup, subject, body, references
