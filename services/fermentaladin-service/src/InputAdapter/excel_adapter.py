import json
import logging
from typing import ClassVar

import pandas as pd

from .base_input_adapter import InputAdapter


class ExcelAdapter(InputAdapter):
    __qualname__: ClassVar[str] = "excel"

    def transform_data(self, file_path: str, sheet_name: str = "Input_Array") -> pd.DataFrame:
        input_df = None
        try:
            input_df = pd.read_excel(
                file_path,
                sheet_name=sheet_name,
                skiprows=2,
                nrows=4,
                header=0,
                usecols="A:Q",
            )
        except json.JSONDecodeError as error:
            logging.error("Invalid Excel input.")
            logging.error(error)
            raise
        except FileNotFoundError as error:
            logging.error("Invalid file path for excel input.")
            logging.error(error)
            raise
        return input_df
