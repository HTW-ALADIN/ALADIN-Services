import logging
import sys
from abc import abstractmethod

import pandas as pd

from Util.base_io_adapter import IOAdapter, unknown


class OutputAdapter(IOAdapter):
    @abstractmethod
    def transform_data(self, data: pd.DataFrame) -> unknown:
        return

    @abstractmethod
    def serialize(self, data: unknown) -> str:
        return

    def write(self, serialized_data: str, file_path: str = None) -> None:
        if file_path:
            try:
                with open(file_path, "w+") as f:
                    f.write(serialized_data)
            except Exception as e:
                logging.error(e)
            finally:
                return

        sys.stdout.write(serialized_data)
