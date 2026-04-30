import logging
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ValidationError

from src.comparison.base import JsonComparator                      # Interface
# from src.comparison.comparator_dummy import DummyComparator       # Platzhalter-Implementierung
from src.comparison.comparator_default import DefaultComparator     # Echte Implementierung
from src.comparison.results import ComparisonResult                 # Pydantic-Modell für die Vergleichsergebnisse

from src.feedback.feedback_builder_default import DefaultFeedbackBuilder   

from src.diagrams.erd.models import Graph


# ---------------------------------------------------------------------------
#   Logging
#   Ausgaben landen in "docker compose logs"
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
log = logging.getLogger("vergleicher")



# ---------------------------------------------------------------------------
#   Request-/Response-Schemata mit Pydantic
#   FastAPI nutzt diese automatisch für die Validierung und Dokumentation.
# ---------------------------------------------------------------------------

class CompareRequest(BaseModel):
    reference: Any  # Musterlösung
    candidate: Any  # zu prüfende Einreichung



# ---------------------------------------------------------------------------
# Strategy Pattern, hier die Implementierung des Vergleichers wechseln
# ---------------------------------------------------------------------------

def get_comparator() -> JsonComparator:
    # return DummyComparator()
    return DefaultComparator()

def get_feedback_builder() -> DefaultFeedbackBuilder:
    return DefaultFeedbackBuilder()


# ---------------------------------------------------------------------------
# Pipeline-Schritte
# ---------------------------------------------------------------------------

# def validate(reference: Any, candidate: Any) -> None:
#    """Optionale Vorprüfung die bei einem Problem eine Exception wirft (= Abbruch)."""
#    log.info("validate - Skip (nicht implementiert)")

def validate_input(reference: Any, candidate: Any) -> tuple[Graph, Graph]:
    """
    Parst beide Eingaben gegen das erd.v1-Schema.
    Wirft pydantic.ValidationError bei Schema-Verletzung.
    Die Exception wird im Endpoint in einen HTTP 422 umgewandelt.
    """
    log.info("Validiere")
    ref_graph = Graph.model_validate(reference)
    cand_graph = Graph.model_validate(candidate)
    return ref_graph, cand_graph



def normalize_graphs(reference: Any, candidate: Any) -> tuple[Any, Any]:
    """Normalisierung"""
    log.info("Normalisiere")
    return reference, candidate


def compare_graphs(reference: Any, candidate: Any) -> ComparisonResult:
    """Holt den aktiven Comparator und führt den Vergleich aus."""
    log.info("Vergleiche")
    return get_comparator().compare(reference, candidate)


def build_final_feedback(result: ComparisonResult) -> ComparisonResult:
    log.info("Erstelle Feedback")
    result.feedback = get_feedback_builder().build(result)
    return result



# Pipeline-Funktion, die die Schritte in der richtigen Reihenfolge aufruft.
def run_comparison_pipeline(reference: Any, candidate: Any) -> ComparisonResult:
    log.info("Pipeline gestartet")

    try:
        # Validierung
        ref_graph, cand_graph = validate_input(reference, candidate)
            
        # Normalisierung
        ref_norm, cand_norm = normalize_graphs(ref_graph, cand_graph)
            
        # Vergleich
        comparison_result = compare_graphs(ref_norm, cand_norm)
            
        # Feedback-Anreicherung
        final_result = build_final_feedback(comparison_result)
            
    except ValidationError as exc:
        log.warning("Validierungsfehler in der Pipeline")
        return ComparisonResult(
            match=False,
            feedback=["Die Eingabe entspricht nicht dem erwarteten Format.", str(exc)],
            limitations=["Wegen ungültiger Eingabedaten kein Vergleich durchgeführt."]
        )
    except Exception as e:
        log.error(f"Unerwarteter Fehler: {e}")
        raise # Re-raise damit FastAPI 500 wirft, falls es kein Schema-Fehler ist

    log.info("Pipeline erfolgreich beendet, Match=%s", final_result.match)
    return final_result



# ---------------------------------------------------------------------------
# FastAPI App
# TODO: Decorations besser verstehen.
# ---------------------------------------------------------------------------
app = FastAPI(title="JSON-Vergleicher", version="0.0.0")


@app.get("/health")
def health() -> dict:
    """Healthcheck, zum Testen ob der Container überhaupt läuft."""
    return {"status": "ok"}


@app.post("/compare", response_model=ComparisonResult)
def post_compare(req: CompareRequest) -> ComparisonResult:
    return run_comparison_pipeline(req.reference, req.candidate)



# ---------------------------------------------------------------------------
#   Python-Standard-Idiom:
#   Dieser Block laeuft NUR, wenn die Datei direkt gestartet wird.
#   Beim Import (z.B. in Tests) wird er uebersprungen.
# ---------------------------------------------------------------------------

# if __name__ == "__main__":
#    main()
