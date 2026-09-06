"""High-level asynchronous charger client."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from dataclasses import replace

from .codec import (
    build_set_max_current,
    build_start_command,
    build_stop_command,
    parse_identity,
    parse_status,
    parse_text_telemetry,
)
from .exceptions import (
    DuosidaCommandError,
    DuosidaCommandUnconfirmedError,
    DuosidaConnectionError,
    DuosidaProtocolError,
)
from .models import (
    ChargerIdentity,
    ChargerState,
    ChargerStatus,
    CommandReceipt,
    CommandStatus,
)
from .transport import DuosidaTransport

StateCallback = Callable[[ChargerStatus], None | Awaitable[None]]


class DuosidaClient:
    """Maintain one local connection and expose decoded state and commands."""

    def __init__(
        self,
        host: str,
        port: int = 9988,
        *,
        timeout: float = 5.0,
        command_timeout: float = 15.0,
        transport: DuosidaTransport | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.command_timeout = command_timeout
        self._transport = transport or DuosidaTransport(host, port, timeout=timeout)
        self._identity: ChargerIdentity | None = None
        self._status: ChargerStatus | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._reader_error: BaseException | None = None
        self._callbacks: set[StateCallback] = set()
        self._subscribers: set[asyncio.Queue[ChargerStatus | BaseException]] = set()
        self._command_lock = asyncio.Lock()
        self._status_condition = asyncio.Condition()
        self._sequence = int(time.monotonic() * 1000) & 0x0FFFFFFF

    async def __aenter__(self) -> DuosidaClient:
        await self.connect()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.disconnect()

    @property
    def connected(self) -> bool:
        """Return whether the TCP stream and reader task are active."""

        return (
            self._transport.connected
            and self._reader_task is not None
            and not self._reader_task.done()
        )

    @property
    def device_id(self) -> str | None:
        """Discovered device identifier."""

        return self._transport.device_id

    @property
    def latest_status(self) -> ChargerStatus | None:
        """Latest state snapshot without performing I/O."""

        return self._status

    async def connect(self) -> ChargerIdentity:
        """Connect and wait for the first identity message."""

        if self.connected and self._identity is not None:
            return self._identity
        self._reader_error = None
        await self._transport.connect()
        self._reader_task = asyncio.create_task(
            self._read_loop(), name=f"duosida-local-{self.host}"
        )
        try:
            async with asyncio.timeout(self.timeout):
                async with self._status_condition:
                    await self._status_condition.wait_for(
                        lambda: self._identity is not None or self._reader_error is not None
                    )
        except TimeoutError as err:
            await self.disconnect()
            raise DuosidaProtocolError("charger did not announce identity") from err
        if self._reader_error is not None:
            error = self._reader_error
            await self.disconnect()
            if isinstance(error, DuosidaConnectionError | DuosidaProtocolError):
                raise error
            raise DuosidaConnectionError("reader stopped during connection") from error
        if self._identity is None:
            raise DuosidaProtocolError("identity wait ended without identity")
        return self._identity

    async def disconnect(self) -> None:
        """Stop background work and close TCP cleanly."""

        task, self._reader_task = self._reader_task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await self._transport.disconnect()
        self._identity = None
        self._status = None

    async def get_identity(self) -> ChargerIdentity:
        """Return cached identity, connecting if required."""

        if self._identity is None:
            return await self.connect()
        return self._identity

    def add_state_callback(self, callback: StateCallback) -> Callable[[], None]:
        """Register a callback and return an unsubscribe function."""

        self._callbacks.add(callback)
        return lambda: self._callbacks.discard(callback)

    async def states(self) -> AsyncIterator[ChargerStatus]:
        """Yield push updates for one subscriber."""

        queue: asyncio.Queue[ChargerStatus | BaseException] = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        if self._status is not None:
            queue.put_nowait(self._status)
        try:
            while True:
                item = await queue.get()
                if isinstance(item, BaseException):
                    raise item
                yield item
        finally:
            self._subscribers.discard(queue)

    async def start_charging(self) -> CommandReceipt:
        """Send remote start and confirm a transition to CHARGING."""

        async with self._command_lock:
            sequence = self._next_sequence()
            await self._send_command(build_start_command(self._device_id_required(), sequence))
            status = await self._wait_for_state(lambda value: value.state is ChargerState.CHARGING)
            return CommandReceipt(
                "start", CommandStatus.CONFIRMED, sequence, observed_state=status.state
            )

    async def stop_charging(self) -> CommandReceipt:
        """Send remote stop and confirm that active charging ended."""

        async with self._command_lock:
            sequence = self._next_sequence()
            session_id = int(time.time() * 1000) & 0xFFFFFFFF
            await self._send_command(
                build_stop_command(self._device_id_required(), sequence, session_id)
            )
            status = await self._wait_for_state(
                lambda value: value.state is not ChargerState.CHARGING
            )
            return CommandReceipt(
                "stop", CommandStatus.CONFIRMED, sequence, observed_state=status.state
            )

    async def set_max_current(self, amps: int) -> CommandReceipt:
        """Set 6-32 A and report the protocol's write-only confirmation level."""

        async with self._command_lock:
            sequence = self._next_sequence()
            try:
                command = build_set_max_current(self._device_id_required(), sequence, amps)
            except ValueError as err:
                raise DuosidaCommandError(str(err)) from err
            await self._send_command(command)
            return CommandReceipt(
                "set_max_current",
                CommandStatus.SENT_UNCONFIRMED,
                sequence,
                requested_value=amps,
            )

    async def _read_loop(self) -> None:
        try:
            async for message in self._transport.messages():
                identity = parse_identity(message)
                if identity is not None:
                    self._identity = identity
                    async with self._status_condition:
                        self._status_condition.notify_all()
                status = parse_status(message)
                if status is not None:
                    await self._publish(status)
                    continue
                telemetry = parse_text_telemetry(message)
                if telemetry is not None and self._status is not None:
                    await self._publish(
                        replace(
                            self._status,
                            voltage=telemetry.voltage,
                            current=telemetry.current,
                            power=telemetry.power,
                            station_temperature=telemetry.station_temperature,
                        )
                    )
        except asyncio.CancelledError:
            raise
        except BaseException as err:
            self._reader_error = err
            async with self._status_condition:
                self._status_condition.notify_all()
            for queue in tuple(self._subscribers):
                self._replace_queue_item(queue, err)

    async def _publish(self, status: ChargerStatus) -> None:
        self._status = status
        async with self._status_condition:
            self._status_condition.notify_all()
        for queue in tuple(self._subscribers):
            self._replace_queue_item(queue, status)
        for callback in tuple(self._callbacks):
            result = callback(status)
            if result is not None:
                await result

    @staticmethod
    def _replace_queue_item(
        queue: asyncio.Queue[ChargerStatus | BaseException], item: ChargerStatus | BaseException
    ) -> None:
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(item)

    async def _send_command(self, command: bytes) -> None:
        if not self.connected:
            raise DuosidaConnectionError("charger is not connected")
        try:
            await self._transport.write(command)
        except DuosidaConnectionError:
            raise
        except Exception as err:
            raise DuosidaCommandError("could not send command") from err

    async def _wait_for_state(self, predicate: Callable[[ChargerStatus], bool]) -> ChargerStatus:
        if self._status is not None and predicate(self._status):
            return self._status
        try:
            async with asyncio.timeout(self.command_timeout):
                async with self._status_condition:
                    await self._status_condition.wait_for(
                        lambda: (self._status is not None and predicate(self._status))
                        or self._reader_error is not None
                    )
        except TimeoutError as err:
            raise DuosidaCommandUnconfirmedError(
                "command was sent but no compatible state transition was observed"
            ) from err
        if self._reader_error is not None:
            raise DuosidaCommandUnconfirmedError("connection ended before command confirmation")
        if self._status is None:
            raise DuosidaCommandUnconfirmedError("no status available for command confirmation")
        return self._status

    def _device_id_required(self) -> str:
        if self.device_id is None:
            raise DuosidaConnectionError("charger is not connected")
        return self.device_id

    def _next_sequence(self) -> int:
        value = self._sequence
        self._sequence = (self._sequence + 1) & 0xFFFFFFFF
        return value
