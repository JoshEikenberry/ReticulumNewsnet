from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass

import umsgpack


@dataclass
class Article:
    message_id: str
    author_hash: str
    author_key: bytes
    display_name: str
    newsgroup: str
    subject: str
    body: str
    references: list[str]
    timestamp: float
    signature: bytes

    @staticmethod
    def compute_message_id(
        newsgroup: str, subject: str, body: str, author_hash: str, timestamp: float
    ) -> str:
        canonical = (
            newsgroup + "\n" + subject + "\n" + body + "\n"
            + author_hash + "\n" + str(timestamp)
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def create(
        cls,
        identity,
        display_name: str,
        newsgroup: str,
        subject: str,
        body: str,
        references: list[str],
        timestamp: float | None = None,
    ) -> Article:
        ts = timestamp if timestamp is not None else time.time()
        author_hash = identity.hash.hex()
        message_id = cls.compute_message_id(newsgroup, subject, body, author_hash, ts)
        signature = identity.sign(message_id.encode("utf-8"))
        return cls(
            message_id=message_id,
            author_hash=author_hash,
            author_key=identity.get_public_key(),
            display_name=display_name,
            newsgroup=newsgroup,
            subject=subject,
            body=body,
            references=references,
            timestamp=ts,
            signature=signature,
        )

    def verify(self, identity) -> bool:
        expected_id = self.compute_message_id(
            self.newsgroup, self.subject, self.body, self.author_hash, self.timestamp
        )
        if expected_id != self.message_id:
            return False
        return identity.validate(self.signature, self.message_id.encode("utf-8"))

    def serialize(self) -> bytes:
        return umsgpack.packb({
            "message_id": self.message_id,
            "author_hash": self.author_hash,
            "author_key": self.author_key,
            "display_name": self.display_name,
            "newsgroup": self.newsgroup,
            "subject": self.subject,
            "body": self.body,
            "references": self.references,
            "timestamp": self.timestamp,
            "signature": self.signature,
        })

    @classmethod
    def deserialize(cls, data: bytes) -> Article:
        d = umsgpack.unpackb(data)
        return cls(
            message_id=d["message_id"],
            author_hash=d["author_hash"],
            author_key=d["author_key"],
            display_name=d["display_name"],
            newsgroup=d["newsgroup"],
            subject=d["subject"],
            body=d["body"],
            references=d["references"],
            timestamp=d["timestamp"],
            signature=d["signature"],
        )

    def to_store_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "author_hash": self.author_hash,
            "author_key": self.author_key,
            "display_name": self.display_name,
            "newsgroup": self.newsgroup,
            "subject": self.subject,
            "body": self.body,
            "references": json.dumps(self.references),
            "timestamp": self.timestamp,
            "signature": self.signature,
            "received_at": time.time(),
        }
