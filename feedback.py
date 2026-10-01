"""Shared PostgreSQL ratings; SQLite is only a local development fallback."""
import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class FeedbackStore:
    def __init__(self, url='', path=None):
        self.url = url
        self.path = str(path) if path else None
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            for sql in [
                '''CREATE TABLE IF NOT EXISTS voice_tests (
                id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, tester TEXT NOT NULL,
                voice TEXT NOT NULL, language TEXT NOT NULL, version TEXT NOT NULL,
                heard INTEGER NOT NULL DEFAULT 0, created_at BIGINT NOT NULL)''',
                '''CREATE TABLE IF NOT EXISTS voice_ratings (
                tester TEXT NOT NULL, voice TEXT NOT NULL, language TEXT NOT NULL,
                version TEXT NOT NULL, test_id TEXT NOT NULL REFERENCES voice_tests(id),
                pronunciation INTEGER NOT NULL CHECK(pronunciation BETWEEN 1 AND 5),
                clarity INTEGER NOT NULL CHECK(clarity BETWEEN 1 AND 5),
                naturalness INTEGER NOT NULL CHECK(naturalness BETWEEN 1 AND 5),
                comment TEXT NOT NULL, updated_at BIGINT NOT NULL,
                PRIMARY KEY(tester, voice, language, version))''',
                '''CREATE TABLE IF NOT EXISTS voice_rating_history (
                id TEXT PRIMARY KEY, test_id TEXT NOT NULL REFERENCES voice_tests(id),
                payload TEXT NOT NULL, created_at BIGINT NOT NULL)''']:
                db.execute(sql)

    @contextmanager
    def connection(self):
        if self.url:
            import psycopg
            db = psycopg.connect(self.url, connect_timeout=10)
        else:
            db = sqlite3.connect(self.path, timeout=10)
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA journal_mode=WAL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def sql(self, text):
        return text.replace('?', '%s') if self.url else text

    def new_test(self, test_id, token, tester, voice, language, version):
        with self.connection() as db:
            db.execute(self.sql('INSERT INTO voice_tests VALUES(?,?,?,?,?,?,0,?)'),
                       (test_id, hashlib.sha256(token.encode()).hexdigest(), tester,
                        voice, language, version, int(time.time())))

    def heard(self, test_id):
        with self.connection() as db:
            db.execute(self.sql('UPDATE voice_tests SET heard=1 WHERE id=?'), (test_id,))

    def rate(self, body):
        if not isinstance(body, dict):
            raise ValueError('Ungültige Bewertung')
        fields = ('pronunciation', 'clarity', 'naturalness')
        if any(type(body.get(k)) is not int or not 1 <= body[k] <= 5 for k in fields):
            raise ValueError('Bitte alle drei Kriterien von 1 bis 5 bewerten')
        comment = body.get('comment', '')
        if not isinstance(comment, str) or len(comment) > 500:
            raise ValueError('Kommentar darf höchstens 500 Zeichen enthalten')
        token = body.get('test_token', '')
        test_id = body.get('test_id', '')
        if not isinstance(token, str) or not isinstance(test_id, str):
            raise ValueError('Ungültiger Test')
        with self.connection() as db:
            row = db.execute(self.sql('SELECT tester,voice,language,version,heard FROM voice_tests WHERE id=? AND token_hash=?'),
                             (test_id, hashlib.sha256(token.encode()).hexdigest())).fetchone()
            if not row or not row[4]:
                raise ValueError('Bewertung erst nach einer gesprochenen Antwort möglich')
            values = (*row[:4], test_id, *(body[k] for k in fields), comment.strip(), int(time.time()))
            db.execute(self.sql('''INSERT INTO voice_ratings VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tester,voice,language,version) DO UPDATE SET
                test_id=excluded.test_id, pronunciation=excluded.pronunciation,
                clarity=excluded.clarity, naturalness=excluded.naturalness,
                comment=excluded.comment, updated_at=excluded.updated_at'''), values)
            db.execute(self.sql('INSERT INTO voice_rating_history VALUES(?,?,?,?)'),
                       (uuid.uuid4().hex, test_id, json.dumps({k: body[k] for k in fields} | {'comment': comment.strip()}), int(time.time())))

    def stats(self, version):
        with self.connection() as db:
            rows = db.execute(self.sql('''SELECT voice,language,COUNT(*),AVG(pronunciation),
                AVG(clarity),AVG(naturalness) FROM voice_ratings WHERE version=?
                GROUP BY voice,language ORDER BY language,AVG(pronunciation) DESC,COUNT(*) DESC,voice'''), (version,)).fetchall()
            total = db.execute(self.sql('SELECT COUNT(DISTINCT tester),COUNT(*) FROM voice_ratings WHERE version=?'), (version,)).fetchone()
        return {'version': version, 'testers': total[0], 'ratings': total[1], 'rows': [
            {'voice': r[0], 'language': r[1], 'testers': r[2], 'pronunciation': round(float(r[3]), 2),
             'clarity': round(float(r[4]), 2), 'naturalness': round(float(r[5]), 2),
             'overall': round(sum(float(x) for x in r[3:6]) / 3, 2)} for r in rows]}

    def versions(self):
        with self.connection() as db:
            return [r[0] for r in db.execute('SELECT version FROM voice_ratings GROUP BY version ORDER BY MAX(updated_at) DESC').fetchall()]
