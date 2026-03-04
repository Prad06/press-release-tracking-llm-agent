"""CLI entrypoint for the LangGraph pipeline."""

from __future__ import annotations

import argparse
import uuid

from .graph import build_app
from .state import GraphState


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run LangGraph event pipeline.")
    p.add_argument(
        "--tickers",
        nargs="*",
        default=[],
        help="Optional list of tickers to restrict processing to.",
    )
    p.add_argument(
        "--method-version",
        default="v0",
        help="Logical method version label stored in processing metadata.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    app = build_app()

    run_id = str(uuid.uuid4())
    print(
        f"[graph] starting run_id={run_id} "
        f"method_version={args.method_version} "
        f"tickers={args.tickers or '*'}"
    )

    state = GraphState(
        run_id=run_id,
        method_version=args.method_version,
        tickers=[t.upper() for t in args.tickers],
    )
    final_state = app.invoke(state)

    print("[graph] finished:", final_state)


if __name__ == "__main__":
    main()

