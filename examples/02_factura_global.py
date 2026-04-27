"""Ejemplo 02 — Factura global a "Público en general".

Cuando vendes mostrador a clientes no identificados (XAXX010101000), debes
emitir un CFDI global donde el bloque InformacionGlobal indica el período
acumulado (diario/semanal/mensual/etc.) y el receptor es genérico.

Detalles SAT:
- RFC receptor: XAXX010101000 ("Público en general")
- Régimen fiscal receptor: 616 (Sin obligaciones fiscales)
- UsoCFDI: S01 (Sin efectos fiscales)
- Domicilio fiscal receptor: mismo CP que LugarExpedicion
"""

from __future__ import annotations

import os
from decimal import Decimal

from contadb_sdk import (
    NOMBRE_PUBLICO_GENERAL,
    REGIMEN_SIN_OBLIGACIONES,
    RFC_PUBLICO_GENERAL,
    USO_PUBLICO_GENERAL,
    Certificado,
    CFDIBuilder,
    Concepto,
    ContaDBClient,
    Emisor,
    InformacionGlobal,
    Receptor,
)


def main() -> None:
    # 1. Carga el CSD
    cert = Certificado.cargar("emisor.cer", "emisor.key", os.environ["CSD_PASSWORD"])

    # 2. Emisor y receptor genérico
    emisor = Emisor(
        rfc="EKU9003173C9",
        nombre="ESCUELA KEMPER URGATE",
        regimen_fiscal="601",
    )
    receptor = Receptor(
        rfc=RFC_PUBLICO_GENERAL,
        nombre=NOMBRE_PUBLICO_GENERAL,
        uso_cfdi=USO_PUBLICO_GENERAL,
        domicilio_fiscal_receptor="64000",  # Mismo CP del emisor
        regimen_fiscal_receptor=REGIMEN_SIN_OBLIGACIONES,
    )

    # 3. Bloque InformacionGlobal — período del CFDI global (mensual abril 2026)
    info_global = InformacionGlobal(
        periodicidad="04",  # Mensual
        meses="04",  # Abril
        año=2026,
    )

    # 4. Resumen de ventas del período (un concepto por categoría)
    concepto_abarrotes = Concepto(
        clave_prod_serv="50202306",
        clave_unidad="H87",
        descripcion="Venta mostrador — abarrotes (período)",
        cantidad=Decimal("1"),
        valor_unitario=Decimal("12500.00"),
        objeto_imp="02",
        tasa_iva=Decimal("0.16"),
    )
    concepto_bebidas = Concepto(
        clave_prod_serv="50161509",
        clave_unidad="H87",
        descripcion="Venta mostrador — bebidas (período)",
        cantidad=Decimal("1"),
        valor_unitario=Decimal("3200.00"),
        objeto_imp="02",
        tasa_iva=Decimal("0.16"),
    )

    # 5. Construye y firma el CFDI global
    cfdi = CFDIBuilder(
        emisor=emisor,
        receptor=receptor,
        serie="GLB",
        folio="042",
        forma_pago="01",  # Efectivo
        metodo_pago="PUE",
        lugar_expedicion="64000",
        informacion_global=info_global,
    )
    cfdi.agregar_concepto(concepto_abarrotes)
    cfdi.agregar_concepto(concepto_bebidas)

    xml = cfdi.construir_y_firmar(cert)

    # 6. Timbra
    with ContaDBClient(api_token=os.environ["CONTADB_API_TOKEN"]) as client:
        result = client.timbrar(xml)

    print(f"✓ Factura global timbrada — UUID: {result.uuid}")


if __name__ == "__main__":
    main()
