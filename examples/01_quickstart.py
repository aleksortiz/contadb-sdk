"""Ejemplo 01 — Quickstart: factura de ingreso PUE con IVA 16%.

Caso típico:
- Receptor identificado (con RFC)
- 1 concepto: servicio de consultoría por $1,000
- IVA 16% trasladado
- Total: $1,160.00
- Pago en una sola exhibición (PUE) por transferencia (forma_pago=03)

Configura las variables de entorno antes de ejecutar:
    export CONTADB_API_TOKEN=cdb_TU_TOKEN
    export CSD_PASSWORD=tu_password_del_sat

Y ajusta las rutas a tu .cer y .key.
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
    Receptor,
)


def main() -> None:
    # 1. Carga el CSD
    cert = Certificado.cargar(
        cer_path="emisor.cer",
        key_path="emisor.key",
        password=os.environ["CSD_PASSWORD"],
    )

    # 2. Datos del emisor y receptor
    emisor = Emisor(
        rfc="EKU9003173C9",
        nombre="ESCUELA KEMPER URGATE",
        regimen_fiscal="601",
    )
    receptor = Receptor(
        rfc="URE180429TM6",
        nombre="UNIVERSIDAD ROBOTICA ESPAÑOLA",
        uso_cfdi="G03",
        domicilio_fiscal_receptor="65000",
        regimen_fiscal_receptor="601",
    )

    # 3. Concepto facturado
    concepto = Concepto(
        clave_prod_serv="43232408",
        clave_unidad="E48",
        unidad="Servicio",
        descripcion="Servicios de consultoría en sistemas",
        cantidad=Decimal("1"),
        valor_unitario=Decimal("1000.00"),
        objeto_imp="02",
        tasa_iva=Decimal("0.16"),
    )

    # 4. Construye y firma el CFDI
    cfdi = CFDIBuilder(
        emisor=emisor,
        receptor=receptor,
        serie="A",
        folio="1001",
        forma_pago="03",  # Transferencia electrónica
        metodo_pago="PUE",
        lugar_expedicion="64000",
    )
    cfdi.agregar_concepto(concepto)

    xml = cfdi.construir_y_firmar(cert)

    # 5. Timbra contra ContaDB
    with ContaDBClient(api_token=os.environ["CONTADB_API_TOKEN"]) as client:
        result = client.timbrar(xml)

    print(f"✓ UUID:           {result.uuid}")
    print(f"  Saldo restante: {result.saldo_restante} timbres")

    # 6. Guarda el XML timbrado
    with open(f"{result.uuid}.xml", "w", encoding="utf-8") as fh:
        fh.write(result.xml_timbrado)
    print(f"  XML guardado en: {result.uuid}.xml")


if __name__ == "__main__":
    main()
