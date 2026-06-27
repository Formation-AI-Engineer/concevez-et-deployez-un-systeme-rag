"""Tests des métriques d'évaluation locales (étape 4.4).

Vérifie les fonctions **pures** (sans LLM ni réseau) : normalisation / Exact Match, couverture
des infos clés, classification correcte/partielle/incorrecte, et agrégation du rapport. La
similarité sémantique (qui charge le modèle d'embeddings) est testée à part, et ignorée si le
modèle n'est pas disponible.
"""

from __future__ import annotations

import pytest

from scripts.evaluate_rag import (
    PairResult,
    build_summary,
    classify,
    exact_match,
    key_info_coverage,
)


# --- Exact Match / normalisation -----------------------------------------------

def test_exact_match_ignore_casse_accents_ponctuation():
    assert exact_match("Concert de JAZZ !", "concert de jazz")
    assert not exact_match("concert de jazz", "exposition de peinture")


# --- Couverture des infos clés -------------------------------------------------

def test_couverture_totale_quand_tous_les_titres_sont_cites():
    reponse = "Je recommande le Festival Jazzycolors et le Concert de la Saint-Jean."
    titres = ["Jazzycolors - Festival de jazz international", "CONCERT DE LA SAINT-JEAN"]
    assert key_info_coverage(reponse, titres) == 1.0


def test_couverture_partielle():
    reponse = "Il y a le Festival Jazzycolors cette semaine."
    titres = ["Jazzycolors - Festival de jazz international", "CONCERT DE LA SAINT-JEAN"]
    assert key_info_coverage(reponse, titres) == 0.5


def test_couverture_vide_non_penalisante():
    """Sans titre attendu (question hors-périmètre), la couverture vaut 1 (neutre)."""
    assert key_info_coverage("Je n'ai rien trouvé.", []) == 1.0


# --- Classification ------------------------------------------------------------

def test_classify_correcte_demande_sens_et_infos():
    assert classify(0.85, 0.8, has_expected=True) == "correcte"
    # bon sens mais infos manquantes -> seulement partielle
    assert classify(0.85, 0.0, has_expected=True) == "partielle"


def test_classify_partielle_et_incorrecte():
    assert classify(0.55, 0.0, has_expected=True) == "partielle"
    assert classify(0.20, 0.0, has_expected=True) == "incorrecte"


def test_classify_refus_juge_sur_le_sens_seul():
    """Cas hors-périmètre : pas d'infos attendues, on classe sur la similarité au refus."""
    assert classify(0.90, 0.0, has_expected=False) == "correcte"
    assert classify(0.30, 0.0, has_expected=False) == "incorrecte"


# --- Agrégation du rapport -----------------------------------------------------

def _res(id_, cat, sim, cov, cls, em=False):
    return PairResult(
        id=id_, category=cat, question="q", reference_answer="r", generated_answer="g",
        retrieved_uids=[1], semantic_similarity=sim, exact_match=em,
        key_info_coverage=cov, classification=cls,
    )


def test_build_summary_agrege_classes_et_categories():
    results = [
        _res("a", "type_evenement", 0.9, 1.0, "correcte"),
        _res("b", "type_evenement", 0.6, 0.5, "partielle"),
        _res("c", "hors_perimetre", 0.2, 1.0, "incorrecte"),
    ]
    s = build_summary(results)
    assert s["n_questions"] == 3
    assert s["classification"] == {"correcte": 1, "partielle": 1, "incorrecte": 1}
    assert s["par_categorie"]["type_evenement"]["n"] == 2
    assert s["par_categorie"]["type_evenement"]["taux_correctes"] == 0.5
    # moyenne de similarité globale = (0.9 + 0.6 + 0.2) / 3
    assert s["similarite_semantique_moyenne"] == pytest.approx(0.5667, abs=1e-3)


# --- Similarité sémantique (nécessite le modèle d'embeddings) -------------------

def test_similarite_semantique_textes_proches_vs_eloignes():
    from rag.embeddings import get_embeddings
    from scripts.evaluate_rag import semantic_similarity

    try:
        emb = get_embeddings()
        emb.embed_query("warmup")
    except Exception as exc:  # pragma: no cover - dépend du cache HF / réseau
        pytest.skip(f"Modèle d'embeddings indisponible : {exc}")

    proche = semantic_similarity(
        "Un concert de jazz a lieu ce soir à Paris.",
        "Ce soir, il y a un concert de jazz dans Paris.",
        emb,
    )
    eloigne = semantic_similarity(
        "Un concert de jazz a lieu ce soir à Paris.",
        "Comment réparer un moteur diesel.",
        emb,
    )
    assert proche > eloigne
    assert proche > 0.7
