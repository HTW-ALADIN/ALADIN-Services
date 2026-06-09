# Fermentation Model - FermentALADIN

Last Change: 06.03.2026

This is the backend code of the FermentALADIN Fermentation model.

!WICHTIG! An der Main (main.py) bitte nicht herumschrauben – Erweiterungen/Änderungen ausschließlich über die Adapter und die CLI-Parameter (Util/argparser.py). Sonst haut das mit der Schnittstelle zu ALADIN nicht hin.

## Usage

Main.py uses a command line interface for controlling its inputs and outputs

USAGE

```sh
uv run main.py -i [Input-Type = stdin|file|excel] -p [file-path] -o[Output-type= df|Chart] optional: -f [output filename] -h
```

Input-type (zum Auslesen der User-Inputparameter der Modellierung)

* stdin - Standardmethode einlesen der Daten aus der Kommandozeile#
* file - zum Auslesen aus einer JSON Datei
* excel - zum direkten Auslesen aus der Datei "./test/Bioreaktor_forPy.xlsx"

OUTPUT Adapter

* df - Schreiben als Dataframe 
* Chart - als Chart.Js 

Output 

* Standardmethode (ohne Angabe von Parametern) ist stdout
* -f = file - zum Schreiben in eine Datei

Help

-h - displays an explanation about usage

Example

```sh
uv run src/main.py -i file -p ./test/test_data/user_input.json -o df -f ausgabe.json
```

This reads the model parameters from file ./test/test_data/user_input.json and creates a file ausgabe.json in a Dataframe format

Example for usage with Excel as GUI

```sh
uv run src/main.py -i excel -p ./test/Bioreactor_forPy.xlsx -o df -f ausgabe.json
```

This reads the model parameters from file ./test/Bioreactor_forPy.xlsx and creates a file ausgabe.json in a Dataframe format

### Usage inside Docker

The Docker image uses a multi-stage build and does not include `uv`. Instead, the virtual environment is already activated via `PATH`, so you run `python` directly instead of `uv run`:

```sh
# local
uv run src/main.py -i excel -p input.xlsx -o df -f ausgabe.json

# inside Docker
python src/main.py -i excel -p input.xlsx -o df -f ausgabe.json
```

Example with `docker run`:

```sh
docker run --rm fermentaladin-service python src/main.py -i file -p ./test/test_data/user_input.json -o df -f ausgabe.json
```

## Architecture

### Input

The models parameters are read (depending on the CLI switch) from 

* from Excel-file, 
* STDIN or 
* JSON file) 

and passed to main.py. 

The model constants are stored in the file ".\src\DataModels\model_db.json". Updating of this model "database" is done from the excel file. 

Output: als dataframe in JSON oder als Chart.js dump

All calculation source code is stored in folder „src/calc“.

### Modelldatenbank aktualisieren:

Die Synchronisation der Excel mit der „Model-Datenbank" (src\DataModels\model_db.json) ist als Utility implementiert (src\Util\sync_excel_models_to_json_file.py) und sollte gezielt ausgeführt werden 

### Plotten der Ergebnisse in Python

Um die Modellergebnisse in Python zu Plotten, liegt unter Util "src\Util\multiplot_ferm.py". Der Aufruf ist in der Main auskommentiert. Zum Testen kann man es wieder einkommentieren oder einfach in nen Test-Case auslagern.

### Use of Interfaces

To reduce the coupling of the current variable naming of the input-format and the models to the code that performs the calculation, the DataModels may be used. If the name of a variable changes (e.g. in the input-format) only the name of the right hand side of the respective enum has to be adapted. If a new variables is introduced, it should be added to the DataModels as well.
TODO: Adapt for string values in Fx_ODE_Bioreaktor.py as well.



## Installing new packages

To install new packages run

```sh
uv pip install [package]
```

where `[package]` should be replaced with the name of the package you want to install.

## Developing and running tests

To ensure the functionality of the code, create unit tests that determine whether the expected result is returned. New tests should be put into the `test`-directory and include `test` in their filename. Multiple tests can be grouped together in one file.

The tests can be executed with the following command:

```sh
uv run pytest
```

Ideally, the tests cover the entirety of the code base. Whether this is the case or not can be checked with:

```sh
uv run pytest --cov=.
```

## DEBUGGING und Programmlog

Statusausgaben sind über über Logger implementiert. Das LOG_LEVEL kann über eine „.env“-Datei im Wurzelverzeichnis des Repositories gesteuert werden – Default bei Nicht-Setzung ist „INFO“. Es ist gute Praxis die .env-Datei nicht zu versionieren, da diese ggf. auch Geheimnisse enthalten kann, die nicht öffentlich im Git stehen sollen. D. h. die musst du dir einmal manuell anlegen. Die „.demo.env“ ist nur zur Doku der vorhandenen Variablen.

## HTTP API

The service exposes a FastAPI HTTP server (`src/api.py`). By default it runs on port **8000**.

### Starting the server

```sh
uv run uvicorn src.api:app --reload
```

The interactive OpenAPI docs are then available at `http://localhost:8000/docs`.

---

### Endpoints

#### `GET /health`

Liveness probe.

**Response** `200 OK`
```json
{"status": "ok"}
```

---

#### `GET /models`

Returns the complete organism model database. Each key is a model ID string.

**Response** `200 OK` — JSON object keyed by model ID:
```json
{
  "1": { "Mikroorganismus": "S.cerevisiae", "Substrat 1": "Glucose", "Produkt": "Ethanol", ... },
  "2": { "Mikroorganismus": "E.coli", ... },
  "3": { "Mikroorganismus": "E.coli Biomass", ... },
  "4": { "Mikroorganismus": "Cupriavidus necator", "Substrat 1": "Fructose", "Produkt": "PHB", ... }
}
```

| Model ID | Organism | Substrate | Product |
|---|---|---|---|
| `"1"` | *S. cerevisiae* | Glucose | Ethanol |
| `"2"` | *E. coli* | Glucose | *(none, theoretical)* |
| `"3"` | *E. coli* Biomass | C-source | *(none, pure biomass)* |
| `"4"` | *Cupriavidus necator* | Fructose | PHB |

---

#### `POST /simulate/df`

Runs the ODE-based multi-phase fermentation simulation and returns the result as **raw time-series data** in column-keyed JSON (`pandas DataFrame.to_json()` format).

**Request body** — JSON array of phase objects (see [Phase schema](#phase-schema) below).

**Response** `200 OK`
```json
{
  "t":      {"0": 0.0, "1": 0.1, ...},
  "c_x":    {"0": 0.1, "1": 0.11, ...},
  "c_s1":   {"0": 100.0, ...},
  ...
}
```

Each key is a result column; values are objects mapping row index (string) to numeric value.

---

#### `POST /simulate/chart`

Same simulation as `/simulate/df`, but returns **Chart.js-ready descriptors** for four charts.

**Request body** — same phase array as `/simulate/df`.

**Response** `200 OK`
```json
{
  "Chart_1": { ... },
  "Chart_2": { ... },
  "Chart_3": { ... },
  "Chart_4": { ... }
}
```

| Chart | Contents |
|---|---|
| `Chart_1` | Substrate concentrations (S1, S2, cumulative feed) |
| `Chart_2` | Aeration parameters (pressure, aeration rate, stirrer speed, dissolved O₂) |
| `Chart_3` | Products and volume (biomass, product concentration, liquid volume) |
| `Chart_4` | Off-gas analysis (OUR, RQ) |

---

### Phase schema

The request body for both `/simulate/df` and `/simulate/chart` is a **JSON array** where each element represents one fermentation phase.

| Field | Type | Required | Description |
|---|---|---|---|
| `Phase` | int | Yes | Phase index (1-based) |
| `Model` | string | **Phase 1 only** | Organism model ID (`"1"`–`"4"`) |
| `DO` | float | **Phase 1 only** | Dissolved oxygen at phase start [% saturation] |
| `c_x0` | float | **Phase 1 only** | Initial biomass concentration [g/L] |
| `Q_Air` | float | Yes | Air flow rate [NL/min] |
| `Bolus_C` | float | Yes | Carbon substrate bolus at phase start [g/L] |
| `Feed_C` | float | Yes | Carbon substrate feed rate [g/(L·h)] |
| `Bolus_N` | float | Yes | Nitrogen substrate bolus at phase start [g/L] |
| `Feed_N` | float | No | Nitrogen substrate feed rate (currently unused) |
| `Drehzahl` | float | Yes | Stirrer speed [rpm] |
| `Druck` | float | Yes | Overpressure [barg] |
| `Dauer` | float | Yes | Phase duration [h] |
| `V_L` | float | Yes | Liquid volume [L] |
| `T` | float | Yes | Temperature [°C] |
| `pH` | float | Yes | pH value |
| `Dichte` | float | No | Density (currently unused) |
| `Q_in` | float | No | Inflow rate (currently unused) |
| `Q_Out` | float | No | Outflow rate (currently unused) |

Phases 2–N **inherit** the dissolved-oxygen and biomass end-state from the previous phase. `Model`, `DO`, and `c_x0` are ignored if provided in those phases.

**Example — single phase (Model 1, S. cerevisiae):**
```json
[
  {
    "Model": "1",
    "Phase": 1,
    "Q_Air": 80.0,
    "Bolus_C": 100.0,
    "Feed_C": 0.0,
    "Bolus_N": 5.0,
    "Drehzahl": 500.0,
    "Druck": 0.0,
    "Dauer": 10.0,
    "V_L": 100.0,
    "T": 30.0,
    "pH": 6.5,
    "DO": 100.0,
    "c_x0": 0.1
  }
]
```

---

### Error responses

| HTTP status | Cause |
|---|---|
| `422 Unprocessable Entity` | Missing required field (`Model`, `DO`, or `c_x0` in phase 1); empty phases array; invalid field type |
| `500 Internal Server Error` | Simulation failure or missing model database |

---

### Manual HTTP tests

Ready-to-use `.http` test files (compatible with VS Code REST Client and JetBrains HTTP Client) are located in `http-tests/`:

| File | Covers |
|---|---|
| `http-tests/health.http` | `GET /health` |
| `http-tests/models.http` | `GET /models` |
| `http-tests/simulate.http` | `POST /simulate/df` and `POST /simulate/chart` — happy-path and error cases |

The variable `@baseUrl = http://localhost:8000` at the top of each file can be overridden with an environment file if needed.

---

## REMARKS

Output Adapter DF: funktioniert nicht zum Anzeigen der JSON Datei im Browser da Value Pairs erzeugt werden und kein JSON Array
