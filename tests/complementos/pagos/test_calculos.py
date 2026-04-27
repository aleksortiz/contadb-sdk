"""Tests de los cálculos puros del Complemento de Pagos 2.0."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from contadb_sdk import DoctoRelacionado, Pago, RetencionDR, TrasladoDR
from contadb_sdk.complementos.pagos._calculos import (
    calcular_impuestos_p,
    calcular_totales,
)


class TestCalcularImpuestosP:
    def test_traslado_simple(self, pago_basico: Pago) -> None:
        ip = calcular_impuestos_p(pago_basico)
        assert len(ip.traslados) == 1
        assert len(ip.retenciones) == 0
        t = ip.traslados[0]
        assert t.impuesto == "002"
        assert t.tasa_o_cuota == Decimal("0.16")
        assert t.base == Decimal("1000.00")
        assert t.importe == Decimal("160.00")

    def test_agrega_traslados_misma_tasa_distintos_dr(self, docto_uuid: str) -> None:
        traslado = TrasladoDR(
            base=Decimal("1000"),
            impuesto="002",
            tipo_factor="Tasa",
            tasa_o_cuota=Decimal("0.16"),
            importe=Decimal("160"),
        )
        dr1 = DoctoRelacionado(
            id_documento=docto_uuid,
            moneda_dr="MXN",
            num_parcialidad=1,
            imp_saldo_ant=Decimal("1160"),
            imp_pagado=Decimal("1160"),
            imp_saldo_insoluto=Decimal("0"),
            objeto_imp_dr="02",
            traslados=[traslado],
        )
        dr2 = DoctoRelacionado(
            id_documento="22222222-3333-4444-5555-666666666666",
            moneda_dr="MXN",
            num_parcialidad=1,
            imp_saldo_ant=Decimal("1160"),
            imp_pagado=Decimal("1160"),
            imp_saldo_insoluto=Decimal("0"),
            objeto_imp_dr="02",
            traslados=[traslado],
        )
        pago = Pago(
            fecha_pago=datetime(2026, 4, 26),
            forma_pago="03",
            moneda="MXN",
            monto=Decimal("2320"),
            documentos=[dr1, dr2],
        )
        ip = calcular_impuestos_p(pago)
        assert len(ip.traslados) == 1  # se agregaron en uno solo
        assert ip.traslados[0].base == Decimal("2000.00")
        assert ip.traslados[0].importe == Decimal("320.00")

    def test_retencion_se_agrega_por_impuesto(self, docto_uuid: str) -> None:
        dr = DoctoRelacionado(
            id_documento=docto_uuid,
            moneda_dr="MXN",
            num_parcialidad=1,
            imp_saldo_ant=Decimal("1060"),
            imp_pagado=Decimal("1060"),
            imp_saldo_insoluto=Decimal("0"),
            objeto_imp_dr="02",
            traslados=[
                TrasladoDR(
                    base=Decimal("1000"),
                    impuesto="002",
                    tipo_factor="Tasa",
                    tasa_o_cuota=Decimal("0.16"),
                    importe=Decimal("160"),
                )
            ],
            retenciones=[
                RetencionDR(
                    base=Decimal("1000"),
                    impuesto="001",
                    tipo_factor="Tasa",
                    tasa_o_cuota=Decimal("0.10"),
                    importe=Decimal("100"),
                )
            ],
        )
        pago = Pago(
            fecha_pago=datetime(2026, 4, 26),
            forma_pago="03",
            moneda="MXN",
            monto=Decimal("1060"),
            documentos=[dr],
        )
        ip = calcular_impuestos_p(pago)
        assert len(ip.retenciones) == 1
        assert ip.retenciones[0].impuesto == "001"
        assert ip.retenciones[0].importe == Decimal("100.00")

    def test_dr_objeto_imp_01_no_agrega(self, docto_uuid: str) -> None:
        dr = DoctoRelacionado(
            id_documento=docto_uuid,
            moneda_dr="MXN",
            num_parcialidad=1,
            imp_saldo_ant=Decimal("1000"),
            imp_pagado=Decimal("1000"),
            imp_saldo_insoluto=Decimal("0"),
            objeto_imp_dr="01",
        )
        pago = Pago(
            fecha_pago=datetime(2026, 4, 26),
            forma_pago="03",
            moneda="MXN",
            monto=Decimal("1000"),
            documentos=[dr],
        )
        ip = calcular_impuestos_p(pago)
        assert ip.vacio

    def test_conversion_moneda_dr_a_p(self, docto_uuid: str) -> None:
        # DR en USD, Pago en MXN, equivalencia=20
        dr = DoctoRelacionado(
            id_documento=docto_uuid,
            moneda_dr="USD",
            equivalencia_dr=Decimal("20"),
            num_parcialidad=1,
            imp_saldo_ant=Decimal("116"),
            imp_pagado=Decimal("116"),
            imp_saldo_insoluto=Decimal("0"),
            objeto_imp_dr="02",
            traslados=[
                TrasladoDR(
                    base=Decimal("100"),
                    impuesto="002",
                    tipo_factor="Tasa",
                    tasa_o_cuota=Decimal("0.16"),
                    importe=Decimal("16"),
                )
            ],
        )
        pago = Pago(
            fecha_pago=datetime(2026, 4, 26),
            forma_pago="03",
            moneda="MXN",
            monto=Decimal("2320"),
            documentos=[dr],
        )
        ip = calcular_impuestos_p(pago)
        assert ip.traslados[0].base == Decimal("2000.00")  # 100 * 20
        assert ip.traslados[0].importe == Decimal("320.00")  # 16 * 20


class TestCalcularTotales:
    def test_totales_iva_16(self, pago_basico: Pago) -> None:
        totales = calcular_totales([pago_basico])
        assert totales.monto_total_pagos == Decimal("1160.00")
        assert totales.total_traslados_base_iva_16 == Decimal("1000.00")
        assert totales.total_traslados_impuesto_iva_16 == Decimal("160.00")
        assert totales.total_traslados_base_iva_8 is None
        assert totales.total_traslados_base_iva_exento is None
        assert totales.total_retenciones_iva is None

    def test_totales_pago_extranjero_convierte_a_mxn(self, docto_uuid: str) -> None:
        dr = DoctoRelacionado(
            id_documento=docto_uuid,
            moneda_dr="USD",
            num_parcialidad=1,
            imp_saldo_ant=Decimal("116"),
            imp_pagado=Decimal("116"),
            imp_saldo_insoluto=Decimal("0"),
            objeto_imp_dr="02",
            traslados=[
                TrasladoDR(
                    base=Decimal("100"),
                    impuesto="002",
                    tipo_factor="Tasa",
                    tasa_o_cuota=Decimal("0.16"),
                    importe=Decimal("16"),
                )
            ],
        )
        pago = Pago(
            fecha_pago=datetime(2026, 4, 26),
            forma_pago="03",
            moneda="USD",
            tipo_cambio=Decimal("20"),
            monto=Decimal("116"),
            documentos=[dr],
        )
        t = calcular_totales([pago])
        assert t.monto_total_pagos == Decimal("2320.00")  # 116 USD * 20
        assert t.total_traslados_base_iva_16 == Decimal("2000.00")
        assert t.total_traslados_impuesto_iva_16 == Decimal("320.00")

    def test_iva_exento_solo_base(self, docto_uuid: str) -> None:
        dr = DoctoRelacionado(
            id_documento=docto_uuid,
            moneda_dr="MXN",
            num_parcialidad=1,
            imp_saldo_ant=Decimal("1000"),
            imp_pagado=Decimal("1000"),
            imp_saldo_insoluto=Decimal("0"),
            objeto_imp_dr="02",
            traslados=[
                TrasladoDR(
                    base=Decimal("1000"),
                    impuesto="002",
                    tipo_factor="Exento",
                )
            ],
        )
        pago = Pago(
            fecha_pago=datetime(2026, 4, 26),
            forma_pago="03",
            moneda="MXN",
            monto=Decimal("1000"),
            documentos=[dr],
        )
        t = calcular_totales([pago])
        assert t.total_traslados_base_iva_exento == Decimal("1000.00")
        assert t.total_traslados_base_iva_16 is None
