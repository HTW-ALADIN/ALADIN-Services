import logging
import os
import sys
from typing import Tuple

import pandas as pd

from calc.calc_bioreactor import calculate
from InputAdapter.input_adapter_strategy import input_adapter_strategy
from OutputAdapter.base_output_adapter import OutputAdapter
from OutputAdapter.output_adapter_strategy import output_adapter_strategy
from Util.arg_parser import parser

# from Util.multiplot_ferm import multiplot_ferm

logging.basicConfig(level=os.environ.get("LOG_LEVEL") or logging.INFO)


def main() -> Tuple[pd.DataFrame, OutputAdapter, str | None]:
    args = parser.parse_args()

    input_adapter = input_adapter_strategy.select_strategy(args.input_type)

    input_df = input_adapter.transform_data(args.parameters)
    output_adapter = output_adapter_strategy.select_strategy(args.output_format)

    return input_df, output_adapter, args.file


if __name__ == "__main__":
    [input_df, output_adapter, file_path] = main()
    result_df = calculate(input_df)

    output = output_adapter.transform_data(result_df)
    serialized_output = output_adapter.serialize(output)
    output_adapter.write(serialized_output, file_path)

    # TODO: flag for toggling?
    # multiplot_ferm(result_df)
    sys.exit(0)
