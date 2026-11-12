"""Richieste HTTP condivise da importazione ricette e recupero immagini.

Un solo punto per User-Agent, limiti di dimensione, controllo dei redirect,
decodifica del charset e nuovi tentativi con attesa crescente sugli errori
temporanei (429, 5xx, timeout, connessione interrotta). Gli errori definitivi
(403, 404, 410, redirect fuori dominio) non vengono ritentati: non si
aggirano blocchi del sito.
"""
import gzip
import re
import socket
import time
import zlib
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

UA = 'CheffinoPersonalProject/0.1 (weekly recipe discovery; respects robots.txt)'
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}
MAX_HTML = 4_000_000


class FetchError(Exception):
    """Errore di acquisizione; ``transient`` indica se ha senso riprovare più tardi."""

    def __init__(self, message, status=None, transient=False):
        super().__init__(message)
        self.status = status
        self.transient = transient


def _same_site(a, b):
    ha, hb = (urlparse(a).hostname or '').lower(), (urlparse(b).hostname or '').lower()
    root = lambda h: '.'.join(h.split('.')[-2:])
    return ha == hb or root(ha) == root(hb)


def _decode(body, headers):
    encoding = (headers.get('Content-Encoding') or '').lower()
    if encoding == 'gzip':
        body = gzip.decompress(body)
    elif encoding == 'deflate':
        body = zlib.decompress(body)
    charset = None
    ctype = headers.get('Content-Type') or ''
    if m := re.search(r'charset=([\w-]+)', ctype, re.I):
        charset = m.group(1)
    if not charset and (m := re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', body[:4096], re.I)):
        charset = m.group(1).decode('ascii', 'ignore')
    try:
        return body.decode(charset or 'utf-8', 'replace')
    except LookupError:
        return body.decode('utf-8', 'replace')


def fetch_text(url, accept='text/html', max_bytes=MAX_HTML, timeout=25, attempts=3,
               backoff=4.0, opener=urlopen, sleep=time.sleep, same_host=True):
    """Scarica una pagina testuale con nuovi tentativi sugli errori temporanei."""
    last = None
    for attempt in range(1, attempts + 1):
        try:
            req = Request(url, headers={'User-Agent': UA, 'Accept': accept,
                                        'Accept-Language': 'it-IT,it;q=0.9'})
            with opener(req, timeout=timeout) as response:
                final = response.geturl()
                if same_host and not _same_site(final, url):
                    raise FetchError('Redirect fuori dal dominio previsto: ' + final)
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise FetchError('Pagina troppo grande')
                return _decode(body, response.headers)
        except HTTPError as exc:
            retry_after = exc.headers.get('Retry-After') if exc.headers else None
            last = FetchError(f'HTTP {exc.code}', exc.code, exc.code in RETRY_STATUS)
            if exc.code not in RETRY_STATUS:
                raise last from exc
            wait = float(retry_after) if retry_after and retry_after.isdigit() else backoff * attempt
        except (URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
            last = FetchError(f'Rete: {getattr(exc, "reason", exc)}', transient=True)
            wait = backoff * attempt
        if attempt < attempts:
            sleep(min(wait, 60))
    raise last
