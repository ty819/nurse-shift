import argparse
import pathlib
from app.validation import load_and_validate


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate nurses.csv and rules.json")
    parser.add_argument("--nurses", default=str(pathlib.Path(__file__).parents[1] / "samples/nurses.csv"))
    parser.add_argument("--rules", default=str(pathlib.Path(__file__).parents[1] / "samples/rules.json"))
    parser.add_argument(
        "--schemas-dir",
        default=str(pathlib.Path(__file__).parents[1] / "packages/schemas"),
    )
    args = parser.parse_args()

    nurses, rules = load_and_validate(args.nurses, args.rules, args.schemas_dir)
    print(f"OK: nurses={len(nurses)} rules.year={rules.get('year')} rules.month={rules.get('month')}")


if __name__ == "__main__":
    main()

