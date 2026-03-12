import argparse
import sys


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_help(sys.stderr)
        self.exit(2, "%s: error: %s\n" % (self.prog, message))


parser = ArgumentParser(
    prog="FermentationModel",
    description="This program calculates the result of a fermentation process based on a set of input parameters. The fermentation model supports multiple phases, as well as batch and flow processing.",
)
parser.add_argument(
    "-p",
    "--parameters",
    type=str,
    help="The input parameters for the fermentation model. The type in which the input parameters are passed is defined with -i option.",
)
parser.add_argument(
    "-i",
    "--input-type",
    default="stdi",
    choices=["stdi", "file", "excel"],
    help='The type with which the input parameters are being passed. Can be "json", "file" or "excel". Default is "json". "file" expects a path to a valid json-file. "excel" expects a path to a valid excel-sheet.',
)
parser.add_argument(
    "-o",
    "--output-format",
    default="df",
    choices=["df", "chart"],
    help='The format of output. Can be "chart" or "df". Default is "df" and outputs a dataframe. "chart" transforms the dataframe into plot descriptions for chartjs.',
)
parser.add_argument("-f", "--file", help="Output to file. Expects a valid file path.")
