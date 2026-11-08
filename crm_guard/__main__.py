import argparse
import csv
import json
import sys
from pathlib import Path
from .core import read_csv, reconcile, preview_target, write_csv, columns


def main(argv=None):
    parser = argparse.ArgumentParser(description='Audit CRM sync CSVs without contacting a CRM.')
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--target', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='New directory; existing paths are refused')
    args = parser.parse_args(argv)
    try:
        source, target = read_csv(args.source), read_csv(args.target)
        plan = reconcile(source, target)
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8')
        preview = preview_target(target, plan)
        write_csv(args.output / 'target-preview.csv', preview)
        with (args.output / 'target-preview.json').open('x', encoding='utf-8') as stream:
            json.dump({'columns': list(columns(preview)), 'rows': preview}, stream,
                      indent=2, ensure_ascii=True)
            stream.write('\n')
    except (OSError, ValueError, csv.Error) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(plan['summary'], sort_keys=True))
    print(f'Review {args.output / "plan.json"}; no CRM was modified.')
    return 2 if plan['issues'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
