"""Tests fonctionnels de l'API REST (étape 5.4).

Hermétiques : l'assistant RAG est **mocké** (aucun index réel, aucun appel Mistral), via
l'injection de dépendances FastAPI. On ne déclenche pas le `lifespan` (pas de `with TestClient`)
pour éviter le chargement du vrai modèle au démarrage ; l'état est piloté à la main.
"""

from __future__ import annotations

import types

import pytest
from fastapi.testclient import TestClient

import api.main as main
from api.main import app, get_assistant


class _FakeDoc:
    def __init__(self, metadata: dict):
        self.metadata = metadata
        self.page_content = "Description de l'événement."


class _FakeAnswer:
    def __init__(self, question, answer, sources):
        self.question = question
        self.answer = answer
        self.sources = sources


class FakeAssistant:
    """Doublure d'assistant : réponse fixe, ou exception pour simuler une panne LLM."""

    def __init__(self, answer="Voici un concert de jazz à Paris.", sources=None, raises=False):
        self._answer = answer
        self._sources = sources if sources is not None else [
            _FakeDoc({"uid": 1, "title": "Festival Jazzycolors", "date_range": "octobre",
                      "location_name": "Le Sunset", "city": "Paris", "url": "https://x"})
        ]
        self._raises = raises
        self.vectorstore = types.SimpleNamespace(index=types.SimpleNamespace(ntotal=1500))

    def answer(self, question: str):
        if self._raises:
            raise RuntimeError("LLM indisponible")
        return _FakeAnswer(question, self._answer, self._sources)


@pytest.fixture
def client():
    """Client de test ; nettoie les overrides et l'état après chaque test."""
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()
    app.state.assistant = None


def _use_assistant(fake):
    app.dependency_overrides[get_assistant] = lambda: fake


# --- Service -------------------------------------------------------------------

def test_racine_redirige_vers_swagger(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (307, 302)
    assert r.headers["location"] == "/docs"


def test_health_degraded_sans_assistant(client):
    app.state.assistant = None
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["assistant_ready"] is False


def test_health_ok_avec_assistant(client):
    app.state.assistant = FakeAssistant()
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["assistant_ready"] is True
    assert body["indexed_events"] == 1500


# --- /ask ----------------------------------------------------------------------

def test_ask_question_valide(client):
    _use_assistant(FakeAssistant())
    r = client.post("/ask", json={"question": "Quels concerts de jazz à Paris ?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"]
    assert body["sources"][0]["title"] == "Festival Jazzycolors"
    assert body["sources"][0]["location"] == "Le Sunset Paris"


def test_ask_dedoublonne_les_sources_par_uid(client):
    """Deux chunks du même événement (même uid) → une seule source ; lieu sans répétition."""
    sources = [
        _FakeDoc({"uid": 7, "title": "Concert", "date_range": "juin",
                  "location_name": "Paris", "city": "Paris", "url": "https://a"}),
        _FakeDoc({"uid": 7, "title": "Concert", "date_range": "juin",
                  "location_name": "Paris", "city": "Paris", "url": "https://a"}),
    ]
    _use_assistant(FakeAssistant(sources=sources))
    r = client.post("/ask", json={"question": "un concert ?"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["sources"]) == 1
    assert body["sources"][0]["location"] == "Paris"  # pas "Paris Paris"


def test_ask_question_vide_renvoie_422(client):
    _use_assistant(FakeAssistant())
    r = client.post("/ask", json={"question": "   "})
    assert r.status_code == 422


def test_ask_champ_manquant_renvoie_422(client):
    _use_assistant(FakeAssistant())
    r = client.post("/ask", json={})
    assert r.status_code == 422


def test_ask_sans_assistant_renvoie_503(client):
    app.state.assistant = None  # get_assistant non overridé -> lit l'état
    r = client.post("/ask", json={"question": "une question"})
    assert r.status_code == 503


def test_ask_erreur_llm_renvoie_500_sans_fuite(client):
    _use_assistant(FakeAssistant(raises=True))
    r = client.post("/ask", json={"question": "une question"})
    assert r.status_code == 500
    # Le détail interne ("LLM indisponible") ne doit pas fuiter dans la réponse.
    assert "indisponible" not in r.json()["detail"].lower()


# --- /rebuild (protégé) --------------------------------------------------------

def test_rebuild_desactive_si_aucun_jeton(client):
    """Sans jeton configuré côté serveur, l'endpoint est refusé (503)."""
    r = client.post("/rebuild")
    assert r.status_code == 503


def test_rebuild_jeton_manquant_renvoie_401(client, monkeypatch):
    monkeypatch.setattr(main, "settings", types.SimpleNamespace(api_rebuild_token="secret"))
    r = client.post("/rebuild")  # pas d'en-tête
    assert r.status_code == 401


def test_rebuild_jeton_valide(client, monkeypatch):
    monkeypatch.setattr(main, "settings", types.SimpleNamespace(api_rebuild_token="secret"))
    # On mocke la reconstruction lourde (index/embeddings) pour un test rapide.
    import rag.chain
    import rag.vectorstore

    fake_vs = types.SimpleNamespace(index=types.SimpleNamespace(ntotal=1500))
    monkeypatch.setattr(rag.vectorstore, "build_and_save", lambda *a, **k: fake_vs)
    monkeypatch.setattr(rag.vectorstore, "vector_count", lambda vs: vs.index.ntotal)
    monkeypatch.setattr(rag.chain, "RAGAssistant", lambda **k: FakeAssistant())

    r = client.post("/rebuild", headers={"X-API-Token": "secret"})
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "indexed_events": 1500}
