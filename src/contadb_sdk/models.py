"""Modelos Pydantic v2 del SDK.

Todos los importes monetarios usan :class:`decimal.Decimal` (no ``float``)
porque el SAT exige precisión exacta. Las tasas también son Decimal en
formato decimal (``0.16`` para 16%, no ``16``).
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Códigos válidos según catálogos SAT.
TipoComprobanteStr = Literal["I", "E", "T", "P", "N"]
MetodoPagoStr = Literal["PUE", "PPD"]
ExportacionStr = Literal["01", "02", "03", "04"]
ObjetoImpStr = Literal["01", "02", "03", "04", "05", "06", "07", "08"]
PeriodicidadStr = Literal["01", "02", "03", "04", "05"]
MotivoCancelacion = Literal["01", "02", "03", "04"]


def _formato_uuid(v: str) -> str:
    """Valida y normaliza un UUID v4 a minúsculas con guiones."""
    try:
        parsed = _uuid.UUID(v)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"UUID con formato inválido: {v!r}") from exc
    return str(parsed)


class _StrictModel(BaseModel):
    """Base con configuración estricta común."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=False,
    )


class Emisor(_StrictModel):
    """Datos del emisor (quien factura)."""

    rfc: str = Field(min_length=12, max_length=13, pattern=r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")
    nombre: str = Field(min_length=1, max_length=300)
    regimen_fiscal: str = Field(pattern=r"^\d{3}$")


class Receptor(_StrictModel):
    """Datos del receptor (quien recibe la factura).

    Para "Público en general" usar ``rfc="XAXX010101000"``,
    ``nombre="PUBLICO EN GENERAL"``, ``regimen_fiscal_receptor="616"``.
    """

    rfc: str = Field(min_length=12, max_length=13, pattern=r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")
    nombre: str = Field(min_length=1, max_length=300)
    uso_cfdi: str = Field(pattern=r"^[A-Z]\d{2}$")
    domicilio_fiscal_receptor: str = Field(pattern=r"^\d{5}$")
    regimen_fiscal_receptor: str = Field(pattern=r"^\d{3}$")
    residencia_fiscal: str | None = Field(default=None, min_length=3, max_length=3)
    num_reg_id_trib: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def _validar_rfc_generico(self) -> Receptor:
        if self.rfc == "XAXX010101000":
            if self.regimen_fiscal_receptor != "616":
                raise ValueError(
                    "RFC genérico XAXX010101000 requiere regimen_fiscal_receptor='616'"
                )
            if self.uso_cfdi != "S01":
                raise ValueError("RFC genérico XAXX010101000 requiere uso_cfdi='S01'")
        elif self.rfc == "XEXX010101000":
            if self.residencia_fiscal is None:
                raise ValueError(
                    "RFC genérico XEXX010101000 (extranjero) requiere residencia_fiscal"
                )
            if self.num_reg_id_trib is None:
                raise ValueError("RFC genérico XEXX010101000 (extranjero) requiere num_reg_id_trib")
            if self.regimen_fiscal_receptor != "616":
                raise ValueError(
                    "RFC genérico XEXX010101000 requiere regimen_fiscal_receptor='616'"
                )
        return self


class Concepto(_StrictModel):
    """Línea de la factura.

    Las tasas son decimales (``0.16`` = 16%). Si ``iva_exento=True`` se
    genera traslado IVA con ``TipoFactor="Exento"`` (sin tasa ni importe).
    """

    clave_prod_serv: str = Field(min_length=8, max_length=8, pattern=r"^\d{8}$")
    no_identificacion: str | None = Field(default=None, max_length=100)
    cantidad: Decimal = Field(gt=Decimal("0"))
    clave_unidad: str = Field(min_length=1, max_length=20)
    unidad: str | None = Field(default=None, max_length=20)
    descripcion: str = Field(min_length=1, max_length=1000)
    valor_unitario: Decimal = Field(ge=Decimal("0"))
    descuento: Decimal | None = Field(default=None, ge=Decimal("0"))
    objeto_imp: ObjetoImpStr = "02"
    tasa_iva: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    tasa_ieps: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    tasa_retencion_isr: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("0.35"))
    tasa_retencion_iva: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("0.16"))
    tasa_retencion_ieps: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    iva_exento: bool = False

    @model_validator(mode="after")
    def _validar_objeto_imp_consistencia(self) -> Concepto:
        tasas = (
            self.tasa_iva,
            self.tasa_ieps,
            self.tasa_retencion_isr,
            self.tasa_retencion_iva,
            self.tasa_retencion_ieps,
        )
        tiene_tasas = any(v is not None and v > Decimal("0") for v in tasas)

        if self.objeto_imp == "01":
            if tiene_tasas:
                raise ValueError("objeto_imp='01' (no objeto) no admite tasas ni retenciones")
            if self.iva_exento:
                raise ValueError("objeto_imp='01' es incompatible con iva_exento=True")
        elif self.objeto_imp not in ("02", "03"):
            if tiene_tasas or self.iva_exento:
                raise ValueError(
                    f"objeto_imp='{self.objeto_imp}' no procesa traslados/retenciones; "
                    "solo objeto_imp='02' o '03' admite tasas. Si tu caso requiere "
                    "estos códigos, omite las tasas o usa '02'."
                )
        return self


class InformacionGlobal(_StrictModel):
    """Bloque cfdi:InformacionGlobal — requerido para CFDI a "Público en general".

    - ``periodicidad``: 01=Diario, 02=Semanal, 03=Quincenal, 04=Mensual, 05=Bimestral.
    - ``meses``: "01"-"12" (o "13"-"18" para bimestres si periodicidad=05).
    - ``año``: año de 4 dígitos.
    """

    periodicidad: PeriodicidadStr
    meses: str = Field(pattern=r"^(0[1-9]|1[0-8])$")
    año: int = Field(ge=2000, le=9999)


class TimbradoResult(BaseModel):
    """Respuesta exitosa del endpoint /api/v1/timbrar."""

    model_config = ConfigDict(extra="ignore")

    success: bool = True
    xml_timbrado: str
    uuid: str
    saldo_restante: int
    fecha_vencimiento: datetime | None = None

    @field_validator("uuid")
    @classmethod
    def _validar_uuid(cls, v: str) -> str:
        return _formato_uuid(v)


class CancelacionResult(BaseModel):
    """Respuesta exitosa del endpoint /api/v1/cancelar."""

    model_config = ConfigDict(extra="ignore")

    success: bool = True
    uuid: str
    aceptada: bool = False
    estatus_uuid: str | None = None
    mensaje: str | None = None
    xml_acuse: str | None = None

    @field_validator("uuid")
    @classmethod
    def _validar_uuid(cls, v: str) -> str:
        return _formato_uuid(v)


__all__ = [
    "CancelacionResult",
    "Concepto",
    "Emisor",
    "ExportacionStr",
    "InformacionGlobal",
    "MetodoPagoStr",
    "MotivoCancelacion",
    "ObjetoImpStr",
    "PeriodicidadStr",
    "Receptor",
    "TimbradoResult",
    "TipoComprobanteStr",
]
