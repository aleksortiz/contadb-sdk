"""Modelos Pydantic del Complemento de Recepción de Pagos 2.0.

Solo definen estructura y validaciones intra-modelo — nada de XML, nada de
side-effects. La construcción XML vive en :mod:`.builder` y los cálculos
agregados en :mod:`._calculos`.

Importes y tasas son ``Decimal`` (nunca ``float``) — el SAT requiere
precisión exacta.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...catalogs import IMPUESTO_IEPS, IMPUESTO_ISR, IMPUESTO_IVA
from .tipos import ObjetoImpDRStr, TipoCadenaPagoStr, TipoFactorStr

_IMPUESTOS_VALIDOS = frozenset({IMPUESTO_ISR, IMPUESTO_IVA, IMPUESTO_IEPS})


class _StrictModel(BaseModel):
    """Configuración estricta común a todos los modelos del complemento."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=False,
    )


class TrasladoDR(_StrictModel):
    """Traslado a nivel DoctoRelacionado (``pago20:TrasladoDR``).

    - ``tipo_factor="Exento"``: no admite ``tasa_o_cuota`` ni ``importe``.
    - ``tipo_factor="Tasa"``/``"Cuota"``: requiere ambos.
    """

    base: Decimal = Field(gt=Decimal("0"))
    impuesto: str = Field(pattern=r"^00[123]$")
    tipo_factor: TipoFactorStr = "Tasa"
    tasa_o_cuota: Decimal | None = Field(default=None, ge=Decimal("0"))
    importe: Decimal | None = Field(default=None, ge=Decimal("0"))

    @model_validator(mode="after")
    def _coherencia_factor(self) -> TrasladoDR:
        if self.tipo_factor == "Exento":
            if self.tasa_o_cuota is not None or self.importe is not None:
                raise ValueError("TrasladoDR Exento no admite tasa_o_cuota ni importe")
        else:
            if self.tasa_o_cuota is None or self.importe is None:
                raise ValueError(
                    "TrasladoDR con TipoFactor 'Tasa'/'Cuota' requiere tasa_o_cuota e importe"
                )
        if self.impuesto not in _IMPUESTOS_VALIDOS:
            raise ValueError(f"Impuesto inválido: {self.impuesto!r}")
        return self


class RetencionDR(_StrictModel):
    """Retención a nivel DoctoRelacionado (``pago20:RetencionDR``).

    A diferencia de los traslados, las retenciones nunca son "Exento" —
    siempre se calculan con ``Tasa`` o ``Cuota``.
    """

    base: Decimal = Field(gt=Decimal("0"))
    impuesto: str = Field(pattern=r"^00[123]$")
    tipo_factor: TipoFactorStr = "Tasa"
    tasa_o_cuota: Decimal = Field(ge=Decimal("0"))
    importe: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def _retencion_no_exenta(self) -> RetencionDR:
        if self.tipo_factor == "Exento":
            raise ValueError("RetencionDR no puede ser TipoFactor='Exento'")
        if self.impuesto not in _IMPUESTOS_VALIDOS:
            raise ValueError(f"Impuesto inválido: {self.impuesto!r}")
        return self


class DoctoRelacionado(_StrictModel):
    """Documento (CFDI previo) que está siendo cubierto por un :class:`Pago`.

    Reglas SAT:
        - ``imp_saldo_insoluto = imp_saldo_ant - imp_pagado`` (validado).
        - ``num_parcialidad >= 1``.
        - ``objeto_imp_dr="02"`` admite traslados/retenciones; ``"01"``/``"03"`` no.
        - Si la moneda del DR difiere de la del Pago padre, debe declararse
          ``equivalencia_dr``; esa validación cruzada se hace en el builder.

    Convención de ``equivalencia_dr``:
        El SDK aplica la regla de validación SAT
        ``ImpPagado_DR * EquivalenciaDR ≈ Pago.Monto``, es decir,
        ``EquivalenciaDR`` convierte importes del DR a la moneda del Pago
        multiplicando. En unidades: ``EquivalenciaDR = MonedaP / MonedaDR``.

        Ejemplo: DR en MXN, Pago en USD, tipo de cambio 1 USD = 20 MXN →
        ``equivalencia_dr = 0.05`` (porque 1 MXN = 0.05 USD).
    """

    id_documento: str = Field(
        pattern=(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        )
    )
    serie: str | None = Field(default=None, min_length=1, max_length=25)
    folio: str | None = Field(default=None, min_length=1, max_length=40)
    moneda_dr: str = Field(pattern=r"^[A-Z]{3}$")
    equivalencia_dr: Decimal | None = Field(default=None, gt=Decimal("0"))
    num_parcialidad: int = Field(ge=1)
    imp_saldo_ant: Decimal = Field(gt=Decimal("0"))
    imp_pagado: Decimal = Field(gt=Decimal("0"))
    imp_saldo_insoluto: Decimal = Field(ge=Decimal("0"))
    objeto_imp_dr: ObjetoImpDRStr = "01"
    traslados: list[TrasladoDR] = Field(default_factory=list)
    retenciones: list[RetencionDR] = Field(default_factory=list)

    @model_validator(mode="after")
    def _coherencia_saldos(self) -> DoctoRelacionado:
        esperado = self.imp_saldo_ant - self.imp_pagado
        if esperado != self.imp_saldo_insoluto:
            raise ValueError(
                "imp_saldo_insoluto debe igualar imp_saldo_ant - imp_pagado "
                f"(esperado {esperado}, recibido {self.imp_saldo_insoluto})"
            )
        if self.imp_pagado > self.imp_saldo_ant:
            raise ValueError("imp_pagado no puede exceder imp_saldo_ant")
        return self

    @model_validator(mode="after")
    def _coherencia_objeto_imp(self) -> DoctoRelacionado:
        if self.objeto_imp_dr != "02" and (self.traslados or self.retenciones):
            raise ValueError("objeto_imp_dr distinto de '02' no admite traslados/retenciones")
        return self


class Pago(_StrictModel):
    """Un movimiento de dinero recibido (``pago20:Pago``).

    Si ``moneda != "MXN"``, ``tipo_cambio`` es obligatorio.

    Los datos bancarios y de cadena de pago (NumOperacion, RfcEmisor*, etc.)
    son opcionales según el catálogo SAT y el método de pago. La aplicación
    de impuestos a nivel Pago (``pago20:ImpuestosP``) se calcula
    automáticamente por el builder a partir de los DRs — no se declara aquí.
    """

    fecha_pago: datetime
    forma_pago: str = Field(pattern=r"^\d{2}$")
    moneda: str = Field(pattern=r"^[A-Z]{3}$")
    tipo_cambio: Decimal | None = Field(default=None, gt=Decimal("0"))
    monto: Decimal = Field(gt=Decimal("0"))
    num_operacion: str | None = Field(default=None, min_length=1, max_length=100)
    rfc_emisor_cta_ord: str | None = Field(default=None, pattern=r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")
    nom_banco_ord_ext: str | None = Field(default=None, min_length=1, max_length=300)
    cta_ordenante: str | None = Field(default=None, min_length=10, max_length=50)
    rfc_emisor_cta_ben: str | None = Field(default=None, pattern=r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")
    cta_beneficiario: str | None = Field(default=None, min_length=10, max_length=50)
    tipo_cad_pago: TipoCadenaPagoStr | None = None
    cert_pago: str | None = Field(default=None, min_length=1)
    cad_pago: str | None = Field(default=None, min_length=1, max_length=8192)
    sello_pago: str | None = Field(default=None, min_length=1)
    documentos: list[DoctoRelacionado] = Field(min_length=1)

    @model_validator(mode="after")
    def _coherencia_moneda(self) -> Pago:
        if self.moneda != "MXN" and self.tipo_cambio is None:
            raise ValueError("tipo_cambio es obligatorio cuando moneda != 'MXN'")
        return self

    @model_validator(mode="after")
    def _coherencia_cadena_pago(self) -> Pago:
        # Los 4 atributos de cadena de pago van juntos: o todos o ninguno.
        cadena_attrs = (self.tipo_cad_pago, self.cert_pago, self.cad_pago, self.sello_pago)
        present = [a is not None for a in cadena_attrs]
        if any(present) and not all(present):
            raise ValueError(
                "tipo_cad_pago, cert_pago, cad_pago y sello_pago deben "
                "declararse todos juntos o ninguno"
            )
        return self


__all__ = [
    "DoctoRelacionado",
    "Pago",
    "RetencionDR",
    "TrasladoDR",
]
