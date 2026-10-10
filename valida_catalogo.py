"""Conservative automatic publication of source-backed meal recipes.

No nutrition/cost invention; no dietary/allergen clearance. Uncertain recipes stay in review.
Idempotent: rerunning does not modify already validated entries unless status changed.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

from classifica_catalogo import classify, assess

DEFAULT = Path('data/catalogo.json')
ALLOWED_TYPES = {'Primo', 'Secondo', 'Piatto unico'}
# Require all components of a meal and unambiguous equipment; do not certify diets.
OVEN = re.compile(r'\b(forno|infornat|cuocete in forno|forno ventilato|forno statico)\b', re.I)
STOVE = re.compile(r'\b(padella|pentola|tegame|casseruola|bollit|lessat|rosolat|saltat|soffrigg|fuoco|fornello)\b', re.I)
MICROWAVE = re.compile(r'\b(microonde)\b', re.I)
AIRFRY = re.compile(r'\b(friggitrice ad aria)\b', re.I)
# Words in ingredient names that are insufficiently resolved for allergy/diet claims
UNCERTAIN_COMPOSITES = re.compile(r'\b(preparato|mix|salsa pronta|condimento pronto)\b', re.I)


def validate(rec):
    typ, kind, _ = classify(rec.get('name', ''))
    qa = assess(rec)
    reasons = []
    if kind != 'candidato' or typ not in ALLOWED_TYPES: reasons.append('non_candidato')
    if not qa['dati_completi']: reasons.append('ingredienti_porzione_procedimento_incompleti')
    if not isinstance(rec.get('time'), (int, float)) or rec['time'] <= 0: reasons.append('tempo_mancante')
    if not rec.get('url', '').startswith('https://ricette.giallozafferano.it/') and not rec.get('url', '').startswith('https://blog.giallozafferano.it/'):
        reasons.append('fonte_non_riconosciuta')
    if not rec.get('image_url', '').startswith('https://'): reasons.append('immagine_mancante')
    steps = rec.get('steps') or []
    procedure = ' '.join(s for s in steps if isinstance(s,str))
    tools = []
    for pattern, name in ((OVEN,'Forno'),(STOVE,'Fornelli'),(MICROWAVE,'Microonde'),(AIRFRY,'Friggitrice ad aria')):
        if pattern.search(procedure): tools.append(name)
    if not tools: reasons.append('attrezzatura_non_determinabile')
    # All of the above only qualifies for a general/unrestricted meal; no allergy or dietary certification.
    if any(UNCERTAIN_COMPOSITES.search(str(x[0])) for x in rec.get('ingredients',[]) if isinstance(x,list) and x):
        reasons.append('ingredienti_composti_non_identificati')
    return {'approved': not reasons, 'reasons': reasons, 'type': typ, 'tools': tools,
            'dietary_verified': [], 'allergen_verified': False, 'validation_version': 1}


def process(path, dry_run=False):
    records=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(records,list): raise ValueError('Catalogo non valido')
    stats=Counter(); modified=0; names=[]
    for r in records:
        if 'classificazione_automatica' not in r and r.get('needs_review') is not True:
            stats['preesistenti']+=1
            continue
        result=validate(r)
        desired={'validazione_automatica':result,'needs_review':not result['approved']}
        if result['approved']:
            desired['type']=result['type'];names.append(r.get('name',''))
        for k,v in desired.items():
            if r.get(k)!=v:
                r[k]=v;modified+=1
        stats['approvate' if result['approved'] else 'in_revisione']+=1
        for reason in result['reasons']: stats['manca_'+reason]+=1
    if modified and not dry_run:
        path.write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Validazione automatica: approvate={stats["approvate"]}; in revisione={stats["in_revisione"]}; preesistenti={stats["preesistenti"]}; campi modificati={modified}')
    if names: print('Attivate per piano senza restrizioni: '+'; '.join(names[:20]))
    for name,count in sorted(stats.items()):
        if name.startswith('manca_'): print(f'  {name}: {count}')
    print('ATTENZIONE: nessuna scheda automatica è certificata per diete, allergie o intolleranze.')
    return stats

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--file',type=Path,default=DEFAULT)
    ap.add_argument('--dry-run',action='store_true');args=ap.parse_args()
    process(args.file,args.dry_run)
