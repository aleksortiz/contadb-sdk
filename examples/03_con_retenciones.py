"""Ejemplo 03 — Honorarios profesionales con retenciones ISR e IVA.

Caso típico de un contador o profesional independiente facturando
servicios a una persona moral, donde la moral retiene:
- 10% de ISR
- 10.6667% de IVA (2/3 del 16%)

El total a cobrar es el subtotal + IVA - retenciones.
"""

from __future__ import annotations

import os
from decimal import Decimal

from contadb_sdk import (
    Certificado,
    CFDIBuilder,
    Concepto,
    ContaDBClient,
    Emisor,
    RateLimitError,
    Receptor,
    SaldoInsuficienteError,
)


def main() -> None:
    # 1. Carga el CSD
    cert = Certificado.cargar("emisor.cer", "emisor.key", os.environ["CSD_PASSWORD"])

    # 2. Emisor (persona física) y receptor (persona moral)
    emisor = Emisor(
        rfc="VECJ880326XXX",
        nombre="JUAN VELASCO",
        regimen_fiscal="612",  # Personas Físicas con Actividades Empresariales
    )
    receptor = Receptor(
        rfc="URE180429TM6",
        nombre="UNIVERSIDAD ROBOTICA ESPAÑOLA",
        uso_cfdi="G03",
        domicilio_fiscal_receptor="65000",
        regimen_fiscal_receptor="601",
    )

    # 3. Concepto con IVA trasladado y retenciones de ISR + IVA
    honorarios = Concepto(
        clave_prod_serv="80111501",  # Servicios profesionales
        clave_unidad="E48",
        descripcion="Honorarios contables — abril 2026",
        cantidad=Decimal("1"),
        valor_unitario=Decimal("15000.00"),
        objeto_imp="02",
        tasa_iva=Decimal("0.16"),
        tasa_retencion_isr=Decimal("0.10"),
        tasa_retencion_iva=Decimal("0.106667"),
    )

    # 4. Construye y firma el CFDI
    cfdi = CFDIBuilder(
        emisor=emisor,
        receptor=receptor,
        serie="H",
        folio="2026-005",
        forma_pago="03",
        metodo_pago="PUE",
        lugar_expedicion="64000",
    )
    cfdi.agregar_concepto(honorarios)

    xml = cfdi.construir_y_firmar(cert)

    # Cálculo esperado:
    #   SubTotal             = 15,000.00
    #   IVA trasladado (16%) = +2,400.00
    #   ISR retenido (10%)   = -1,500.00
    #   IVA retenido (10.67%)= -1,600.00 (2/3 del IVA)
    #   ──────────────────────────────────
    #   Total                = 14,300.00

    # 5. Timbra con manejo de errores comunes
    with ContaDBClient(api_token=os.environ["CONTADB_API_TOKEN"]) as client:
        try:
            result = client.timbrar(xml)
        except SaldoInsuficienteError:
            print("✗ Sin saldo de timbres. Compra más en https://contadb.mx/facturacion")
            return
        except RateLimitError as e:
            print(f"✗ Rate limit: reintenta en {e.retry_after}s")
            return

    print(f"✓ Honorarios timbrados — UUID: {result.uuid}")
    print(f"  Saldo restante: {result.saldo_restante} timbres")


if __name__ == "__main__":
    main()
