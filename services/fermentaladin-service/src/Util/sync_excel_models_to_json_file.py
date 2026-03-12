import json

import numpy as np
import pandas as pd


def sync_excel_models(
    excel_path: str = "./Bioreaktor_forPy.xlsx",
    model_file_storage_path: str = "./src/DataModels/model_db.json",
):
    excel_models = pd.read_excel(
        excel_path,
        sheet_name="Input_Array",
        skiprows=37,
        nrows=4,
        header=0,
        usecols="A:AA",
    ).replace({np.nan: None})

    model_kv_store = {}
    for model in excel_models.to_dict(orient="records"):
        model_kv_store[model["Modell"]] = model

    with open(model_file_storage_path, "w+") as f:
        json.dump(model_kv_store, f)


if __name__ == "__main__":
    sync_excel_models()
