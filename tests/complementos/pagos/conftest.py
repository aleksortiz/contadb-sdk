"""Fixtures locales para tests del Complemento de Pagos 2.0."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from contadb_sdk import DoctoRelacionado, Pago, PagoBuilder, TrasladoDR


@pytest.fixture
def docto_uuid() -> str:
    return "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def docto_relacionado_basico(docto_uuid: str) -> DoctoRelacionado:
    """DR con IVA 16% — saldo previo $1160, pago total."""
    return DoctoRelacionado(
        id_documento=docto_uuid,
        serie="A",
        folio="1",
        moneda_dr="MXN",
        num_parcialidad=1,
        imp_saldo_ant=Decimal("1160.00"),
        imp_pagado=Decimal("1160.00"),
        imp_saldo_insoluto=Decimal("0.00"),
        objeto_imp_dr="02",
        traslados=[
            TrasladoDR(
                base=Decimal("1000.00"),
                impuesto="002",
                tipo_factor="Tasa",
                tasa_o_cuota=Decimal("0.16"),
                importe=Decimal("160.00"),
            )
        ],
    )


@pytest.fixture
def pago_basico(docto_relacionado_basico: DoctoRelacionado) -> Pago:
    return Pago(
        fecha_pago=datetime(2026, 4, 26, 12, 0, 0),
        forma_pago="03",
        moneda="MXN",
        monto=Decimal("1160.00"),
        documentos=[docto_relacionado_basico],
    )


@pytest.fixture
def pago_builder(pago_basico: Pago) -> PagoBuilder:
    return PagoBuilder().agregar_pago(pago_basico)
