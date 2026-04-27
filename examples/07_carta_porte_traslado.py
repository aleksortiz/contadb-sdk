"""Ejemplo 07 — Carta Porte 3.1 con Autotransporte (Traslado nacional).

Caso típico: una empresa mueve mercancía propia entre sus sucursales o
hacia un cliente, sin venta involucrada. CFDI tipo "T" (Traslado) con
complemento de Carta Porte 3.1.

Caso del ejemplo:
- Origen:  Planta Monterrey, NL (CP 64000), salida 26-abr 06:00
- Destino: Obra CDMX (CP 03100), llegada 27-abr 14:00
- Distancia recorrida: 940 km
- Mercancía: 5,000 kg de varilla corrugada
- Vehículo propio: camión configuración T3S2, placa NLF-1234, modelo 2022
- Operador: empleado con licencia federal SCT
"""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal

from contadb_sdk import (
    Certificado,
    CFDIBuilder,
    ContaDBClient,
    Emisor,
    Receptor,
)
from contadb_sdk.complementos.carta_porte import (
    Autotransporte,
    CartaPorteBuilder,
    Domicilio,
    FiguraTransporte,
    IdentificacionVehicular,
    Mercancia,
    Seguros,
    TiposFigura,
    Ubicacion,
)


def main() -> None:
    # 1. Carga el CSD
    cert = Certificado.cargar("emisor.cer", "emisor.key", os.environ["CSD_PASSWORD"])

    # 2. Domicilio del origen
    domicilio_origen = Domicilio(
        calle="Av. Constitución",
        numero_exterior="100",
        colonia="Centro",
        municipio="019",  # Monterrey (catálogo c_Municipio — string libre en 3a)
        estado="NLE",  # Nuevo León (catálogo c_Estado)
        pais="MEX",  # Validado contra catálogo
        codigo_postal="64000",
    )

    # 3. Ubicación de origen
    origen = Ubicacion(
        tipo_ubicacion="Origen",
        id_ubicacion="OR000001",
        rfc_remitente_destinatario="EKU9003173C9",
        nombre_remitente_destinatario="ESCUELA KEMPER URGATE",
        fecha_hora_salida_llegada=datetime(2026, 4, 26, 6, 0, 0),
        domicilio=domicilio_origen,
    )

    # 4. Domicilio del destino
    domicilio_destino = Domicilio(
        calle="Av. Insurgentes Sur",
        numero_exterior="2000",
        colonia="Del Valle",
        municipio="014",  # Benito Juárez
        estado="CMX",  # Ciudad de México
        pais="MEX",
        codigo_postal="03100",
    )

    # 5. Ubicación de destino — incluye distancia recorrida desde el origen
    destino = Ubicacion(
        tipo_ubicacion="Destino",
        id_ubicacion="DE000001",
        rfc_remitente_destinatario="URE180429TM6",
        nombre_remitente_destinatario="UNIVERSIDAD ROBOTICA ESPAÑOLA",
        fecha_hora_salida_llegada=datetime(2026, 4, 27, 14, 0, 0),
        distancia_recorrida=Decimal("940"),  # km
        domicilio=domicilio_destino,
    )

    # 6. Mercancía transportada
    mercancia = Mercancia(
        bienes_transp="11161703",  # ClaveProdServCP — varilla de acero
        descripcion="Varilla corrugada 3/8 grado 42",
        cantidad=Decimal("5000"),
        clave_unidad="KGM",  # Kilogramo
        peso_en_kg=Decimal("5000"),
        material_peligroso="No",
    )

    # 7. Identificación vehicular del autotransporte
    identificacion = IdentificacionVehicular(
        config_vehicular="T3S2",  # Validado contra ConfiguracionAutotransporte
        peso_bruto_vehicular=Decimal("28.5"),  # toneladas
        placa_vm="NLF1234",
        anio_modelo_vm=2022,
    )

    # 8. Seguros del autotransporte (responsabilidad civil obligatoria)
    seguros = Seguros(
        asegura_resp_civil="QUALITAS COMPAÑIA DE SEGUROS",
        poliza_resp_civil="POL-RC-998877",
    )

    # 9. Autotransporte — vehículo + permiso SCT + seguros
    autotransporte = Autotransporte(
        perm_sct="TPAF01",  # Autotransporte federal de carga
        num_permiso_sct="A-12345-2025",
        identificacion_vehicular=identificacion,
        seguros=seguros,
    )

    # 10. Operador del vehículo (TipoFigura=01)
    operador = TiposFigura(
        tipo_figura="01",  # Operador
        rfc_figura="VECJ880326XXX",
        num_licencia="A1234567",
        nombre_figura="JUAN VELASCO",
    )

    figura_transporte = FiguraTransporte()
    figura_transporte.agregar_figura(operador)

    # 11. Ensambla la Carta Porte
    carta_porte = CartaPorteBuilder(
        transp_internac="No",
        total_dist_rec=Decimal("940"),
    )
    carta_porte.agregar_ubicacion(origen)
    carta_porte.agregar_ubicacion(destino)
    carta_porte.agregar_mercancia(mercancia)
    carta_porte.establecer_autotransporte(autotransporte)
    carta_porte.agregar_figura_transporte(figura_transporte)

    # 12. CFDI tipo "T" — la factory aplica los defaults SAT (subtotal/total=0,
    #     sin forma/método de pago, concepto placeholder con la mercancía).
    emisor = Emisor(
        rfc="EKU9003173C9",
        nombre="ESCUELA KEMPER URGATE",
        regimen_fiscal="601",
    )
    receptor = Receptor(
        rfc="URE180429TM6",
        nombre="UNIVERSIDAD ROBOTICA ESPAÑOLA",
        uso_cfdi="S01",
        domicilio_fiscal_receptor="03100",
        regimen_fiscal_receptor="601",
    )
    cfdi = CFDIBuilder.para_traslado(
        emisor=emisor,
        receptor=receptor,
        serie="T",
        folio="2026-001",
        lugar_expedicion="64000",
    )
    cfdi.agregar_complemento(carta_porte)

    xml = cfdi.construir_y_firmar(cert)

    # 13. Timbra
    with ContaDBClient(api_token=os.environ["CONTADB_API_TOKEN"]) as client:
        result = client.timbrar(xml)

    print(f"✓ Carta Porte timbrada — UUID: {result.uuid}")
    print(f"  Saldo restante: {result.saldo_restante} timbres")


if __name__ == "__main__":
    main()
