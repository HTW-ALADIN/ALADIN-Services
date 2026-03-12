import json
import logging
from typing import ClassVar

import pandas as pd

from .base_input_adapter import InputAdapter


class FileInputAdapter(InputAdapter):
    __qualname__: ClassVar[str] = "file"

    def transform_data(self, file_path: str) -> pd.DataFrame:
        input_df = None
        logging.error(file_path)
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            input_df = pd.DataFrame(data)
        except json.JSONDecodeError as error:
            logging.error("Invalid JSON input from file.")
            logging.error(error)
            raise
        except FileNotFoundError as error:
            logging.error("Invalid file path for input JSON file.")
            logging.error(error)
            raise
        return input_df
