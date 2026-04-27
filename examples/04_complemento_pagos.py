"""Ejemplo 04 — Complemento de Recepción de Pagos 2.0 (CRP / REP).

Caso típico: emitiste una factura con método de pago **PPD** (pago en
parcialidades o diferido) y ahora necesitas timbrar el comprobante de
pago al recibir el dinero del cliente.

Reglas SAT clave para CFDI tipo "P":
- TipoDeComprobante = "P"
- Moneda = "XXX" (siempre — el CFDI no representa el dinero, los Pagos sí)
- SubTotal = Total = 0
- Sin FormaPago, MetodoPago ni CondicionesDePago a nivel comprobante
- Un único concepto placeholder (ClaveProdServ=84111506, ValorUnitario=0)
- El bloque <pago20:Pagos> contiene los movimientos reales y sus impuestos

``CFDIBuilder.para_pago(...)`` aplica todos esos defaults; tú solo agregas
el complemento de Pagos.

Caso del ejemplo:
- Factura previa por $11,600 (subtotal $10,000 + IVA $1,600), UUID conocido.
- Cliente paga el total el 26 de abril vía transferencia (forma_pago=03).
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

    # 2. Construye el traslado de IVA del documento relacionado
    traslado_iva = TrasladoDR(
        base=Decimal("10000.00"),
        impuesto="002",  # IVA
        tipo_factor="Tasa",
        tasa_o_cuota=Decimal("0.16"),
        importe=Decimal("1600.00"),
    )

    # 3. Construye el documento relacionado (la factura PPD que se está pagando)
    docto = DoctoRelacionado(
        id_documento="11111111-2222-3333-4444-555555555555",  # UUID de la factura PPD
        serie="A",
        folio="1001",
        moneda_dr="MXN",
        num_parcialidad=1,
        imp_saldo_ant=Decimal("11600.00"),
        imp_pagado=Decimal("11600.00"),
        imp_saldo_insoluto=Decimal("0.00"),
        objeto_imp_dr="02",
        traslados=[traslado_iva],
    )

    # 4. Construye el pago (un solo movimiento que cubre el documento)
    pago = Pago(
        fecha_pago=datetime(2026, 4, 26, 12, 0, 0),
        forma_pago="03",  # Transferencia
        moneda="MXN",
        monto=Decimal("11600.00"),
        num_operacion="SPEI-2026042612345",
        documentos=[docto],
    )

    # 5. Empaqueta el pago en el bloque <pago20:Pagos>
    pagos = PagoBuilder()
    pagos.agregar_pago(pago)

    # 6. CFDI tipo "P" — la factory aplica los defaults SAT y el concepto placeholder
    emisor = Emisor(
        rfc="EKU9003173C9",
        nombre="ESCUELA KEMPER URGATE",
        regimen_fiscal="601",
    )
    receptor = Receptor(
        rfc="URE180429TM6",
        nombre="UNIVERSIDAD ROBOTICA ESPAÑOLA",
        uso_cfdi="CP01",  # Pagos
        domicilio_fiscal_receptor="65000",
        regimen_fiscal_receptor="601",
    )
    cfdi = CFDIBuilder.para_pago(
        emisor=emisor,
        receptor=receptor,
        serie="P",
        folio="2026-001",
        lugar_expedicion="64000",
    )
    cfdi.agregar_complemento(pagos)

    xml = cfdi.construir_y_firmar(cert)

    # 7. Timbra
    with ContaDBClient(api_token=os.environ["CONTADB_API_TOKEN"]) as client:
        result = client.timbrar(xml)

    print(f"✓ REP timbrado — UUID: {result.uuid}")
    print(f"  Saldo restante: {result.saldo_restante} timbres")

    with open(f"{result.uuid}.xml", "w", encoding="utf-8") as fh:
        fh.write(result.xml_timbrado)


if __name__ == "__main__":
    main()
