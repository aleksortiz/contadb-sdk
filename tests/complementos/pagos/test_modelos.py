"""Tests de los modelos Pydantic del Complemento de Pagos 2.0."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from contadb_sdk import DoctoRelacionado, Pago, RetencionDR, TrasladoDR


class TestTrasladoDR:
    def test_traslado_tasa_valido(self) -> None:
        t = TrasladoDR(
            base=Decimal("1000"),
            impuesto="002",
            tipo_factor="Tasa",
            tasa_o_cuota=Decimal("0.16"),
            importe=Decimal("160"),
        )
        assert t.tipo_factor == "Tasa"

    def test_traslado_exento_sin_tasa(self) -> None:
        t = TrasladoDR(
            base=Decimal("1000"),
            impuesto="002",
            tipo_factor="Exento",
        )
        assert t.tasa_o_cuota is None
        assert t.importe is None

    def test_traslado_exento_con_tasa_falla(self) -> None:
        with pytest.raises(PydanticValidationError, match="Exento no admite"):
            TrasladoDR(
                base=Decimal("1000"),
                impuesto="002",
                tipo_factor="Exento",
                tasa_o_cuota=Decimal("0.16"),
            )

    def test_traslado_tasa_sin_importe_falla(self) -> None:
        with pytest.raises(PydanticValidationError, match="requiere tasa_o_cuota e importe"):
            TrasladoDR(
                base=Decimal("1000"),
                impuesto="002",
                tipo_factor="Tasa",
                tasa_o_cuota=Decimal("0.16"),
            )

    def test_impuesto_invalido_falla(self) -> None:
        with pytest.raises(PydanticValidationError):
            TrasladoDR(
                base=Decimal("1000"),
                impuesto="999",
                tipo_factor="Tasa",
                tasa_o_cuota=Decimal("0.16"),
                importe=Decimal("160"),
            )


class TestRetencionDR:
    def test_retencion_basica(self) -> None:
        r = RetencionDR(
            base=Decimal("1000"),
            impuesto="001",
            tipo_factor="Tasa",
            tasa_o_cuota=Decimal("0.10"),
            importe=Decimal("100"),
        )
        assert r.impuesto == "001"

    def test_retencion_exento_falla(self) -> None:
        with pytest.raises(PydanticValidationError, match="no puede ser TipoFactor='Exento'"):
            RetencionDR(
                base=Decimal("1000"),
                impuesto="001",
                tipo_factor="Exento",
                tasa_o_cuota=Decimal("0"),
                importe=Decimal("0"),
            )


class TestDoctoRelacionado:
    def test_dr_basico(self, docto_uuid: str) -> None:
        dr = DoctoRelacionado(
            id_documento=docto_uuid,
            moneda_dr="MXN",
            num_parcialidad=1,
            imp_saldo_ant=Decimal("1000"),
            imp_pagado=Decimal("500"),
            imp_saldo_insoluto=Decimal("500"),
            objeto_imp_dr="01",
        )
        assert dr.objeto_imp_dr == "01"

    def test_saldo_insoluto_inconsistente_falla(self, docto_uuid: str) -> None:
        with pytest.raises(PydanticValidationError, match="imp_saldo_insoluto debe igualar"):
            DoctoRelacionado(
                id_documento=docto_uuid,
                moneda_dr="MXN",
                num_parcialidad=1,
                imp_saldo_ant=Decimal("1000"),
                imp_pagado=Decimal("500"),
                imp_saldo_insoluto=Decimal("400"),  # debería ser 500
                objeto_imp_dr="01",
            )

    def test_imp_pagado_excede_saldo_falla(self, docto_uuid: str) -> None:
        with pytest.raises(PydanticValidationError):
            DoctoRelacionado(
                id_documento=docto_uuid,
                moneda_dr="MXN",
                num_parcialidad=1,
                imp_saldo_ant=Decimal("500"),
                imp_pagado=Decimal("1000"),
                imp_saldo_insoluto=Decimal("-500"),
                objeto_imp_dr="01",
            )

    def test_objeto_imp_01_con_traslados_falla(self, docto_uuid: str) -> None:
        traslado = TrasladoDR(
            base=Decimal("1000"),
            impuesto="002",
            tipo_factor="Tasa",
            tasa_o_cuota=Decimal("0.16"),
            importe=Decimal("160"),
        )
        with pytest.raises(PydanticValidationError, match="no admite traslados/retenciones"):
            DoctoRelacionado(
                id_documento=docto_uuid,
                moneda_dr="MXN",
                num_parcialidad=1,
                imp_saldo_ant=Decimal("1000"),
                imp_pagado=Decimal("500"),
                imp_saldo_insoluto=Decimal("500"),
                objeto_imp_dr="01",
                traslados=[traslado],
            )

    def test_uuid_invalido_falla(self) -> None:
        with pytest.raises(PydanticValidationError):
            DoctoRelacionado(
                id_documento="no-es-uuid",
                moneda_dr="MXN",
                num_parcialidad=1,
                imp_saldo_ant=Decimal("1000"),
                imp_pagado=Decimal("500"),
                imp_saldo_insoluto=Decimal("500"),
                objeto_imp_dr="01",
            )


class TestPago:
    def test_pago_mxn_sin_tipo_cambio(self, docto_relacionado_basico: DoctoRelacionado) -> None:
        p = Pago(
            fecha_pago=datetime(2026, 4, 26),
            forma_pago="03",
            moneda="MXN",
            monto=Decimal("1160"),
            documentos=[docto_relacionado_basico],
        )
        assert p.tipo_cambio is None

    def test_pago_usd_sin_tipo_cambio_falla(
        self, docto_relacionado_basico: DoctoRelacionado
    ) -> None:
        with pytest.raises(PydanticValidationError, match="tipo_cambio es obligatorio"):
            Pago(
                fecha_pago=datetime(2026, 4, 26),
                forma_pago="03",
                moneda="USD",
                monto=Decimal("100"),
                documentos=[docto_relacionado_basico],
            )

    def test_pago_sin_documentos_falla(self) -> None:
        with pytest.raises(PydanticValidationError):
            Pago(
                fecha_pago=datetime(2026, 4, 26),
                forma_pago="03",
                moneda="MXN",
                monto=Decimal("100"),
                documentos=[],
            )

    def test_cadena_pago_parcial_falla(self, docto_relacionado_basico: DoctoRelacionado) -> None:
        with pytest.raises(PydanticValidationError, match="deben declararse todos juntos"):
            Pago(
                fecha_pago=datetime(2026, 4, 26),
                forma_pago="03",
                moneda="MXN",
                monto=Decimal("1160"),
                documentos=[docto_relacionado_basico],
                tipo_cad_pago="01",
                cad_pago="abc",
                # falta cert_pago y sello_pago
            )
