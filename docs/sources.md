# Sources and attribution

Primary and corroborating material used during research:

- [DUOSIDA SES-32-ORW datasheet](https://alumifixsolar.com.br/wp-content/uploads/2022/02/Datasheet-carregadores-veiculares-7kW11kW.pdf)
- [Vendor local Wi-Fi app manual](https://chongdianbei.x-cheng.com/apk/doc/SmartChargeAPPManual.pdf)
- [TÜV test report for SES-32 / SEL-32](https://www.eautotoltokabel.hu/wp-content/uploads/2020/10/EV-wall-charger-TUV-test-report.pdf)
- [americodias/duosida-ev](https://github.com/americodias/duosida-ev), an
  MIT-licensed independent implementation used only to corroborate discovery
  and command hypotheses. No source code was copied.
- [Public OCPP trace for related UCHEN/DUOSIDA firmware](https://github.com/evcc-io/evcc/discussions/28841),
  used to corroborate that `VendorMaxWorkCurrent` is exposed with two decimal
  places. This does not replace physical validation on the SES-32-ORW.
- [jello1974/duosidaEV-home-assistant](https://github.com/jello1974/duosidaEV-home-assistant),
  a cloud-based integration used only to compare state labels. It is not a
  runtime dependency and its cloud transport is not reused.

The decisive telemetry evidence is a set of private, locally captured charger
sessions. Public fixtures are length-preserving sanitized derivatives.
