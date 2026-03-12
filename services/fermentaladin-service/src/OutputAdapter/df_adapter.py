from typing import ClassVar

import pandas as pd

from .base_output_adapter import OutputAdapter


class DFAdapter(OutputAdapter):
    __qualname__: ClassVar[str] = "df"

    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        return df

    def serialize(self, df: pd.DataFrame) -> str:
        return df.to_json()
