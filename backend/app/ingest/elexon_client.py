"""HTTP client for the two Elexon /stream endpoints.

Response shapes are pinned in docs/ASSUMPTIONS.md (A2-A7). Stdlib only.
"""
import http.client
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
# verified format for publishDateTimeFrom/To (ASSUMPTIONS A3)
TS_FORMAT = "%Y-%m-%dT%H:%MZ"


class ElexonError(RuntimeError):
    pass


def stream_url(dataset: str, frm: datetime, to: datetime) -> str:
    return (
        f"{BASE_URL}/datasets/{dataset}/stream"
        f"?publishDateTimeFrom={frm.strftime(TS_FORMAT)}&publishDateTimeTo={to.strftime(TS_FORMAT)}"
    )


def get_json(
    url: str,
    *,
    attempts: int = 5,
    timeout: float = 60,
    opener: Callable = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
):
    """GET and decode JSON. Retries 5xx and network/timeouts with exponential backoff; 4xx fails at once."""
    for attempt in range(1, attempts + 1):
        try:
            with opener(url, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                raise ElexonError(f"{url} -> HTTP {exc.code}") from exc
            reason = f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as exc:
            reason = type(exc).__name__
        if attempt == attempts:
            raise ElexonError(f"{url} failed after {attempts} attempts ({reason})")
        delay = 2 ** (attempt - 1)
        log(f"    retry {attempt}/{attempts - 1} in {delay}s ({reason})")
        sleep(delay)


def windows(lower: datetime, upper: datetime, chunk: timedelta) -> Iterator[tuple[datetime, datetime]]:
    a = lower
    while a < upper:
        b = min(a + chunk, upper)
        yield a, b
        a = b


def fetch(
    dataset: str,
    lower: datetime,
    upper: datetime,
    chunk_days: int = 7,
    workers: int = 4,
    log: Callable[[str], None] = print,
    **http_kwargs,
) -> list[dict]:
    """Every row published in [lower, upper], in chunks fetched concurrently.

    Elexon's publishDateTimeTo is inclusive (A4), so chunk edges overlap and the last
    chunk includes rows published exactly at `upper`. Callers dedupe and apply the
    exclusive upper bound themselves.
    """

    def one_chunk(window: tuple[datetime, datetime]) -> list[dict]:
        a, b = window
        t0 = time.monotonic()
        data = get_json(stream_url(dataset, a, b), log=log, **http_kwargs)
        if not isinstance(data, list):
            raise ElexonError(f"{dataset}: expected a bare JSON array (A2), got {type(data).__name__}")
        log(f"  {dataset:<7} {a.strftime(TS_FORMAT)} .. {b.strftime(TS_FORMAT)}  {len(data):>6,} rows  {time.monotonic() - t0:.1f}s")
        return data

    with ThreadPoolExecutor(max_workers=workers) as pool:
        parts = list(pool.map(one_chunk, windows(lower, upper, timedelta(days=chunk_days))))
    return [row for part in parts for row in part]
