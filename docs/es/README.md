# Guía en español

`duosida-local` se comunica directamente por la red local con cargadores
compatibles. No inicia sesión en DSCharge ni consulta servicios en la nube.

La compatibilidad inicial se limita al DUOSIDA SES-32-ORW que se pudo observar
físicamente. La lectura de identidad, firmware y telemetría está respaldada por
capturas reales. Descubrimiento UDP, start, stop y límite de corriente siguen
siendo experimentales hasta completar la matriz física.

## Instalación de desarrollo

```powershell
uv sync --locked --all-groups
uv run pytest
```

## Uso básico

```python
async with DuosidaClient("IP_DEL_CARGADOR") as charger:
    print(await charger.get_identity())
    async for estado in charger.states():
        print(estado)
```

## Precauciones

- Probar primero con 6 A.
- No superar la capacidad de la instalación eléctrica.
- Usar una LAN confiable o una VLAN aislada: el protocolo local no cifra el
  tráfico.
- `set_max_current()` sólo confirma el envío; el cargador no devuelve el valor
  almacenado en las capturas disponibles.
- No compartir fotos ni capturas originales con identificadores privados.

La documentación técnica canónica está en inglés: [arquitectura](../architecture.md),
[protocolo](../protocol.md) y [compatibilidad](../compatibility.md).
