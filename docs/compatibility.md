# Compatibility matrix

Hardware under test: DUOSIDA SES-32-ORW, 230 V, 32 A, 7.2 kW, single phase.
Private identifiers are intentionally omitted.

| Capability | Automated fixture | Physical result | Status |
|---|---:|---|---|
| TCP identification | Yes | Previously observed | Verified |
| Identity and firmware | Yes | Previously captured | Verified |
| Available telemetry | Yes | Previously captured | Verified |
| Charging telemetry near 6 A | Yes | Previously captured | Verified |
| Charging telemetry near 16 A | Yes | Previously captured | Verified |
| Vehicle connected / stopped | Yes | Previously captured | Verified |
| Fragmented/concatenated TCP | Yes | Capture-derived stream | Verified offline |
| UDP discovery | Yes (mock network) | Pending | Experimental |
| Set current 6 A | Exact-byte test | Pending | Experimental |
| Set current 16 A | Exact-byte test | Pending | Experimental |
| Start charging | Exact-byte/state test | Pending | Experimental |
| Stop charging | Exact-byte/state test | Pending | Experimental |
| Charger restart/reconnect | Simulated | Pending | Experimental |
| Internet blocked, LAN retained | N/A | Pending | Experimental |

Other models are not verified. Contributors should add sanitized evidence and a
repeatable result before changing this table.
