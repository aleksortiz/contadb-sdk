"""Ejemplo 05 — REP con parcialidades sobre múltiples facturas.

Caso típico: el cliente realiza UN solo depósito que cubre parcialmente
varias facturas. En CRP 2.0 esto se modela como un único ``Pago`` con
varios ``DoctoRelacionado`` — cada DR lleva su propio ``NumParcialidad``,
``ImpSaldoAnt``, ``ImpPagado`` e ``ImpSaldoInsoluto``.

Caso del ejemplo:
- Factura A1001: saldo $5,800 → cliente abona $3,000 (parcialidad 2 de N).
- Factura A1002: saldo $11,600 → cliente liquida $11,600 (parcialidad 1).
- Total del depósito: $14,600.

El builder agrega automáticamente:
- ``pago20:ImpuestosP`` por Pago (suma de impuestos de los DRs).
- ``pago20:Totales`` por comprobante (con ImpuestoIVA16 acumulado, etc.).
"""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal

from contadb_sdk import (
    Certificado,
    CFDIBuilder,
    ContaDBClient,
    DoctoRelacionado,
    Emisor,
    Pago,
    PagoBuilder,
    Receptor,
    TrasladoDR,
)


def main() -> None:
    # 1. Carga el CSD
    cert = Certificado.cargar("emisor.cer", "emisor.key", os.environ["CSD_PASSWORD"])

    # 2. Abono parcial sobre A1001 — paga $3,000 de un saldo de $5,800.
    #    Base proporcional gravada por IVA: 3000 / 1.16 ≈ 2586.21 → IVA = 413.79.
    traslado_a1001 = TrasladoDR(
        base=Decimal("2586.21"),
        impuesto="002",
        tipo_factor="Tasa",
        tasa_o_cuota=Decimal("0.16"),
        importe=Decimal("413.79"),
    )
    dr_parcial = DoctoRelacionado(
        id_documento="aaaaaaaa-1111-2222-3333-444444444444",
        serie="A",
        folio="1001",
        moneda_dr="MXN",
        num_parcialidad=2,
        imp_saldo_ant=Decimal("5800.00"),
        imp_pagado=Decimal("3000.00"),
        imp_saldo_insoluto=Decimal("2800.00"),
        objeto_imp_dr="02",
        traslados=[traslado_a1001],
    )

    # 3. Liquidación total de A1002 — paga $11,600 de un saldo de $11,600.
    traslado_a1002 = TrasladoDR(
        base=Decimal("10000.00"),
        impuesto="002",
        tipo_factor="Tasa",
        tasa_o_cuota=Decimal("0.16"),
        importe=Decimal("1600.00"),
    )
    dr_liquidacion = DoctoRelacionado(
        id_documento="bbbbbbbb-5555-6666-7777-888888888888",
        serie="A",
        folio="1002",
        moneda_dr="MXN",
        num_parcialidad=1,
        imp_saldo_ant=Decimal("11600.00"),
        imp_pagado=Decimal("11600.00"),
        imp_saldo_insoluto=Decimal("0.00"),
        objeto_imp_dr="02",
        traslados=[traslado_a1002],
    )

    # 4. Un único pago que cubre ambos documentos
    pago = Pago(
        fecha_pago=datetime(2026, 4, 26, 9, 30, 0),
        forma_pago="03",
        moneda="MXN",
        monto=Decimal("14600.00"),  # 3,000 + 11,600
        num_operacion="SPEI-2026042699999",
        documentos=[dr_parcial, dr_liquidacion],
    )

    pagos = PagoBuilder()
    pagos.agregar_pago(pago)

    # 5. CFDI tipo "P"
    emisor = Emisor(
        rfc="EKU9003173C9",
        nombre="ESCUELA KEMPER URGATE",
        regimen_fiscal="601",
    )
    receptor = Receptor(
        rfc="URE180429TM6",
        nombre="UNIVERSIDAD ROBOTICA ESPAÑOLA",
        uso_cfdi="CP01",
        domicilio_fiscal_receptor="65000",
        regimen_fiscal_receptor="601",
    )
    cfdi = CFDIBuilder.para_pago(
        emisor=emisor,
        receptor=receptor,
        serie="P",
        folio="2026-002",
        lugar_expedicion="64000",
    )
    cfdi.agregar_complemento(pagos)

    xml = cfdi.construir_y_firmar(cert)

    # Totales agregados que generará el SDK:
    #   TotalTrasladosBaseIVA16     = 2,586.21 + 10,000.00 = 12,586.21
    #   TotalTrasladosImpuestoIVA16 =   413.79 +  1,600.00 =  2,013.79
    #   MontoTotalPagos             =                       14,600.00

    # 6. Timbra
    with ContaDBClient(api_token=os.environ["CONTADB_API_TOKEN"]) as client:
        result = client.timbrar(xml)

    print(f"✓ REP con parcialidades timbrado — UUID: {result.uuid}")


if __name__ == "__main__":
    main()
