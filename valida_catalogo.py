"""Conservative automatic publication of source-backed meal recipes.

No nutrition/cost invention; no dietary/allergen clearance. Uncertain recipes stay in review.
Idempotent: rerunning does not modify already validated entries unless status changed.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

from classifica_catalogo import classify_record, assess

DEFAULT = Path('data/catalogo.json')
ALLOWED_TYPES = {'Primo', 'Secondo', 'Piatto unico'}
# Require all components of a meal and unambiguous equipment; do not certify diets.
# Attrezzatura dal procedimento. Le radici («infornat», «rosolat») devono poter
# proseguire («infornate», «rosolatelo»): la v1 usava \b anche dopo la radice e
# riconosceva solo le parole esatte, lasciando 41 ricette senza attrezzatura.
OVEN = re.compile(r'\b(?:forno|fornetto|inforn\w*|sforn\w*|gratin\w*)', re.I)
# Solo parole inequivocabili: «cottura», «cuocete», «tostate», «vapore», «griglia»
# compaiono anche nelle ricette al forno e non bastano per richiedere i fornelli.
STOVE = re.compile(r'\b(?:padell\w*|pentol\w*|tegam\w*|casseruol\w*|wok|bollit\w*|bollor\w*|bollent\w*|'
                   r'sbollent\w*|lessat\w*|lessa(?:te|re)\w*|rosolat\w*|rosola(?:te|re)\w*|'
                   r'soffrigg\w*|soffritt\w*|fuoco|fiamma|fornell\w*|piastra|bagnomaria|sobbollire|'
                   r'friggete|friggere|frittura)', re.I)
OVEN_ONLY = re.compile(r'\b(?:cuocete|cuocere|cottura)\b[^.]{0,40}\bforno', re.I)
MICROWAVE = re.compile(r'\b(?:microonde)\b', re.I)
AIRFRY = re.compile(r'\b(?:friggitrice ad aria)\b', re.I)
NO_COOK = 'Nessuna cottura'
# Words in ingredient names that are insufficiently resolved for allergy/diet claims
UNCERTAIN_COMPOSITES = re.compile(r'\b(preparato|mix|salsa pronta|condimento pronto)\b', re.I)


def detect_tools(procedure, rec=None):
    """Forno / Fornelli / Microonde / Friggitrice ad aria; «Nessuna cottura» se la
    fonte dichiara cottura assente (cookTime 0) e il testo non cita alcuna cottura."""
    tools = []
    airfry = AIRFRY.search(procedure)
    if OVEN.search(procedure): tools.append('Forno')
    # «cuocete in forno» non implica i fornelli; la friggitrice ad aria nemmeno.
    stove_text = AIRFRY.sub(' ', OVEN_ONLY.sub(' ', procedure))
    if STOVE.search(stove_text): tools.append('Fornelli')
    if MICROWAVE.search(procedure): tools.append('Microonde')
    if airfry: tools.append('Friggitrice ad aria')
    if not tools and rec is not None and rec.get('source_cook_minutes') == 0:
        tools.append(NO_COOK)
    return tools


def validate(rec):
    typ, kind, _ = classify_record(rec)
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
    tools = detect_tools(procedure, rec)
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
