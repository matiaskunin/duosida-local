# Security policy

Please report vulnerabilities privately through GitHub Security Advisories.
Do not include real device identifiers, network addresses, MAC addresses or
serial numbers in public reports.

The local charger protocol is unauthenticated and unencrypted in the observed
firmware. Keep the charger on a trusted/isolated LAN and restrict TCP 9988 and
UDP 48890/48899 to the Home Assistant host where practical.
