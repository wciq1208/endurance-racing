"""Generate the frontend contract from the actual Pydantic CSV models."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from race_data.models import Envelope,Run
from race_data.csv_io import MODELS

if __name__=='__main__':
    value={'envelope':Envelope.model_json_schema(),'run':Run.model_json_schema(),
           'datasets':{name:dict(columns=list(model.model_fields),schema=model.model_json_schema()) for name,model in MODELS.items()}}
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    target=ROOT/'frontend/src/csv-schema.json';text=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if args.check:
        if not target.exists() or target.read_text(encoding='utf-8')!=text:raise SystemExit('Frontend contract is stale; run scripts/export_csv_schema.py')
    else:target.write_text(text,encoding='utf-8')
