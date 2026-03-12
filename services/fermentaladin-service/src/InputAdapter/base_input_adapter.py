import json
from abc import abstractmethod

import pandas as pd

from Util.base_io_adapter import IOAdapter


class InputAdapter(IOAdapter):
    @abstractmethod
    def transform_data(self, data: json) -> pd.DataFrame:
        return
