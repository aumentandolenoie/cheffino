"""Rimuove i riferimenti numerici alle foto GialloZafferano dai passaggi.

Non modifica ingredienti, dosi, tempi o valori nutrizionali. Funziona su tutte
le schede esistenti in data/catalogo.json e sulle future ricette quando eseguito
nel workflow settimanale. Nessuna richiesta di rete.
"""
import argparse
import json
import re
from pathlib import Path

CATALOG = Path('data/catalogo.json')
# Non confondere le foto con dosi, temperature e tempi di preparazione.
MEASURES = re.compile(
    r'^(?:g|gr|grammi?|kg|mg|ml|cl|dl|l|litri?|minuti?|min|secondi?|sec|ore?|h|'
    r'°c|gradi|spicchi?|cucchiai?|cucchiaini?|fette?|pezzi?|persone|porzioni|'
    r'giorni?|settimane?|cm|mm|%)\b', re.I)
PHOTO = re.compile(r'(?<=\S)\s+([1-9]|[1-3]\d|40)(?=\s*(?:[.,;:!?]|\b))')


def candidates(steps):
    hits = []
    for step_index, step in enumerate(steps):
        if not isinstance(step, str):
            continue
        for m in PHOTO.finditer(step):
            # Non modificare '10 minuti', '4 g', ecc.
            following = step[m.end():].lstrip()
            if MEASURES.match(following):
                continue
            # Evita intervalli tipo 'a 2-3' e numeri decimali.
            preceding = step[:m.start()].rstrip()
            if preceding and preceding[-1] in '-/,.0123456789':
                continue
            if following.startswith(('-', '/', '–')):
                continue
            hits.append((step_index, m.start(), m.end(), int(m.group(1))))
    return hits


# --- Pulizia v2 -----------------------------------------------------------
# GialloZafferano inserisce nel testo i numeri delle foto del procedimento:
# «versate l'olio 9 e scaldatelo», «aderire (8.», «(5-6)». La versione 1
# richiedeva una sequenza 1,2,3... senza buchi e si fermava al primo numero
# non riconosciuto, lasciando nel testo pubblicato riferimenti come «12 .».
# La v2 accetta un riferimento solo se:
#   - il numero appartiene alle foto dello stesso blocco (o di quelli vicini),
#     ricavate dai nomi file delle immagini (…_7.jpg, …strip_7-9.jpg), oppure
#   - fa parte di una catena crescente (salti <= 2) di almeno tre riferimenti
#     che parte da 1-3 (sezioni con numerazione che riparte sono gestite);
# e in ogni caso il numero non è una dose, un tempo o una misura.
REF = re.compile(
    r'(?P<lead>[ \t\u00a0]*)(?P<open>\()?[ ]?(?P<a>\d{1,3})'
    r'(?:[ ]?[-\u2013][ ]?(?P<b>\d{1,3}))?[ ]?(?P<close>\))?'
    r'(?=[ \t\u00a0]*(?:[.,;:!?)\u2026]|$)|[ \t\u00a0]+[^\W\d_]|[ \t\u00a0]+\d{1,3}\b(?![.,]\d))')
# Parole che seguono un riferimento fotografico nel testo GZ.
CONNECTORS = {
    'e', 'ed', 'poi', 'quindi', 'fino', 'finche', 'finché', 'sino', 'mentre', 'infine',
    'intanto', 'a', 'ad', 'per', 'con', 'che', 'in', 'dopo', 'prima', 'oppure', 'o',
    'ma', 'così', 'cosi', 'senza', 'facendo', 'e/o', 'nel', 'nella', 'sul', 'sulla',
    'dentro', 'insieme', 'direttamente', 'subito', 'aiutandovi', 'mescolando',
    'lasciando', 'usando', 'utilizzando', 'tenendo', 'avendo', 'dove', 'come', 'se',
    'oltre', 'ancora', 'ora', 'quando', 'appena', 'non', 'fin', 'affinché', 'affinche',
    'il', 'lo', 'la', 'i', 'gli', 'le', 'un', 'uno', 'una', 'del', 'della', 'dei',
    'delle', 'al', 'alla', 'ai', 'alle', 'da', 'di', 'su', 'tra', 'fra', 'verso',
}
# Parole che precedono quantità reali: «in 4», «a 2», «circa 3».
QUANTITY_LEAD = {
    'in', 'a', 'ad', 'di', 'da', 'per', 'con', 'su', 'tra', 'fra', 'circa', 'le', 'i',
    'gli', 'x', 'ogni', 'ne', 'dei', 'delle', 'degli', 'ai', 'alle', 'al', 'verso',
    'oltre', 'almeno', 'sui', 'sulle', 'n', 'n.', 'n°', 'numero', 'entro', 'altri',
    'altre', 'dopo', 'massimo', 'minimo', 'ultimi', 'ultime', 'primi', 'prime',
    'otterrete', 'ricavate', 'ricavare', 'ricavatene', 'formate', 'dividete',
    'dividetelo', 'dividetela', 'tagliatelo', 'tagliatela', 'serviranno', 'circa',
}
_IMAGE_NUMBER = re.compile(r'(?<![x\d])[-_](\d{1,3})\.(?:jpe?g|png|webp)(?:$|\?)', re.I)
_IMAGE_STRIP = re.compile(r'strip[_-]?(\d{1,3})-(\d{1,3})\.(?:jpe?g|png|webp)(?:$|\?)', re.I)


def photo_numbers(step_images):
    """Numeri di foto per blocco, dai nomi file; None se non ricavabili."""
    if not isinstance(step_images, list) or not step_images:
        return None
    result, found = [], False
    for group in step_images:
        numbers = set()
        for url in group if isinstance(group, list) else []:
            name = str(url).rsplit('/', 1)[-1]
            if m := _IMAGE_STRIP.search(name):
                a, b = map(int, m.groups())
                if 1 <= a <= b <= a + 5:
                    numbers.update(range(a, b + 1))
            elif m := _IMAGE_NUMBER.search(name):
                numbers.add(int(m.group(1)))
        found = found or bool(numbers)
        result.append(numbers)
    return result if found else None


def _tokens(steps):
    """Riferimenti numerici plausibili, nell'ordine del testo."""
    out = []
    for index, step in enumerate(steps):
        if not isinstance(step, str):
            continue
        for m in REF.finditer(step):
            start = m.start('open') if m.group('open') else m.start('a')
            before = step[:start]
            if before and not before[-1].isspace() and before[-1] != '(' and not m.group('open'):
                continue  # «30x20», «1,5», «180°»: parte di un'altra parola
            stripped = before.rstrip()
            if not stripped:
                continue  # un blocco non inizia con un riferimento fotografico
            if stripped[-1] in '-/\u2013x×' and not m.group('open'):
                continue  # «20 - 30», «1/ 2»
            if m.group('b') and not (m.group('open') and m.group('close')):
                continue  # «4-5 minuti»: intervallo reale senza parentesi
            after = step[m.end():]
            if re.match(r'[.,]\d', after):
                continue  # «1,5 cm», «0.5»
            word = re.match(r'\s*([^\s.,;:!?()]+)', after)
            following = word.group(1).casefold() if word and not re.match(r'\s*[.,;:!?)\u2026]', after) else ''
            if following and not following.isdigit() and (MEASURES.match(following) or following not in CONNECTORS
                              and not following.endswith(('ando', 'endo'))):
                continue
            prev = re.search(r'([^\s(]+)\s*\(?\s*$', before)
            if prev and prev.group(1).casefold().strip('.,;:') in QUANTITY_LEAD:
                continue
            a = int(m.group('a'))
            b = int(m.group('b')) if m.group('b') else a
            if not (1 <= a <= b <= 120 and b - a <= 3):
                continue
            span_start = m.start()
            span_end = m.end()
            out.append({'step': index, 'start': span_start, 'end': span_end, 'a': a, 'b': b,
                        'open': bool(m.group('open')), 'close': bool(m.group('close'))})
    return out


def _chains(tokens, anchors=()):
    """Catene crescenti di riferimenti (salti <= 2) lunghe almeno 3.

    Una catena è accettata se parte da 1-3 oppure se contiene almeno due
    riferimenti già confermati dai nomi file delle foto (``anchors``).
    """
    anchors = set(anchors)
    remaining = list(range(len(tokens)))
    selected = set()
    while True:
        best = []
        n = len(remaining)
        length, parent = [1] * n, [-1] * n
        for j in range(n):
            tj = tokens[remaining[j]]
            for i in range(j):
                ti = tokens[remaining[i]]
                if 0 < tj['a'] - ti['b'] <= 2 and length[i] + 1 > length[j]:
                    length[j], parent[j] = length[i] + 1, i
        for j in range(n):
            chain, k = [], j
            while k != -1:
                chain.append(remaining[k]); k = parent[k]
            chain.reverse()
            if len(chain) > len(best) and (tokens[chain[0]]['a'] <= 3 or
                                           sum(k in anchors for k in chain) >= 2):
                best = chain
        if len(best) < 3:
            return selected
        selected.update(best)
        remaining = [i for i in remaining if i not in selected]


def find_photo_refs(steps, step_images=None):
    tokens = _tokens(steps)
    evidence = photo_numbers(step_images) if step_images is not None else None
    chosen = set()
    if evidence and len(evidence) == len(steps):
        for k, t in enumerate(tokens):
            near = set()
            for j in (t['step'] - 1, t['step'], t['step'] + 1):
                if 0 <= j < len(evidence):
                    near |= evidence[j]
            if t['a'] in near and t['b'] in near:
                chosen.add(k)
    chosen |= _chains(tokens, chosen)
    return [tokens[k] for k in sorted(chosen)]


def _tidy(text):
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'[ \t\u00a0]+([.,;:!?\u2026])', r'\1', text)
    text = re.sub(r'([.,;:])(?:\s*\1)+', r'\1', text)
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'[ \t\u00a0]{2,}', ' ', text)
    return text.strip()


def clean_steps(steps, step_images=None):
    """Rimuove i riferimenti alle foto. Restituisce (passaggi, numero_rimossi)."""
    if not isinstance(steps, list):
        return steps, 0
    refs = find_photo_refs(steps, step_images)
    if not refs:
        return steps, 0
    updated = list(steps)
    by_step = {}
    for ref in refs:
        by_step.setdefault(ref['step'], []).append(ref)
    for index, items in by_step.items():
        text = updated[index]
        for ref in sorted(items, key=lambda r: r['start'], reverse=True):
            piece = text[ref['start']:ref['end']]
            # «(8.» -> «.»; «(5-6)» -> «»; «olio 9 e» -> «olio e»
            replacement = ' ' if re.search(r'\S$', text[:ref['start']]) and not piece.lstrip().startswith('(') else ''
            if piece.lstrip().startswith('(') and not ref['close']:
                replacement = ''
            text = text[:ref['start']] + replacement + text[ref['end']:]
        updated[index] = _tidy(text)
    return updated, len(refs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    args = parser.parse_args()
    data = json.loads(args.catalog.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError('Il catalogo deve essere una lista JSON')
    recipes_changed = references_removed = 0
    for recipe in data:
        if recipe.get('source') != 'GialloZafferano':
            continue
        steps, removed = clean_steps(recipe.get('steps'), recipe.get('step_images'))
        if removed:
            recipe['steps'] = steps
            recipes_changed += 1
            references_removed += removed
            print(f"Pulita: {recipe.get('name', 'Senza nome')} | riferimenti foto rimossi={removed}")
    if recipes_changed:
        args.catalog.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Pulizia procedimenti: ricette aggiornate={recipes_changed}; riferimenti fotografici rimossi={references_removed}; totale={len(data)}', flush=True)


if __name__ == '__main__':
    main()
