import json
from typing import ClassVar, Dict, Generic, TypeVar

import pandas as pd

from .base_output_adapter import OutputAdapter

# Type variables representing the generic TS parameters
TType = TypeVar("TType")  # corresponds to ChartType
TData = TypeVar("TData")  # corresponds to DefaultDataPoint<TType>
TLabel = TypeVar("TLabel")  # corresponds to unknown


# Stub for ChartDataset<TType, TData> - see https://www.chartjs.org/docs/latest/general/data-structures.html
class ChartDataset(Generic[TType, TData]):
    pass


class ChartJSAdapter(OutputAdapter):
    __qualname__: ClassVar[str] = "chart"

    def transform_data(self, df: pd.DataFrame) -> Dict[str, ChartDataset]:
        """
        Transforms the calculation-output of the fermentation model into currently 4 charts in the data-format of the Chart.js-library.
        """

        df["Drehzahl"] = df["Drehzahl"] / 10

        hochminus1 = r"\u{207B}\u{00B9}"
        cdot = r"\u{00B7}"
        labelfontsize = 18
        oliv = "#A0C382"
        petrol = "#5F9B8C"
        sun_yellow = "#FAC846"
        orange = "#FF7D2D"

        charts = {}

        charts["Chart_1"] = {
            "type": "line",
            "data": {
                "labels": df["t"].to_list(),
                "datasets": [
                    {
                        "label": "Substrat 1 (S1)",
                        "yAxisID": "yL",
                        "fill": False,
                        "lineTension": 0.2,
                        "pointRadius": 0,
                        "backgroundColor": orange,
                        "borderColor": orange,
                        "data": df["c_S1"].to_list(),
                    },
                    {
                        "label": "Summe Feeding S1",
                        "yAxisID": "yL",
                        "fill": False,
                        "lineTension": 0.2,
                        "pointRadius": 0,
                        "backgroundColor": sun_yellow,
                        "borderColor": sun_yellow,
                        "data": df["Sum_Feed"].to_list(),
                    },
                    {
                        "label": "Substrat 2 (S2)",
                        "yAxisID": "yR",
                        "fill": False,
                        "lineTension": 0.2,
                        "pointRadius": 0,
                        "backgroundColor": petrol,
                        "borderColor": petrol,
                        "data": df["c_S2"].to_list(),
                    },
                ],
            },
            "options": {
                "legend": {"display": True},
                "scales": {
                    "x": {
                        "type": "linear",
                        "title": {
                            "display": True,
                            "text": "t in h",
                            "font": {"size": labelfontsize},
                        },
                        "ticks": {"min": 0, "stepSize": 1},
                    },
                    "yL": {
                        "position": "left",
                        "type": "linear",
                        "display": True,
                        "grid": {"drawOnChartArea": True},
                        "min": 0,
                        "title": {
                            "display": True,
                            "text": "c(S1) [g" + cdot + "L" + hochminus1 + "]",
                            "font": {"size": labelfontsize},
                        },
                    },
                    "yR": {
                        "position": "right",
                        "display": True,
                        "grid": {"drawOnChartArea": False},
                        "type": "linear",
                        "min": 0,
                        "title": {
                            "display": True,
                            "text": "c(S2) [g" + cdot + "L" + hochminus1 + "]",
                            "font": {"size": labelfontsize},
                            "color": petrol,
                        },
                        "ticks": {"color": petrol},
                    },
                },
                "plugins": {
                    "legend": {"position": "bottom"},
                    "title": {
                        "display": True,
                        "text": "Substratkonzentration",
                        "font": {"size": labelfontsize + 2},
                    },
                },
            },
        }

        charts["Chart_2"] = {
            "type": "line",
            "data": {
                "labels": df["t"].to_list(),
                "datasets": [
                    {
                        "label": "Druck (p)",
                        "yAxisID": "yL",
                        "fill": False,
                        "lineTension": 0.2,
                        "pointRadius": 0,
                        "backgroundColor": orange,
                        "borderColor": orange,
                        "data": df["Druck"].to_list(),
                    },
                    {
                        "label": "Begasungsrate Luft (Q_Air)",
                        "yAxisID": "yL",
                        "fill": False,
                        "lineTension": 0.2,
                        "pointRadius": 0,
                        "backgroundColor": sun_yellow,
                        "borderColor": sun_yellow,
                        "data": df["Begasungsrate"].to_list(),
                    },
                    {
                        "label": "Drehzahl (n)",
                        "yAxisID": "yR",
                        "fill": False,
                        "lineTension": 0.2,
                        "pointRadius": 0,
                        "backgroundColor": "black",
                        "borderColor": "black",
                        "data": df["Drehzahl"].to_list(),
                    },
                    {
                        "label": "Gel" + r"\u{00F6}" + "stsauerstoff (DO)",
                        "yAxisID": "yR",
                        "fill": False,
                        "lineTension": 0.2,
                        "pointRadius": 0,
                        "backgroundColor": oliv,
                        "borderColor": oliv,
                        "data": df["c_DO"].to_list(),
                    },
                ],
            },
            "options": {
                "legend": {"display": True},
                "scales": {
                    "x": {
                        "type": "linear",
                        "title": {
                            "display": True,
                            "text": "t in h",
                            "font": {"size": labelfontsize},
                        },
                        "ticks": {"min": 0, "stepSize": 1},
                    },
                    "yL": {
                        "position": "left",
                        "type": "linear",
                        "display": True,
                        "grid": {"drawOnChartArea": True},
                        "min": 0,
                        "title": {
                            "display": True,
                            "text": "p [barg], Q_Air [NL" + cdot + "L" + hochminus1 + cdot + "min" + hochminus1 + "]",
                            "font": {"size": labelfontsize},
                        },
                    },
                    "yR": {
                        "position": "right",
                        "display": True,
                        "grid": {"drawOnChartArea": False},
                        "type": "linear",
                        "min": 0,
                        "title": {
                            "display": True,
                            "text": "n/10[min" + hochminus1 + "], DO [%]",
                            "font": {"size": labelfontsize},
                            "color": "black",
                        },
                        "ticks": {"color": "black"},
                    },
                },
                "plugins": {
                    "legend": {"position": "bottom"},
                    "title": {
                        "display": True,
                        "text": "Begasungsbezogen",
                        "font": {"size": labelfontsize + 2},
                    },
                },
            },
        }

        charts["Chart_3"] = {
            "type": "line",
            "data": {
                "labels": df["t"].to_list(),
                "datasets": [
                    {
                        "label": "Biotrockenmasse c(x)",
                        "yAxisID": "yL",
                        "fill": False,
                        "lineTension": 0.2,
                        "pointRadius": 0,
                        "backgroundColor": orange,
                        "borderColor": orange,
                        "data": df["c_x"].to_list(),
                    },
                    {
                        "label": "Produktkonz. c(p)",
                        "yAxisID": "yL",
                        "fill": False,
                        "lineTension": 0.2,
                        "pointRadius": 0,
                        "backgroundColor": sun_yellow,
                        "borderColor": sun_yellow,
                        "data": df["c_P"].to_list(),
                    },
                    {
                        "label": "Volumen (V)",
                        "yAxisID": "yR",
                        "fill": False,
                        "lineTension": 0.2,
                        "pointRadius": 0,
                        "backgroundColor": petrol,
                        "borderColor": petrol,
                        "data": df["V_L"].to_list(),
                    },
                ],
            },
            "options": {
                "legend": {"display": True},
                "scales": {
                    "x": {
                        "type": "linear",
                        "title": {
                            "display": True,
                            "text": "t in h",
                            "font": {"size": labelfontsize},
                        },
                        "ticks": {"min": 0, "stepSize": 1},
                    },
                    "yL": {
                        "position": "left",
                        "type": "linear",
                        "display": True,
                        "grid": {"drawOnChartArea": True},
                        "min": 0,
                        "title": {
                            "display": True,
                            "text": "c(P), c(X) [g" + cdot + "L" + hochminus1 + "]",
                            "font": {"size": labelfontsize},
                        },
                    },
                    "yR": {
                        "position": "right",
                        "display": True,
                        "grid": {"drawOnChartArea": False},
                        "type": "linear",
                        "min": 0,
                        "title": {
                            "display": True,
                            "text": "V [L]",
                            "font": {"size": labelfontsize},
                            "color": "black",
                        },
                        "ticks": {"color": "black"},
                    },
                },
                "plugins": {
                    "legend": {"position": "bottom"},
                    "title": {
                        "display": True,
                        "text": "Produkte und Volumen",
                        "font": {"size": labelfontsize + 2},
                    },
                },
            },
        }

        charts["Chart_4"] = {
            "type": "line",
            "data": {
                "labels": df["t"].to_list(),
                "datasets": [
                    {
                        "label": "Oxygen uptake rate (OUR)",
                        "yAxisID": "yL",
                        "fill": False,
                        "lineTension": 0.2,
                        "pointRadius": 0,
                        "backgroundColor": "brown",
                        "borderColor": "brown",
                        "data": df["OUR"].to_list(),
                    },
                    {
                        "label": "Respiratorischer Quotient (RQ)",
                        "yAxisID": "yR",
                        "fill": False,
                        "lineTension": 0.2,
                        "pointRadius": 0,
                        "backgroundColor": petrol,
                        "borderColor": petrol,
                        "data": df["RQ"].to_list(),
                    },
                ],
            },
            "options": {
                "legend": {"display": True},
                "scales": {
                    "x": {
                        "type": "linear",
                        "title": {
                            "display": True,
                            "text": "t in h",
                            "font": {"size": labelfontsize},
                        },
                        "ticks": {"min": 0, "stepSize": 1},
                    },
                    "yL": {
                        "position": "left",
                        "type": "linear",
                        "display": True,
                        "grid": {"drawOnChartArea": True},
                        "min": 0,
                        "title": {
                            "display": True,
                            "text": "OUR [mmol" + cdot + "L" + hochminus1 + cdot + "h" + hochminus1 + "]",
                            "font": {"size": labelfontsize},
                        },
                    },
                    "yR": {
                        "position": "right",
                        "display": True,
                        "grid": {"drawOnChartArea": False},
                        "type": "linear",
                        "min": 0,
                        "title": {
                            "display": True,
                            "text": "RQ [-]",
                            "font": {"size": labelfontsize},
                            "color": petrol,
                        },
                        "ticks": {"color": petrol},
                    },
                },
                "plugins": {
                    "legend": {"position": "bottom"},
                    "title": {
                        "display": True,
                        "text": "Abgasanalyse",
                        "font": {"size": labelfontsize + 2},
                    },
                },
            },
        }

        return charts

    def serialize(self, data: ChartDataset) -> str:
        return json.dumps(data)
