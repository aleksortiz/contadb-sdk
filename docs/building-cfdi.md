# Construcción de CFDI 4.0

Esta guía cubre los detalles del builder: qué campos calcula automáticamente,
qué casos especiales maneja, y cómo trabajar con escenarios complejos.

## Tasas como decimales

El SDK usa **decimales** para tasas, no porcentajes. `0.16` significa 16%.

```python
Concepto(..., tasa_iva=Decimal("0.16"))    # ✅ Correcto: 16%
Concepto(..., tasa_iva=Decimal("16"))      # ❌ Mal: 1600%
```

Siempre usa `Decimal` (no `float`) para evitar errores de redondeo en
matemática binaria.

## Cálculos automáticos

Por cada concepto:

```
Importe       = Cantidad × ValorUnitario       (redondeado a 2 dec)
Base impuesto = Importe - (Descuento o 0)
Importe IVA   = Base × tasa_iva                (si tasa_iva != None)
Importe IEPS  = Base × tasa_ieps               (si tasa_ieps > 0)
Importe ret.  = Base × tasa_retencion_*        (cada retención)
```

Por comprobante:

```
SubTotal                       = Σ Importe
Descuento (atributo opcional)  = Σ Descuento  (solo si > 0)
TotalImpuestosTrasladados      = Σ Importe traslados
TotalImpuestosRetenidos        = Σ Importe retenciones
Total                          = SubTotal - Descuento + TotalTrasladados - TotalRetenidos
```

El bloque `<cfdi:Impuestos>` se construye consolidado por `(Impuesto, TipoFactor, TasaOCuota)`.

## Casos especiales

### IVA Exento

```python
Concepto(
    clave_prod_serv="...",
    clave_unidad="...",
    descripcion="Producto exento de IVA",
    cantidad=Decimal("1"),
    valor_unitario=Decimal("100"),
    iva_exento=True,  # genera <Traslado TipoFactor="Exento" Base="100"/>
)
```

### IVA tasa 0%

```python
Concepto(..., tasa_iva=Decimal("0"))
# Genera <Traslado Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.000000" Importe="0.00"/>
```

### Sin IVA (no objeto)

```python
Concepto(..., objeto_imp="01")
# objeto_imp="01" prohíbe tasas y retenciones — el validator de Pydantic
# rechaza la combinación con IVA/retenciones.
```

### Retención de honorarios profesionales

Personas físicas con actividad empresarial que facturan a personas morales:

```python
Concepto(
    ...,
    tasa_iva=Decimal("0.16"),                   # 16%
    tasa_retencion_isr=Decimal("0.10"),         # 10%
    tasa_retencion_iva=Decimal("0.106667"),     # 2/3 del IVA
)
```

### Moneda extranjera

Requiere `tipo_cambio`:

```python
CFDIBuilder(
    ...,
    moneda="USD",
    tipo_cambio=Decimal("17.5234"),
)
```

### Factura global (público en general)

```python
from contadb_sdk import (
    InformacionGlobal,
    RFC_PUBLICO_GENERAL, NOMBRE_PUBLICO_GENERAL,
    USO_PUBLICO_GENERAL, REGIMEN_SIN_OBLIGACIONES,
)

builder = CFDIBuilder(
    ...,
    receptor=Receptor(
        rfc=RFC_PUBLICO_GENERAL,
        nombre=NOMBRE_PUBLICO_GENERAL,
        uso_cfdi=USO_PUBLICO_GENERAL,
        domicilio_fiscal_receptor=lugar_expedicion,  # Mismo CP del emisor
        regimen_fiscal_receptor=REGIMEN_SIN_OBLIGACIONES,
    ),
    informacion_global=InformacionGlobal(
        periodicidad="04",  # Mensual
        meses="04",         # Abril
        año=2026,
    ),
)
```

## Inspeccionar el XML antes de firmar

```python
xml_bytes = builder.construir_xml()  # sin sello
print(xml_bytes.decode("utf-8"))
```

## Inspeccionar la cadena original

```python
from contadb_sdk import cadena_original

cadena = cadena_original(builder.construir_xml())
print(cadena)
# ||4.0|A|1|2026-04-26T12:00:00|03||1000.00|MXN|1160.00|I|01|...||
```

## Verificación cruzada cert ↔ emisor

El builder verifica que el RFC extraído del certificado coincide con el del
emisor. Si no, lanza `ValidationError`. Esto evita firmar comprobantes con
un certificado que no corresponde al emisor declarado.

## Limitaciones de v1.0

El builder NO soporta (aún):

- Complementos de CFDI (Carta Porte, Comercio Exterior, INE, etc.). Estos
  se agregarán en versiones futuras.
- CFDI tipo P (Pagos 2.0). Usa el endpoint `/api/v1/complementos-pago`
  directamente con XML pre-construido si lo necesitas hoy.
- CFDI tipo N (Nómina 1.2). Mismo enfoque.
- Generación de PDF. El SAT solo certifica el XML. Si necesitas PDF, usa
  herramientas externas como `weasyprint` con un template propio.

Si construyes el XML por tu cuenta, puedes seguir usando el cliente:

```python
xml = construir_mi_cfdi_complejo()  # XML que tu código generó
client.timbrar(xml)
```
