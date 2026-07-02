#!/usr/bin/env python3
"""One-shot reader for the oracle debug_arbiter socket op (round-1 instrumentation)."""
import asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path("/home/volence/sonic_hacks/empyrean/clients/python")))
from aether import BusClient, BusError  # noqa: E402


async def main() -> None:
    bus = BusClient(client_id="wedgeprobe", client_name="wedge-probe", client_version="1",
                    want_events=False)
    await bus.connect()
    method = sys.argv[1] if len(sys.argv) > 1 else "emulator.debug_arbiter"
    try:
        result = await bus.call(method, {})
        print(json.dumps(result, indent=2, sort_keys=True))
    except BusError as e:
        print(f"BusError {e.code}: {e}", file=sys.stderr)
        sys.exit(2)


asyncio.run(main())
