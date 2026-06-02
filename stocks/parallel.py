"""
Shared concurrency helper for I/O-bound ticker fetches.

yfinance / Finviz / stockanalysis lookups are network-bound: each ticker spends
almost all of its time waiting on HTTP, so running them on a thread pool turns a
linear O(n) wall-clock cost into a near-constant one. Each yf.Ticker object is
independent, so this is safe to parallelize.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, List, Optional, TypeVar

T = TypeVar("T")  # input item (e.g. a ticker, or a (ticker, label) tuple)
R = TypeVar("R")  # fetch result (e.g. SectorStock / HiddenGem)

# yfinance is rate-limited; 8 workers keeps us fast without tripping throttling.
DEFAULT_WORKERS = 8


def parallel_fetch(
    items: Iterable[T],
    worker: Callable[[T], Optional[R]],
    max_workers: int = DEFAULT_WORKERS,
    progress: Optional[Callable[[int, int], None]] = None,
) -> List[R]:
    """
    Run ``worker(item)`` across ``items`` concurrently and collect the non-None
    results. Result order is NOT guaranteed; callers that need a specific order
    (e.g. ranking by quant score) sort afterwards, which every current caller
    already does.

    ``progress(done, total)`` — if supplied — is invoked after each item
    completes so callers can render a live counter.
    """
    items = list(items)
    total = len(items)
    if total == 0:
        return []

    results: List[R] = []
    done = 0
    with ThreadPoolExecutor(max_workers=min(max_workers, total)) as pool:
        futures = {pool.submit(worker, item): item for item in items}
        for future in as_completed(futures):
            try:
                res = future.result()
            except Exception:
                res = None  # worker already fails soft, but never let one kill the batch
            if res is not None:
                results.append(res)
            done += 1
            if progress is not None:
                progress(done, total)
    return results
