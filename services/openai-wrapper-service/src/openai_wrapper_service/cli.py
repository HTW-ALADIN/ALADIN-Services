from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openai_wrapper_service.client import OpenAIWrapper, OpenAIWrapperProtocol
from openai_wrapper_service.schemas import EmbeddingsRequest, GenerateRequest


def _read_input(value: str) -> str:
    if value == "-":
        return sys.stdin.read()
    return value


def _write_output(payload: str, output: Path | None) -> None:
    if output is None:
        sys.stdout.write(payload)
        if not payload.endswith("\n"):
            sys.stdout.write("\n")
        return
    output.write_text(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openai-wrapper",
        description="Call the OpenAI wrapper service contract from the command line.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="Generate text from an input prompt.")
    generate_parser.add_argument("input", help="Input text. Use '-' to read from stdin.")
    generate_parser.add_argument("--model")
    generate_parser.add_argument("--instructions")
    generate_parser.add_argument("--max-output-tokens", type=int)
    generate_parser.add_argument("--temperature", type=float)
    generate_parser.add_argument("--store", action="store_true")
    generate_parser.add_argument("--text-only", action="store_true", help="Write only output_text instead of JSON.")
    generate_parser.add_argument("-o", "--output", type=Path)

    embeddings_parser = subparsers.add_parser("embeddings", help="Create embeddings for one or more inputs.")
    embeddings_parser.add_argument("input", nargs="+", help="Input text values. Use a single '-' to read stdin.")
    embeddings_parser.add_argument("--model")
    embeddings_parser.add_argument("--dimensions", type=int)
    embeddings_parser.add_argument("--user")
    embeddings_parser.add_argument("-o", "--output", type=Path)

    return parser


def main(argv: list[str] | None = None, service: OpenAIWrapperProtocol | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client = service or OpenAIWrapper()

    if args.command == "generate":
        response = client.generate(
            GenerateRequest(
                input=_read_input(args.input),
                model=args.model,
                instructions=args.instructions,
                max_output_tokens=args.max_output_tokens,
                temperature=args.temperature,
                store=args.store,
            )
        )
        payload = response.output_text if args.text_only else response.model_dump_json(indent=2)
        _write_output(payload, args.output)
        return 0

    if args.command == "embeddings":
        input_value: str | list[str]
        if len(args.input) == 1:
            input_value = _read_input(args.input[0])
        else:
            input_value = args.input

        response = client.embeddings(
            EmbeddingsRequest(input=input_value, model=args.model, dimensions=args.dimensions, user=args.user)
        )
        _write_output(response.model_dump_json(indent=2), args.output)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
