import argparse
from datetime import datetime

from kurrasa.config import AGENT_MODELS, create_llm
from kurrasa.pipeline.run import run_scenario


def main():
    parser = argparse.ArgumentParser(description="Run Kurrasa on a scenario, or as a human requester.")
    who = parser.add_mutually_exclusive_group(required=True)
    who.add_argument("--scenario", help="scenario folder name, e.g. crm_vague")
    who.add_argument("--human", action="store_true", help="type the requester's answers yourself")
    parser.add_argument("--run-id", default=datetime.now().strftime("%Y%m%d-%H%M%S"))
    args = parser.parse_args()

    out = run_scenario(
        None if args.human else args.scenario,
        args.run_id,
        create_llm(**AGENT_MODELS["agent"]),
        create_llm(**AGENT_MODELS["requester"]),
    )
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
