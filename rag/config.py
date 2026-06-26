"""Configuration centralisée du projet RAG.

Charge les variables d'environnement depuis ``.env.local`` (prioritaire, non versionné)
puis ``.env`` en repli, et les expose via un objet ``settings`` typé et réutilisable
(API, scripts, tests). Aucune clé d'API n'est jamais codée en dur ni versionnée.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Racine du projet (…/Projet 7) : ce fichier est dans rag/.
ROOT_DIR = Path(__file__).resolve().parent.parent

# .env.local prioritaire (secrets locaux), puis .env en repli. override=False :
# une variable déjà définie dans l'environnement réel (CI, Docker) n'est pas écrasée.
for _env_file in (".env.local", ".env"):
    _path = ROOT_DIR / _env_file
    if _path.exists():
        load_dotenv(_path, override=False)


def _get(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


@dataclass(frozen=True)
class Settings:
    # --- Secrets ---
    mistral_api_key: str | None = _get("MISTRAL_API_KEY")
    openagenda_api_key: str | None = _get("OPENAGENDA_API_KEY")

    # --- Modèles ---
    mistral_model: str = _get("MISTRAL_MODEL", "mistral-small-latest")
    embedding_model: str = _get(
        "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    # --- Périmètre des données ---
    events_city: str = _get("EVENTS_CITY", "Paris")
    events_months_back: int = int(_get("EVENTS_MONTHS_BACK", "12"))

    # --- Chemins (résolus en absolu depuis la racine) ---
    raw_data_path: Path = ROOT_DIR / _get("RAW_DATA_PATH", "data/raw/events.json")
    processed_data_path: Path = ROOT_DIR / _get("PROCESSED_DATA_PATH", "data/processed/events.parquet")
    vectorstore_dir: Path = ROOT_DIR / _get("VECTORSTORE_DIR", "vectorstore/index")

    # --- Paramètres RAG ---
    chunk_size: int = int(_get("CHUNK_SIZE", "800"))
    chunk_overlap: int = int(_get("CHUNK_OVERLAP", "100"))
    top_k: int = int(_get("TOP_K", "4"))
    # Seuil de distance (cosinus) au-delà duquel un document récupéré est jugé non pertinent
    # et écarté du contexte. Calibré empiriquement : requêtes culturelles ~0.4–0.8,
    # requêtes hors-périmètre ~1.0+. Au-delà du seuil pour tous les docs → réponse honnête
    # « aucun événement correspondant » sans appeler le LLM.
    relevance_threshold: float = float(_get("RELEVANCE_THRESHOLD", "0.9"))

    log_level: str = _get("LOG_LEVEL", "INFO")

    def require_mistral_key(self) -> str:
        if not self.mistral_api_key:
            raise RuntimeError("MISTRAL_API_KEY manquante (définir dans .env.local ou .env).")
        return self.mistral_api_key

    def require_openagenda_key(self) -> str:
        if not self.openagenda_api_key:
            raise RuntimeError("OPENAGENDA_API_KEY manquante (définir dans .env.local ou .env).")
        return self.openagenda_api_key


settings = Settings()
