"""
FermentALADIN FastAPI server.

Exposes the bioreactor fermentation simulation as an HTTP API.  The CLI
(src/main.py) remains unchanged; this module wires directly into the same
calculation and adapter layer.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from calc.calc_bioreactor import calculate
from OutputAdapter.chart_js_adapter import ChartJSAdapter
from OutputAdapter.df_adapter import DFAdapter

logging.basicConfig(level=os.environ.get("LOG_LEVEL") or logging.INFO)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FermentALADIN",
    description=(
        "Bioreactor fermentation simulation API. "
        "Simulates multi-phase fermentation using ODE-based kinetic models "
        "and returns either raw time-series data or Chart.js-ready descriptors."
    ),
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

_MODEL_DB_PATH = pathlib.Path(__file__).parent / "DataModels" / "model_db.json"


class FermentationPhase(BaseModel):
    """Parameters for a single fermentation phase.

    For phase 1, ``DO`` and ``c_x0`` are required.
    Subsequent phases inherit the dissolved-oxygen and biomass state from the
    previous phase; ``DO`` and ``c_x0`` are ignored if provided.
    """

    Model: str | None = Field(
        default=None,
        description="Organism model ID (1–4). Required for phase 1; ignored for subsequent phases.",
        examples=["1"],
    )
    Phase: int = Field(description="Phase index (1-based).", examples=[1])
    Q_Air: float = Field(description="Air flow rate [NL/min].", examples=[80.0])
    Bolus_C: float = Field(description="Carbon substrate bolus at phase start [g/L].", examples=[100.0])
    Feed_C: float = Field(description="Carbon substrate feed rate [g/(L·h)].", examples=[0.0])
    Bolus_N: float = Field(description="Nitrogen substrate bolus at phase start [g/L].", examples=[5.0])
    Feed_N: float | None = Field(default=None, description="Nitrogen substrate feed rate (currently unused).")
    Drehzahl: float = Field(description="Stirrer speed [rpm].", examples=[500.0])
    Druck: float = Field(description="Overpressure [barg].", examples=[0.0])
    Dauer: float = Field(description="Phase duration [h].", examples=[10.0])
    V_L: float = Field(description="Liquid volume [L].", examples=[100.0])
    T: float = Field(description="Temperature [°C].", examples=[30.0])
    pH: float = Field(description="pH value.", examples=[6.5])
    DO: float | None = Field(
        default=None,
        description="Dissolved oxygen at phase start [% saturation]. Required for phase 1.",
        examples=[100.0],
    )
    Dichte: float | None = Field(default=None, description="Density (currently unused).")
    c_x0: float | None = Field(
        default=None,
        description="Initial biomass concentration [g/L]. Required for phase 1.",
        examples=[0.1],
    )
    Q_in: float | None = Field(default=None, description="Inflow rate (currently unused).")
    Q_Out: float | None = Field(default=None, description="Outflow rate (currently unused).")


class HealthResponse(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _phases_to_dataframe(phases: list[FermentationPhase]) -> pd.DataFrame:
    """Convert a list of FermentationPhase Pydantic models to the DataFrame
    format expected by ``calculate()``."""
    return pd.DataFrame([phase.model_dump() for phase in phases])


def _run_simulation(phases: list[FermentationPhase]) -> pd.DataFrame:
    """Validate inputs and run the ODE simulation, raising HTTPException on error."""
    if not phases:
        raise HTTPException(status_code=422, detail="At least one fermentation phase is required.")

    phase_1 = phases[0]
    if phase_1.Model is None:
        raise HTTPException(status_code=422, detail="'Model' is required for phase 1.")
    if phase_1.DO is None:
        raise HTTPException(status_code=422, detail="'DO' (dissolved oxygen) is required for phase 1.")
    if phase_1.c_x0 is None:
        raise HTTPException(status_code=422, detail="'c_x0' (initial biomass) is required for phase 1.")

    input_df = _phases_to_dataframe(phases)

    try:
        return calculate(input_df)
    except FileNotFoundError as exc:
        logging.error("model_db.json not found: %s", exc)
        raise HTTPException(status_code=500, detail="Internal error: model database not found.") from exc
    except Exception as exc:
        logging.error("Simulation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Simulation failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="ok")


@app.get(
    "/models",
    response_model=dict[str, Any],
    tags=["Models"],
    summary="List available organism models",
    description=(
        "Returns the full contents of the model database. "
        "Each key is a model ID string (e.g. '1'), and the value contains "
        "the kinetic parameters and organism metadata."
    ),
)
def get_models() -> dict[str, Any]:
    """Return all organism models from the model database."""
    try:
        with _MODEL_DB_PATH.open() as f:
            return json.load(f)
    except FileNotFoundError as exc:
        logging.error("model_db.json not found: %s", exc)
        raise HTTPException(status_code=500, detail="Internal error: model database not found.") from exc


@app.post(
    "/simulate/df",
    response_model=dict[str, Any],
    tags=["Simulation"],
    summary="Simulate fermentation — DataFrame output",
    description=(
        "Runs the ODE-based multi-phase fermentation simulation and returns the "
        "result as a column-keyed JSON object (pandas ``DataFrame.to_json()`` format). "
        "Each key is a result column name; the value is an object mapping row index to value.\n\n"
        "**Phase 1 requirements:** `Model`, `DO`, and `c_x0` must be provided."
    ),
)
def simulate_df(phases: list[FermentationPhase]) -> dict[str, Any]:
    """Run the simulation and return raw time-series data."""
    result_df = _run_simulation(phases)
    adapter = DFAdapter()
    return json.loads(adapter.serialize(adapter.transform_data(result_df)))


@app.post(
    "/simulate/chart",
    response_model=dict[str, Any],
    tags=["Simulation"],
    summary="Simulate fermentation — Chart.js output",
    description=(
        "Runs the ODE-based multi-phase fermentation simulation and returns the "
        "result as four Chart.js-ready chart descriptors (`Chart_1` … `Chart_4`):\n\n"
        "- **Chart_1** — Substrate concentrations (S1, S2, cumulative feed)\n"
        "- **Chart_2** — Aeration parameters (pressure, aeration rate, stirrer speed, dissolved O₂)\n"
        "- **Chart_3** — Products and volume (biomass, product concentration, liquid volume)\n"
        "- **Chart_4** — Off-gas analysis (OUR, RQ)\n\n"
        "**Phase 1 requirements:** `Model`, `DO`, and `c_x0` must be provided."
    ),
)
def simulate_chart(phases: list[FermentationPhase]) -> dict[str, Any]:
    """Run the simulation and return Chart.js chart descriptors."""
    result_df = _run_simulation(phases)
    adapter = ChartJSAdapter()
    return json.loads(adapter.serialize(adapter.transform_data(result_df)))
