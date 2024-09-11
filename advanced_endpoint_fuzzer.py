import asyncio
import aiohttp
import argparse
import json
import logging
import signal
import sys
import time
import urllib.parse
from typing import Dict, List, Tuple, Optional
from aiohttp import ClientTimeout
from rich.console import Console
from rich.progress import Progress, TaskID
from rich.table import Table
from rich.logging import RichHandler

class EndpointFuzzer:
    def __init__(
        self,
        base_url: str,
        wordlist_path: Optional[str] = None,
        rate_limit: Optional[float] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 10,
        concurrency: int = 10,
        max_retries: int = 3,
        output_file: Optional[str] = None,
        verbose: bool = False,
        ignore_ssl: bool = False,
    ):
        self.base_url = base_url
        self.wordlist_path = wordlist_path
        self.rate_limit = rate_limit
        self.headers = headers or {}
        self.timeout = timeout
        self.concurrency = concurrency
        self.max_retries = max_retries
        self.output_file = output_file
        self.verbose = verbose
        self.ignore_ssl = ignore_ssl

        self.discovered_endpoints: List[str] = []
        self.unusual_endpoints: List[Tuple[str, int]] = []
        self.total_requests = 0
        self.failed_requests = 0
        self.retries = 0
        self.status_code_counts: Dict[int, int] = {}

        self.console = Console(force_terminal=True)
        self.progress: Optional[Progress] = None
        self.task_id: Optional[TaskID] = None
        self.start_time: float = 0

        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.INFO,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True, console=self.console)]
        )
        self.logger = logging.getLogger("endpoint_fuzzer")

    async def load_wordlist(self) -> List[str]:
        if self.wordlist_path:
            self.logger.info(f"Loading wordlist from {self.wordlist_path}")
            with open(self.wordlist_path, "r") as f:
                return f.read().splitlines()
        else:
            return await self.load_remote_wordlist()

    async def load_remote_wordlist(self) -> List[str]:
        seclists_url = "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/common.txt"
        self.logger.info(f"Fetching remote wordlist from {seclists_url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(seclists_url) as response:
                response.raise_for_status()
                text = await response.text()
                return text.splitlines()

    async def fuzz_endpoints(self):
        wordlist = await self.load_wordlist()
        self.logger.info(f"Starting fuzzing with {len(wordlist)} words")

        self.start_time = time.time()
        async with aiohttp.TCPConnector(ssl=not self.ignore_ssl) as connector:
            async with aiohttp.ClientSession(connector=connector) as session:
                semaphore = asyncio.Semaphore(self.concurrency)
                with Progress(console=self.console) as progress:
                    self.progress = progress
                    self.task_id = progress.add_task("[cyan]Fuzzing...", total=len(wordlist))
                    tasks = [self.test_endpoint(session, semaphore, word) for word in wordlist]
                    await asyncio.gather(*tasks)

        self.print_summary()

    async def test_endpoint(self, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, endpoint: str):
        async with semaphore:
            full_url = urllib.parse.urljoin(self.base_url, endpoint)
            for attempt in range(self.max_retries):
                try:
                    if self.rate_limit:
                        await asyncio.sleep(1 / self.rate_limit)
                    timeout = ClientTimeout(total=self.timeout)
                    async with session.get(full_url, headers=self.headers, timeout=timeout) as response:
                        await self.process_response(full_url, response.status)
                    break
                except aiohttp.ClientError as e:
                    if attempt == self.max_retries - 1:
                        self.handle_request_error(full_url, str(e))
                    else:
                        self.retries += 1
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff

    async def process_response(self, full_url: str, status_code: int):
        self.total_requests += 1
        self.status_code_counts[status_code] = self.status_code_counts.get(status_code, 0) + 1

        if status_code == 200:
            self.logger.info(f"Valid endpoint found: {full_url} (Status code: {status_code})")
            self.discovered_endpoints.append(full_url)
        elif status_code != 404:
            self.logger.warning(f"Unusual status code for {full_url} (Status code: {status_code})")
            self.unusual_endpoints.append((full_url, status_code))
        else:
            self.logger.debug(f"Invalid endpoint: {full_url} (Status code: {status_code})")

        if self.progress and self.task_id:
            self.progress.update(self.task_id, advance=1)

    def handle_request_error(self, full_url: str, error: str):
        self.total_requests += 1
        self.failed_requests += 1
        self.logger.error(f"Request failed for {full_url}: {error}")

    def print_summary(self):
        elapsed_time = time.time() - self.start_time
        self.console.print(f"\n[bold cyan]Fuzzing completed in {elapsed_time:.2f} seconds.")
        self.console.print(f"[cyan]Total requests: {self.total_requests}")
        self.console.print(f"[red]Failed requests: {self.failed_requests}")
        self.console.print(f"[yellow]Retries: {self.retries}")

        table = Table(title="Status Code Counts")
        table.add_column("Status Code", style="cyan")
        table.add_column("Count", style="magenta")
        for status_code, count in self.status_code_counts.items():
            table.add_row(str(status_code), str(count))
        self.console.print(table)

        if self.discovered_endpoints:
            self.console.print("[green]Found valid endpoints:")
            for endpoint in self.discovered_endpoints:
                self.console.print(f"[green]- {endpoint}")
        else:
            self.console.print("[red]No valid endpoints found.")

        if self.unusual_endpoints:
            self.console.print("[yellow]Unusual status codes:")
            for endpoint, status_code in self.unusual_endpoints:
                self.console.print(f"[yellow]{status_code}: {endpoint}")

        if self.output_file:
            self.save_results()

    def save_results(self):
        with open(self.output_file, "w") as f:
            json.dump({
                "discovered_endpoints": self.discovered_endpoints,
                "unusual_endpoints": self.unusual_endpoints,
                "status_code_counts": self.status_code_counts,
                "total_requests": self.total_requests,
                "failed_requests": self.failed_requests,
                "retries": self.retries
            }, f, indent=2)
        self.logger.info(f"Results saved to {self.output_file}")

def signal_handler(signum, frame):
    print("\nInterrupted by user. Exiting gracefully...")
    sys.exit(0)

async def main():
    parser = argparse.ArgumentParser(description="Advanced Endpoint Fuzzer")
    parser.add_argument("base_url", help="Base URL of the API to test")
    parser.add_argument("--wordlist", help="Path to the wordlist file")
    parser.add_argument("--rate-limit", type=float, help="Rate limit for requests (requests per second)")
    parser.add_argument("--headers", type=json.loads, help="Custom headers for requests (JSON format)")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout for requests in seconds")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent requests")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum number of retries for failed requests")
    parser.add_argument("--output", help="File to save discovered endpoints (JSON format)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--ignore-ssl", action="store_true", help="Ignore SSL certificate validation")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)

    fuzzer = EndpointFuzzer(
        base_url=args.base_url,
        wordlist_path=args.wordlist,
        rate_limit=args.rate_limit,
        headers=args.headers,
        timeout=args.timeout,
        concurrency=args.concurrency,
        max_retries=args.max_retries,
        output_file=args.output,
        verbose=args.verbose,
        ignore_ssl=args.ignore_ssl
    )

    await fuzzer.fuzz_endpoints()

if __name__ == "__main__":
    asyncio.run(main())
