from InputAdapter.base_input_adapter import InputAdapter
from InputAdapter.excel_adapter import ExcelAdapter
from InputAdapter.file_input_adapter import FileInputAdapter
from InputAdapter.std_in_adapter import STDINAdapter
from Util.strategy_pattern import Strategy


class InputAdapterStrategy(Strategy[InputAdapter]):
    pass


input_adapter_strategy = InputAdapterStrategy()
input_adapter_strategy.register_strategy(FileInputAdapter)
input_adapter_strategy.register_strategy(STDINAdapter)
input_adapter_strategy.register_strategy(ExcelAdapter)
