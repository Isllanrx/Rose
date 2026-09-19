#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hashes Downloader
Downloads hashes.game.txt from CommunityDragon/Data repository
Checks for updates based on latest commit SHA
"""

import json
import requests
from pathlib import Path
from typing import IO, Optional, Dict
from utils.core.atomic_file import atomic_write
from utils.core.logging import get_logger
from config import APP_USER_AGENT, RATE_LIMIT_REQUEST_TIMEOUT

log = get_logger()

_DOWNLOAD_CHUNK_BYTES = 1 << 20
_HASHES_PART_COUNT = 9


class _HashesDownloadFailed(Exception):
    """A part failed mid-download, so the installed file must stay untouched."""

    def __init__(self, filename: str) -> None:
        super().__init__(filename)
        self.filename = filename


class _JoinedPartWriter:
    """Joins the downloaded parts with exactly one newline between them.

    Byte for byte the same output as the previous in-memory merge, which rstripped
    every part and joined them, but holding one chunk instead of four copies of the
    whole 230 MB file. Trailing newlines are held back rather than written, because
    only the following chunk says whether they are interior or trailing.
    """

    def __init__(self, handle: IO[bytes]) -> None:
        self._handle = handle
        self._held = b''
        self._part_index = 0
        self._last_byte = b''
        self.bytes_written = 0

    def _emit(self, data: bytes) -> None:
        if not data:
            return
        self._handle.write(data)
        self.bytes_written += len(data)
        self._last_byte = data[-1:]

    def start_part(self) -> None:
        if self._part_index:
            self._emit(b'\n')
        self._part_index += 1
        self._held = b''

    def feed(self, chunk: bytes) -> None:
        stripped = chunk.rstrip(b'\n')
        if stripped:
            self._emit(self._held)
            self._emit(stripped)
            self._held = chunk[len(stripped):]
        else:
            self._held += chunk

    def finish(self) -> None:
        if self.bytes_written and self._last_byte != b'\n':
            self._emit(b'\n')


class HashesDownloader:
    """Downloads and manages hashes.game.txt from CommunityDragon/Data repository"""
    
    def __init__(self, tools_dir: Path):
        self.tools_dir = tools_dir
        self.hashes_file = tools_dir / "hashes.game.txt"
        self.state_file = tools_dir / ".hashes_state.json"
        
        # GitHub repository info
        self.repo_owner = "CommunityDragon"
        self.repo_name = "Data"
        self.branch = "master"
        self.api_base = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}"
        self.raw_base = f"https://raw.githubusercontent.com/{self.repo_owner}/{self.repo_name}/{self.branch}"
        self.hashes_path = "hashes/lol"
        
        # Create session for API requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': APP_USER_AGENT,
            'Accept': 'application/vnd.github.v3+json'
        })
    
    def get_latest_commit_sha(self) -> Optional[str]:
        """Get the latest commit SHA for the hashes/lol directory"""
        try:
            # Get the latest commit that touched the hashes/lol directory
            # We'll check the commits API for commits that modified files in this path
            response = self.session.get(
                f"{self.api_base}/commits",
                params={'sha': self.branch, 'path': self.hashes_path, 'per_page': 1},
                timeout=RATE_LIMIT_REQUEST_TIMEOUT
            )
            response.raise_for_status()
            commits = response.json()
            
            if commits and len(commits) > 0:
                latest_sha = commits[0]['sha']
                log.debug(f"Latest commit SHA for {self.hashes_path}: {latest_sha[:8]}")
                return latest_sha
            
            log.warning(f"No commits found for path {self.hashes_path}")
            return None
            
        except requests.HTTPError as e:
            if e.response and e.response.status_code in (403, 429):
                log.warning(f"GitHub API rate limit exceeded: {e}")
                return None
            else:
                log.error(f"Failed to get latest commit SHA: {e}")
                return None
        except requests.RequestException as e:
            log.error(f"Failed to get latest commit SHA: {e}")
            return None
    
    def load_local_state(self) -> Dict:
        """Load local state from state file"""
        if not self.state_file.exists():
            return {}
        
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            log.warning(f"Failed to load local state: {e}")
            return {}
    
    def save_local_state(self, state: Dict):
        """Save local state to state file"""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except IOError as e:
            log.warning(f"Failed to save local state: {e}")
    
    def has_hashes_changed(self) -> bool:
        """Check if hashes have changed since last update"""
        local_state = self.load_local_state()
        if not local_state:
            log.info("No local state found, hashes will be downloaded")
            return True
        
        # Check if file exists
        if not self.hashes_file.exists():
            log.info("hashes.game.txt not found, will download")
            return True
        
        # Get latest commit SHA
        latest_sha = self.get_latest_commit_sha()
        if not latest_sha:
            # If we can't get the SHA, assume no changes (to avoid unnecessary downloads)
            log.warning("Could not get latest commit SHA, assuming no changes")
            return False
        
        # Compare with local state
        local_sha = local_state.get('last_commit_sha')
        if local_sha != latest_sha:
            log.info(f"Hashes changed: {local_sha[:8] if local_sha else 'None'} -> {latest_sha[:8]}")
            return True
        
        log.debug("Hashes unchanged, skipping download")
        return False
    
    def _stream_hashes_file(self, filename: str, writer: "_JoinedPartWriter") -> bool:
        """Stream one hashes part straight into *writer*, never holding it in memory."""
        url = f"{self.raw_base}/{self.hashes_path}/{filename}"

        try:
            log.info(f"Downloading {filename}...")
            start = writer.bytes_written
            with self.session.get(
                url, timeout=RATE_LIMIT_REQUEST_TIMEOUT, stream=True
            ) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=_DOWNLOAD_CHUNK_BYTES):
                    if chunk:
                        writer.feed(chunk)
            log.info(f"Downloaded {filename} ({writer.bytes_written - start} bytes)")
            return True
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                log.error(f"File not found: {filename}")
            elif e.response is not None and e.response.status_code in (403, 429):
                log.error(f"GitHub API rate limit exceeded while downloading {filename}")
            else:
                log.error(f"Failed to download {filename}: {e}")
            return False
        except requests.RequestException as e:
            log.error(f"Failed to download {filename}: {e}")
            return False

    def download_and_merge_hashes(self) -> bool:
        """Download every hashes part and write them out as a single file."""
        try:
            self.tools_dir.mkdir(parents=True, exist_ok=True)

            # durable=False per ADR-006: the state file is only written after the
            # swap, so an interrupted download is simply redone on the next run.
            with atomic_write(self.hashes_file, "wb", durable=False) as handle:
                writer = _JoinedPartWriter(handle)
                for index in range(_HASHES_PART_COUNT):
                    writer.start_part()
                    if not self._stream_hashes_file(f"hashes.game.txt.{index}", writer):
                        raise _HashesDownloadFailed(f"hashes.game.txt.{index}")
                writer.finish()
                total_bytes = writer.bytes_written

            log.info(f"Successfully created hashes.game.txt ({total_bytes} bytes)")

            latest_sha = self.get_latest_commit_sha()
            if latest_sha:
                self.save_local_state({
                    'last_commit_sha': latest_sha,
                    'file_size': total_bytes,
                })

            return True

        except _HashesDownloadFailed as e:
            log.error(f"Failed to download {e.filename}; keeping the previous hashes file")
            return False
        except Exception as e:
            log.error(f"Failed to download and merge hashes: {e}")
            return False
    
    def ensure_hashes_file(self) -> bool:
        """Ensure hashes.game.txt exists and is up to date"""
        try:
            # Check if file needs to be downloaded/updated
            if self.has_hashes_changed():
                log.info("Updating hashes.game.txt...")
                return self.download_and_merge_hashes()
            else:
                log.debug("hashes.game.txt is up to date")
                return True
                
        except Exception as e:
            log.error(f"Failed to ensure hashes file: {e}")
            return False


def ensure_hashes_file(tools_dir: Path) -> bool:
    """
    Ensure hashes.game.txt exists in the tools directory and is up to date.
    
    Args:
        tools_dir: Path to the injection/tools directory
        
    Returns:
        True if the file exists and is up to date, False otherwise
    """
    downloader = HashesDownloader(tools_dir)
    return downloader.ensure_hashes_file()

