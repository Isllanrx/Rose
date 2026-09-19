#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UDP Transport Layer
Handles UDP socket operations with NAT hole punching
"""

import asyncio
import socket
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Tuple

from utils.core.logging import get_logger

log = get_logger()

# Hole punching configuration
HOLE_PUNCH_TIMEOUT = 60.0          # total time to keep punching (seconds)
HOLE_PUNCH_BURST_COUNT = 10        # fast initial burst packet count
HOLE_PUNCH_BURST_INTERVAL = 0.3    # seconds between burst packets
HOLE_PUNCH_SUSTAINED_INTERVAL = 1.5  # seconds between sustained packets
HOLE_PUNCH_RECV_TIMEOUT = 0.8      # wait for reply per iteration

# Keepalive configuration
KEEPALIVE_INTERVAL = 15.0  # seconds
KEEPALIVE_TIMEOUT = 45.0   # consider dead after this


@dataclass
class PeerEndpoint:
    """Represents a peer's network endpoint"""
    external_ip: str
    external_port: int
    internal_ip: str
    internal_port: int
    last_seen: float = 0.0
    is_lan: bool = False

    def get_addresses(self) -> list[Tuple[str, int]]:
        """Get list of addresses to try (external first, then internal for LAN)"""
        addrs = [(self.external_ip, self.external_port)]
        # Only try internal if it's a real LAN address (0.0.0.0 is invalid to send to)
        if self.internal_ip and self.internal_ip != "0.0.0.0" and self.internal_ip != self.external_ip:
            addrs.append((self.internal_ip, self.internal_port))
        return addrs


class UDPTransport:
    """Async UDP transport with hole punching support"""

    def __init__(self, local_port: int = 0):
        """Initialize UDP transport

        Args:
            local_port: Local port to bind to (0 for auto-assign)
        """
        self._local_port = local_port
        self._socket: Optional[socket.socket] = None
        self._bound = False
        self._receive_task: Optional[asyncio.Task] = None
        self._running = False

        # Message handlers by source address
        self._handlers: Dict[Tuple[str, int], Callable[[bytes, Tuple[str, int]], None]] = {}
        self._default_handler: Optional[Callable[[bytes, Tuple[str, int]], None]] = None

        # Pending receives (for hole punching)
        self._pending_receives: asyncio.Queue = asyncio.Queue()

    @property
    def local_port(self) -> int:
        """Get the bound local port"""
        return self._local_port

    @property
    def local_address(self) -> Tuple[str, int]:
        """Get the local address"""
        if self._socket:
            return self._socket.getsockname()
        return ("0.0.0.0", self._local_port)

    async def bind(self) -> int:
        """Bind to local port

        Returns:
            The bound port number
        """
        if self._bound:
            return self._local_port

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setblocking(False)

        # Allow address reuse
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind to specified port (or 0 for auto-assign)
        self._socket.bind(("0.0.0.0", self._local_port))

        # Get assigned port
        self._local_port = self._socket.getsockname()[1]
        self._bound = True

        log.info(f"[UDP] Bound to port {self._local_port}")
        return self._local_port

    def get_socket(self) -> Optional[socket.socket]:
        """Get the underlying socket (for STUN client)"""
        return self._socket

    async def start_receiving(self):
        """Start the receive loop"""
        if self._running:
            return

        if not self._bound:
            await self.bind()

        self._running = True
        self._receive_task = asyncio.create_task(self._receive_loop())
        log.debug("[UDP] Receive loop started")

    async def stop(self):
        """Stop the transport"""
        self._running = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:  # silent-ok: cancellation is the normal shutdown path
                pass
            self._receive_task = None

        if self._socket:
            self._socket.close()
            self._socket = None

        self._bound = False
        log.info("[UDP] Transport stopped")

    async def send(self, data: bytes, addr: Tuple[str, int]):
        """Send UDP packet

        Args:
            data: Data to send
            addr: Destination (ip, port) tuple
        """
        if not self._socket:
            raise RuntimeError("Transport not bound")

        loop = asyncio.get_event_loop()
        try:
            await loop.sock_sendto(self._socket, data, addr)
        except Exception as e:
            log.warning(f"[UDP] Send failed to {addr}: {e}")
            raise

    async def recv(self, timeout: float = 5.0) -> Tuple[bytes, Tuple[str, int]]:
        """Receive a UDP packet with timeout

        Args:
            timeout: Timeout in seconds

        Returns:
            Tuple of (data, (ip, port))

        Raises:
            asyncio.TimeoutError: If no packet received within timeout
        """
        try:
            return await asyncio.wait_for(
                self._pending_receives.get(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise

    def put_back(self, data: bytes, addr: Tuple[str, int]):
        """Put a packet back for a later recv() (e.g. wrong peer)"""
        self._pending_receives.put_nowait((data, addr))

    def set_handler(self, addr: Tuple[str, int], handler: Callable[[bytes, Tuple[str, int]], None]):
        """Set handler for packets from specific address"""
        self._handlers[addr] = handler

    def remove_handler(self, addr: Tuple[str, int]):
        """Remove handler for specific address"""
        self._handlers.pop(addr, None)

    def set_default_handler(self, handler: Callable[[bytes, Tuple[str, int]], None]):
        """Set default handler for unmatched packets"""
        self._default_handler = handler

    async def hole_punch(
        self,
        endpoint: PeerEndpoint,
        punch_data: bytes = b"PUNCH",
        timeout: float = HOLE_PUNCH_TIMEOUT,
    ) -> Optional[Tuple[str, int]]:
        """Attempt UDP hole punching to establish connection.

        Punches ALL addresses in parallel (external + internal simultaneously)
        and keeps retrying for up to `timeout` seconds so both sides have time
        to start punching.

        Args:
            endpoint: Peer endpoint to punch through to
            punch_data: Data to send in punch packets
            timeout: Total seconds to keep trying (default 60)

        Returns:
            Working address (ip, port) or None if punching failed
        """
        if not self._socket:
            await self.bind()

        addresses = endpoint.get_addresses()
        all_peer_ips = {endpoint.external_ip, endpoint.internal_ip}
        log.info(f"[UDP] Starting parallel hole punch to {len(addresses)} address(es) (timeout={timeout}s)")

        result: list = [None]
        success_event = asyncio.Event()

        # Launch one puncher task per address, all run simultaneously
        tasks = []
        for addr in addresses:
            task = asyncio.create_task(
                self._punch_one_address(addr, all_peer_ips, punch_data, success_event, result)
            )
            tasks.append(task)

        try:
            await asyncio.wait_for(success_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:  # silent-ok: no reply before the timeout is the expected failure; the caller checks success
            pass

        # Cancel all tasks
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        if result[0]:
            log.info(f"[UDP] Hole punch successful! Connected via {result[0]}")
        else:
            log.warning(f"[UDP] Hole punch failed after {timeout}s")
        return result[0]

    async def _punch_one_address(
        self,
        addr: Tuple[str, int],
        all_peer_ips: set,
        punch_data: bytes,
        success_event: asyncio.Event,
        result: list,
    ):
        """Punch a single address: fast burst then sustained pings until success or cancelled."""
        log.info(f"[UDP] Punching {addr}")
        packet_num = 0

        try:
            while not success_event.is_set():
                packet_num += 1

                # Send punch packet
                try:
                    await self.send(punch_data, addr)
                    if packet_num <= HOLE_PUNCH_BURST_COUNT or packet_num % 10 == 0:
                        log.debug(f"[UDP] Sent punch #{packet_num} to {addr}")
                except Exception as e:
                    log.debug(f"[UDP] Punch send to {addr} failed: {e}")

                # Choose interval: fast burst first, then slower sustained
                interval = HOLE_PUNCH_BURST_INTERVAL if packet_num <= HOLE_PUNCH_BURST_COUNT else HOLE_PUNCH_SUSTAINED_INTERVAL
                await asyncio.sleep(interval)

                # Check for response from any peer address
                try:
                    data, recv_addr = await asyncio.wait_for(
                        self._pending_receives.get(),
                        timeout=HOLE_PUNCH_RECV_TIMEOUT,
                    )

                    if recv_addr[0] in all_peer_ips:
                        # Got a response from the peer
                        if not data.startswith(b"PUNCH"):
                            await self._pending_receives.put((data, recv_addr))
                        result[0] = recv_addr
                        success_event.set()
                        return

                    # Not from expected peer, put back
                    await self._pending_receives.put((data, recv_addr))
                except asyncio.TimeoutError:  # silent-ok: receive timeout; the punch loop retries
                    continue

        except asyncio.CancelledError:  # silent-ok: cancellation is the normal shutdown path
            return

    async def _receive_loop(self):
        """Background loop to receive packets"""
        loop = asyncio.get_event_loop()

        while self._running and self._socket:
            try:
                data, addr = await loop.sock_recvfrom(self._socket, 65535)

                # Reply to PUNCH so hole punch succeeds (other side gets a response)
                if data.startswith(b"PUNCH"):
                    try:
                        await self.send(data, addr)
                        log.debug(f"[UDP] Sent punch reply to {addr}")
                    except Exception as e:
                        log.debug(f"[UDP] Punch reply failed: {e}")

                # Check for specific handler
                handler = self._handlers.get(addr)
                if handler:
                    try:
                        handler(data, addr)
                    except Exception as e:
                        log.warning(f"[UDP] Handler error for {addr}: {e}")
                elif self._default_handler:
                    try:
                        self._default_handler(data, addr)
                    except Exception as e:
                        log.warning(f"[UDP] Default handler error: {e}")
                else:
                    # Queue for recv() calls (e.g. hole punch initiator waiting for reply)
                    await self._pending_receives.put((data, addr))

            except asyncio.CancelledError:  # silent-ok: cancellation is the normal shutdown path
                break
            except Exception as e:
                if self._running:
                    log.debug(f"[UDP] Receive error: {e}")
                await asyncio.sleep(0.1)

        log.debug("[UDP] Receive loop ended")


class UDPProtocol(asyncio.DatagramProtocol):
    """Alternative asyncio-native UDP protocol"""

    def __init__(self):
        self.transport: Optional[asyncio.DatagramTransport] = None
        self._receive_queue: asyncio.Queue = asyncio.Queue()
        self._handlers: Dict[Tuple[str, int], Callable] = {}
        self._default_handler: Optional[Callable] = None

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        handler = self._handlers.get(addr)
        if handler:
            handler(data, addr)
        elif self._default_handler:
            self._default_handler(data, addr)
        else:
            self._receive_queue.put_nowait((data, addr))

    def error_received(self, exc: Exception):
        log.warning(f"[UDP] Protocol error: {exc}")

    def connection_lost(self, exc: Optional[Exception]):
        if exc:
            log.warning(f"[UDP] Connection lost: {exc}")
