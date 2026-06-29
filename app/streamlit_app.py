"""Interface web Streamlit pour l'assistant RAG d'événements culturels (Puls-Events).

UI conversationnelle légère : elle interroge l'**API REST FastAPI** (``POST /ask``, ``GET /health``)
et n'embarque **aucune logique RAG ni modèle** — toute l'intelligence vit côté API. On respecte
ainsi la séparation métier / présentation, et l'UI démarre instantanément.

Lancement (l'API doit tourner par ailleurs) :
    # 1. l'API (local ou conteneur Docker)
    uv run uvicorn api.main:app            # → http://127.0.0.1:8000
    # 2. l'interface
    uv run --extra ui streamlit run app/streamlit_app.py

L'URL de l'API est configurable via la variable d'environnement ``RAG_API_URL`` ou la barre latérale.
"""

from __future__ import annotations

import html
import os

import requests
import streamlit as st

API_URL = os.getenv("RAG_API_URL", "http://127.0.0.1:8000").rstrip("/")
ASK_TIMEOUT = 90  # la génération Mistral peut prendre quelques secondes
HEALTH_TIMEOUT = 5

NAVY = "#0F2F52"
AMBER = "#F59E0B"

EXAMPLES = [
    "Quels concerts de jazz puis-je voir à Paris ?",
    "Une expo de peinture à voir à Paris ?",
    "Y a-t-il des spectacles pour enfants ?",
    "Que faire pour la Fête de la musique ?",
]

st.set_page_config(
    page_title="Assistant culturel — Puls-Events",
    page_icon="🎭",
    layout="centered",
    initial_sidebar_state="expanded",
)

# --- Charte graphique (navy / ambre, cohérente avec la présentation) -------------------------
st.markdown(
    f"""
    <style>
      #MainMenu, footer {{visibility: hidden;}}
      .block-container {{padding-top: 2.2rem; max-width: 820px;}}
      .hero {{
        background: linear-gradient(135deg, {NAVY} 0%, #1b4a7e 100%);
        border-radius: 16px; padding: 26px 32px; margin-bottom: 18px;
        box-shadow: 0 6px 20px rgba(15,47,82,.18);
      }}
      .hero-kicker {{color: {AMBER}; font-weight: 700; letter-spacing: 1.5px; font-size: .78rem;}}
      .hero-title {{color: #fff; font-size: 1.75rem; font-weight: 800; margin-top: 6px; line-height: 1.2;}}
      .hero-sub {{color: #cdd7e3; margin-top: 8px; font-size: .96rem;}}
      .src-card {{
        border: 1px solid #E5E7EB; border-left: 4px solid {AMBER}; border-radius: 10px;
        padding: 10px 14px; margin: 8px 0; background: #F9FAFB;
      }}
      .src-title {{font-weight: 700; color: {NAVY}; font-size: .95rem;}}
      .src-meta {{color: #6B7280; font-size: .84rem; margin-top: 2px;}}
      .src-card a {{color: {AMBER}; text-decoration: none; font-size: .84rem; font-weight: 600;}}
      .stButton button {{border-radius: 10px; text-align: left;}}
    </style>
    """,
    unsafe_allow_html=True,
)


def fetch_health(base_url: str) -> tuple[dict | None, str | None]:
    """Interroge ``GET /health`` ; renvoie ``(payload, erreur)``."""
    try:
        resp = requests.get(f"{base_url}/health", timeout=HEALTH_TIMEOUT)
        resp.raise_for_status()
        return resp.json(), None
    except requests.RequestException as exc:
        return None, str(exc)


def ask_api(base_url: str, question: str) -> dict:
    """Appelle ``POST /ask`` et renvoie la réponse JSON (lève une exception parlante sinon)."""
    resp = requests.post(f"{base_url}/ask", json={"question": question}, timeout=ASK_TIMEOUT)
    if resp.status_code == 422:
        raise ValueError("Question invalide (vide ou trop longue).")
    if resp.status_code == 503:
        raise RuntimeError("Assistant indisponible côté API (index non chargé ?).")
    resp.raise_for_status()
    return resp.json()


def render_sources(sources: list[dict]) -> None:
    """Affiche les événements sources sous forme de cartes dans un volet repliable."""
    if not sources:
        return
    with st.expander(f"📍 Sources ({len(sources)})", expanded=False):
        for src in sources:
            title = html.escape(str(src.get("title") or "Événement"))
            meta_bits = [src.get("date"), src.get("location")]
            meta = html.escape(" · ".join(b for b in meta_bits if b))
            url = src.get("url")
            link = (
                f"<a href='{html.escape(url)}' target='_blank'>Voir l'événement ↗</a>" if url else ""
            )
            st.markdown(
                f"<div class='src-card'><div class='src-title'>{title}</div>"
                f"<div class='src-meta'>{meta}</div>{link}</div>",
                unsafe_allow_html=True,
            )


# --- État de session --------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "api_url" not in st.session_state:
    st.session_state.api_url = API_URL

# --- Barre latérale ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.session_state.api_url = st.text_input(
        "URL de l'API", value=st.session_state.api_url
    ).rstrip("/")

    health, err = fetch_health(st.session_state.api_url)
    if health and health.get("status") == "ok":
        st.success(f"API en ligne · {health.get('indexed_events', '?')} événements indexés")
    elif health:
        st.warning("API en mode dégradé (index absent). Construisez l'index puis rechargez.")
    else:
        st.error("API injoignable. Démarrez l'API puis rechargez la page.")
        st.caption(f"Détail : {err}")

    st.markdown("### 💡 Exemples de questions")
    for example in EXAMPLES:
        if st.button(example, use_container_width=True, key=f"ex_{example}"):
            st.session_state.pending = example

    st.divider()
    if st.button("🗑️ Effacer la conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.caption("Interface branchée sur l'API REST · Puls-Events (POC RAG)")

# --- En-tête ----------------------------------------------------------------------------------
st.markdown(
    "<div class='hero'>"
    "<div class='hero-kicker'>PULS-EVENTS · ASSISTANT CULTUREL</div>"
    "<div class='hero-title'>Quels événements pour vous aujourd'hui&nbsp;?</div>"
    "<div class='hero-sub'>Posez une question en langage naturel — concerts, expositions, "
    "spectacles à Paris. Les réponses s'appuient sur de vrais événements, avec leurs sources.</div>"
    "</div>",
    unsafe_allow_html=True,
)

# --- Historique de conversation ---------------------------------------------------------------
for message in st.session_state.messages:
    avatar = "🧑" if message["role"] == "user" else "🎭"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])
        render_sources(message.get("sources", []))

# --- Nouvelle question (saisie libre ou exemple cliqué) ---------------------------------------
prompt = st.chat_input("Posez votre question sur les événements culturels…")
prompt = prompt or st.session_state.pop("pending", None)

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🎭"):
        try:
            with st.spinner("Recherche dans les événements…"):
                data = ask_api(st.session_state.api_url, prompt)
            answer = data.get("answer", "")
            sources = data.get("sources", [])
            st.markdown(answer)
            render_sources(sources)
            st.session_state.messages.append(
                {"role": "assistant", "content": answer, "sources": sources}
            )
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            error_msg = f"⚠️ Désolé, une erreur est survenue : {exc}"
            st.error(error_msg)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_msg, "sources": []}
            )
