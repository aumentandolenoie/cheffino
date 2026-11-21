"""Stima del costo delle ricette dai prezzi dei prodotti.

I supermercati non pubblicano listini leggibili (i volantini sono sfogliabili o
PDF, diversi per punto vendita), quindi la stima usa un listino di **prezzi
medi indicativi** della grande distribuzione italiana (€/kg o €/l, prodotto di
marca commerciale, aggiornato a fine 2026). Il costo di una ricetta è la somma
delle quantità indicate dalla fonte moltiplicate per questi prezzi, divisa per
le porzioni.

Regole prudenti:
- si stimano solo gli ingredienti con una quantità indicata; «q.b.» (sale, olio
  per ungere, spezie…) non entra nel conto: di solito è già in dispensa;
- se meno dell'80% degli ingredienti con quantità ha un prezzo nel listino, la
  ricetta non riceve una stima (meglio nessun numero che un numero sbagliato);
- l'app dichiara sempre che è una stima, non il prezzo del proprio negozio.
"""
import re
import unicodedata

AGGIORNAMENTO = '2026-11'

# (regex sul nome normalizzato, €/kg o €/l, peso di un pezzo in grammi)
# L'ordine conta: le voci più specifiche vengono prima.
LISTINO = [
    # costo zero o preparati in casa
    (r'^(acqua|ghiaccio)\b|^fumetto|scarti', 0, 1),
    # spezie, sale e aromi secchi
    (r'zafferano', 8000, 0.15),
    (r'sale (di )?maldon', 20, 0),
    (r'^sale\b', 0.5, 0),
    (r'^pepe\b|pepe (nero|bianco|rosa|verde|mix)', 40, 1),
    (r'peperoncino (secco|in polvere|di ca[iy]enna)|pepe di ca[iy]enna|paprika|curcuma|cumino|cannella|noce moscata|'
     r'coriandolo in polvere|semi di coriandolo|curry|zenzero in polvere|chiodi di garofano|anice|aglio in polvere|'
     r'origano secco|ginepro|senape (gialla )?in polvere|olive nere in polvere', 40, 1),
    (r'bicarbonato', 3, 0),
    (r'lievito alimentare', 30, 0),
    (r'lievito di birra secco', 25, 7),
    (r'lievito di birra', 10, 25),
    (r'caglio', 30, 0),
    (r'^te\b|^tè\b', 40, 0),
    # oli, aceti, vini
    (r'olio (extra ?vergine|extravergine)', 9, 0),
    (r'olio di sesamo|olio di semi (di )?sesamo', 15, 0),
    (r'olio di oliva', 7, 0),
    (r'olio di semi|olio per friggere', 3, 0),
    (r'aceto balsamico', 6, 0),
    (r'^aceto', 2.5, 0),
    (r'brandy|cognac', 20, 0),
    (r'vino di riso', 10, 0),
    (r'^vino|marsala', 5, 0),
    (r'^birra', 3, 0),
    # zuccheri
    (r'muscovado', 6, 0),
    (r'zucchero di canna', 2.5, 0),
    (r'^zucchero', 1.3, 0),
    (r'^miele', 10, 0),
    (r'^malto', 8, 0),
    # farine, amidi, pane
    (r'farina di mandorle', 15, 0),
    (r'farina di ceci', 4, 0),
    (r'farina di riso', 3, 0),
    (r'farina (di mais|istantanea|per polenta)', 2.5, 0),
    (r'^farina|^semola|^semolino', 1.5, 0),
    (r'amido|maizena|fecola', 4, 0),
    (r'pane senza glutine|focaccia senza glutine', 11, 300),
    (r'pangrattato|panko', 4, 0),
    (r'pancarre|pane (bianco )?in cassetta', 3.5, 25),
    (r'panini|puccia|rosette', 5, 80),
    (r'^pane|filoncini', 3.5, 60),
    (r'piadin|tortill|^pita', 6, 70),
    (r'taralli', 6, 10),
    (r'amaretti', 10, 8),
    # pasta, riso e cereali
    (r'pasta sfoglia', 7, 230),
    (r'senza glutine', 4.5, 0),
    (r'(troccoli|strozzapreti) freschi|all.uovo|tagliatelle|fettuccine|pappardelle', 6, 0),
    (r'^gnocchi', 3, 0),
    (r'integral|5 cereali|di ceci|chicchi di farina di legumi', 2.8, 0),
    (r'^(pasta|spaghett|linguin|fusill|penne|pennette|pennoni|pennotti|mezz[ei] (maniche|penne|rigatoni)|mini penne|'
     r'rigatoni|paccheri|conchiglion|orecchiett|trofie|casarecce|calamarata|pipe|ditalini|bucatini|capellini|'
     r'cellentani|cavatelli|busiate|tripoline|mafaldotte|farfalle|dischi volanti|elicoidali)', 2.0, 0),
    (r'riso (carnaroli|per risotti|originario|basmati)', 4, 0),
    (r'^riso', 3, 0),
    (r'^farro', 4, 0),
    (r'^orzo', 3, 0),
    (r'^bulgur|^couscous|^cous cous', 4, 0),
    (r'^quinoa', 8, 0),
    # legumi
    (r'(ceci|fagioli|lenticchie|legumi).*(precott|gia cott|lessat)', 3, 0),
    (r'lenticchie rosse', 5, 0),
    (r'^(ceci|fagioli|lenticchie|fave secche)', 4, 0),
    (r'^tofu', 8, 0),
    # pomodoro
    (r'concentrato', 6, 0),
    (r'pomodor(i|ini) secchi', 18, 0),
    (r'pelati|polpa di pomodoro|passata', 2, 0),
    (r'pomodorini|pachino', 4.5, 15),
    (r'^pomodori', 3, 150),
    # verdura
    (r'fiori di zucca', 25, 8),
    (r'^zucca', 1.8, 1000),
    (r'zucchine', 2.5, 200),
    (r'patate', 1.6, 200),
    (r'carote', 1.5, 100),
    (r'cipoll(e|otti|otto|ine) (rosse )?(di )?tropea|cipollotti rossi', 3, 100),
    (r'cipollott', 3, 60),
    (r'cipoll', 1.5, 150),
    (r'scalogno', 5, 30),
    (r'^porri', 3, 200),
    (r'^sedano', 2, 50),
    (r'melanzane', 2.5, 300),
    (r'friggitelli', 4, 30),
    (r'peperon(i|cini (verdi|dolci)|cino (verde|dolce))', 3.5, 200),
    (r'peperoni cruschi', 60, 10),
    (r'peperoncino', 15, 10),
    (r'fagiolini|taccole', 4.5, 0),
    (r'spinacini|songino|valeriana', 11, 0),
    (r'rucola', 12, 0),
    (r'spinaci|erbette|bietol', 4, 0),
    (r'lattuga|insalata|scarola|cicoria|indivia', 3, 300),
    (r'radicchio', 4, 300),
    (r'cavoletti', 4, 15),
    (r'kale|cavolo riccio|pak choi', 8, 200),
    (r'cavol|verza|broccol|cime di rapa', 2.5, 800),
    (r'asparagi', 8, 25),
    (r'carciofi', 4, 200),
    (r'porcini secchi|funghi secchi', 60, 0),
    (r'porcini', 25, 0),
    (r'funghi (champignon)?$|champignon', 5, 20),
    (r'funghi', 14, 20),
    (r'cetrioli', 2, 250),
    (r'cetriolini', 8, 10),
    (r'ravanelli', 4, 15),
    (r'finocch(i|io)$|^finocchi ', 2, 300),
    (r'barbabietol', 2.5, 150),
    (r'piselli', 4, 0),
    (r'^fave', 4, 0),
    (r'^mais', 4, 0),
    (r'castagne', 7, 10),
    (r'avocado', 6, 200),
    (r'zenzero', 8, 20),
    (r'^aglio', 6, 40),
    # erbe aromatiche fresche
    (r'basilico|prezzemolo|menta|salvia|rosmarino|timo|maggiorana|erba cipollina|aneto|coriandolo|alloro|'
     r'finocchietto|santoreggia|origano', 25, 5),
    # frutta
    (r'succo di (limone|lime)', 7.5, 40),
    (r'succo d.arancia', 3, 80),
    (r'^scorza', 10, 3),
    (r'^limon', 2.5, 120),
    (r'^lime', 4, 70),
    (r'^arance|^mandarini', 2.2, 180),
    (r'^mele', 2.2, 180),
    (r'^pere', 2.5, 180),
    (r'^pesche', 3, 150),
    (r'^uva\b', 3.5, 0),
    (r'^uvetta', 8, 0),
    (r'melone', 2, 1200),
    (r'cocomero|anguria', 1, 3000),
    (r'melagrana', 4, 300),
    (r'^more|lamponi|mirtilli', 20, 0),
    # frutta secca e semi
    (r'pinoli', 60, 0.3),
    (r'pistacchi', 35, 0.7),
    (r'anacardi', 20, 1.5),
    (r'nocciole', 18, 1.5),
    (r'mandorle', 15, 1.2),
    (r'noci', 15, 5),
    (r'arachidi', 8, 0.8),
    (r'^semi', 12, 0),
    (r'tahina', 12, 0),
    # latticini e uova
    (r'^(uova|uovo|tuorl|album)', 5.5, 55),
    (r'^burrata', 15, 125),
    (r'^burro', 10, 0),
    (r'panna acida', 8, 0),
    (r'^panna', 6, 0),
    (r'latte di soia', 2, 0),
    (r'^latte', 1.6, 0),
    (r'yogurt greco', 6, 0),
    (r'^yogurt', 3.5, 125),
    (r'parmigiano', 22, 0),
    (r'grana', 16, 0),
    (r'ricotta salata', 14, 0),
    (r'^ricotta', 6, 0),
    (r'pecorino|casizolu', 18, 0),
    (r'mozzarell|fiordilatte', 9, 125),
    (r'stracciatella', 16, 0),
    (r'^feta', 12, 0),
    (r'gorgonzola', 12, 0),
    (r'philadelphia|formaggio spalmabile', 12, 0),
    (r'crescenza|stracchino', 9, 0),
    (r'cheddar|sottilette|formaggio fuso|edamer', 10, 20),
    (r'fontina|taleggio|provol|caciocavallo|scamorza|quartirolo|primosale|robiola|caprino|brie|asiago|toma\b|'
     r'casera|caciottina|formaggio', 14, 190),
    # carne e salumi
    (r'pollo intero', 5.5, 1500),
    (r'fusi di pollo|cosce di pollo', 6, 130),
    (r'pollo|tacchino', 11, 150),
    (r'macinat|spalla tritata', 11, 0),
    (r'carpaccio|controfiletto|filetto di manzo|noce di manzo', 32, 0),
    (r'vitello|manzo|cappello del prete|biancostato', 17, 0),
    (r'agnello', 15, 0),
    (r'costine', 8, 0),
    (r'maiale|lonza|carre', 9, 200),
    (r'salsiccia', 9, 100),
    (r'nduja', 25, 0),
    (r'guanciale', 15, 0),
    (r'pancetta|bacon', 15, 15),
    (r'speck', 22, 15),
    (r'prosciutto crudo', 30, 15),
    (r'prosciutto cotto', 20, 20),
    (r'bresaola', 35, 10),
    (r'salame', 22, 10),
    (r'pesteda', 30, 0),
    # pesce
    (r'bottarga', 150, 0),
    (r'salmone affumicato', 40, 0),
    (r'salmone', 22, 150),
    (r'pesce spada', 25, 150),
    (r'baccala', 20, 0),
    (r'stoccafisso', 35, 0),
    (r'polpo|polipetti', 15, 800),
    (r'calamar|seppie', 15, 150),
    (r'gamberi rossi|scampi', 42, 30),
    (r'gamberoni|mazzancolle', 22, 30),
    (r'gamber', 18, 20),
    (r'canocchie', 20, 30),
    (r'cozze', 4, 0),
    (r'vongole', 12, 0),
    (r'branzino|spigola|orata|ombrina', 14, 400),
    (r'merluzzo|nasello|platessa|trota|persico', 14, 150),
    (r'rana pescatrice', 25, 0),
    (r'triglie', 15, 80),
    (r'sgombro', 10, 300),
    (r'(acciughe|alici|sarde).*(sott.olio|sotto sale|dolci)|salsa alle acciughe', 50, 4),
    (r'acciughe|alici|sarde', 9, 30),
    (r'tonno sott.olio|^tonno$', 18, 0),
    (r'tonno', 30, 0),
    # condimenti e conserve
    (r'capperi|frutti di cappero', 20, 0),
    (r'olive taggiasche', 20, 0),
    (r'pate di olive', 15, 0),
    (r'^olive', 10, 4),
    (r'senape', 8, 0),
    (r'maionese', 6, 0),
    (r'ketchup', 4, 0),
    (r'salsa di soia', 8, 0),
    (r'worcestershire|tabasco|salsa piccante', 30, 0),
    (r'salsa barbecue', 7, 0),
    (r'mostarda', 15, 0),
    (r'brodo vegetale', 0.5, 0),
    (r'^brodo', 1, 0),
]
_COMPILATI = [(re.compile(rx), prezzo, pezzo) for rx, prezzo, pezzo in LISTINO]

# Unità della fonte -> grammi (o ml) per unità; «None» = peso di un pezzo dal listino.
GRAMMI_PER_UNITA = {
    'g': 1, 'kg': 1000, 'mg': 0.001, 'ml': 1, 'l': 1000,
    'spicchio': 5, 'spicchi': 5, 'cucchiai': 12, 'cucchiaini': 4, 'rametti': 3, 'foglie': 0.5,
    'pizzichi': 0.5, 'coste': 50, 'fette': 30, 'bicchieri': 200, 'ciuffi': 5, 'mazzetti': 20,
    'gocce': 0.05, 'tazze': 250, 'mestoli': 100, 'bacche': 0.3, 'vasetti': 125, 'confezioni': 250,
    'scatole': 400, 'barattoli': 400, 'cespi': 300, 'gambi': 50, 'stecche': 3, 'baccelli': 3,
    'noci': 10, 'fili': 3, 'tazzine': 50, 'manciate': 30,
    'pezzi': None, 'filetti': None, 'bustine': None, 'rotoli': None,
}
COPERTURA_MINIMA = 0.8


def _norm(nome):
    t = unicodedata.normalize('NFD', str(nome)).encode('ascii', 'ignore').decode().lower()
    t = re.sub(r'\([^)]*\)', ' ', t)  # «(da pulire)», «(2 da 550 g)»…
    return re.sub(r'\s+', ' ', t.replace('’', "'")).strip()


def voce_listino(nome):
    """(€/kg, peso pezzo g) dell'ingrediente, o None se non è nel listino."""
    n = _norm(nome)
    for rx, prezzo, pezzo in _COMPILATI:
        if rx.search(n):
            return prezzo, pezzo
    return None


def costo_ingrediente(nome, quantita, unita):
    """Euro per la quantità indicata; None se non stimabile (q.b. o prezzo ignoto)."""
    if not isinstance(quantita, (int, float)) or quantita <= 0:
        return None
    voce = voce_listino(nome)
    if voce is None:
        return None
    prezzo, pezzo = voce
    grammi = GRAMMI_PER_UNITA.get((unita or '').strip(), 'ignota')
    if grammi == 'ignota':
        return None
    if grammi is None:
        if not pezzo:
            return None  # prodotto che non si vende a pezzi: quantità non interpretabile
        grammi = pezzo
    return prezzo * quantita * grammi / 1000


def stima_ricetta(r):
    """{'porzione': €, 'totale': €, 'copertura': 0-1} o None se la stima non è affidabile."""
    porzioni = r.get('servings')
    if not isinstance(porzioni, (int, float)) or porzioni <= 0:
        return None
    totale, con_quantita, stimati = 0.0, 0, 0
    for ing in r.get('ingredients') or []:
        if not isinstance(ing, (list, tuple)) or len(ing) < 3:
            continue
        nome, q, u = ing[0], ing[1], ing[2]
        if not isinstance(q, (int, float)) or q <= 0:
            continue  # q.b. o quantità non indicata: fuori dal conto
        con_quantita += 1
        c = costo_ingrediente(nome, q, u)
        if c is not None:
            stimati += 1
            totale += c
    if not con_quantita:
        return None
    copertura = stimati / con_quantita
    if copertura < COPERTURA_MINIMA or totale <= 0:
        return None
    return {'porzione': round(totale / porzioni, 2), 'totale': round(totale, 2),
            'copertura': round(copertura, 2)}
