import json
import logging
import sys
from typing import ClassVar

import pandas as pd

from .base_input_adapter import InputAdapter


class STDINAdapter(InputAdapter):
    __qualname__: ClassVar[str] = "stdi"

    def transform_data(self, data: str) -> pd.DataFrame:
        try:
            input_df = pd.DataFrame(json.loads(data))
        except json.JSONDecodeError as error:
            logging.error("Invalid JSON input from stdi.")
            logging.error(error)
            sys.exit(1)
        return input_df
