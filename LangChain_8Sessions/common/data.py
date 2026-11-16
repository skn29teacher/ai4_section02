import json
from common.runtime import ROOT

def cases():
    return json.loads((ROOT / 'data' / 'notices.json').read_text(encoding='utf-8'))

def first_input():
    return {k:v for k,v in cases()[0].items() if k != 'id'}
