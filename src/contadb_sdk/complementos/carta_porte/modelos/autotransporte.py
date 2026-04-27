"""Modelos del autotransporte (``cartaporte31:Autotransporte``).

Agrupa cuatro responsabilidades:
    - :class:`Autotransporte` — contenedor con permiso SCT.
    - :class:`IdentificacionVehicular` — placas, año, configuración.
    - :class:`Seguros` — pólizas obligatorias y opcionales.
    - :class:`Remolque` — remolques opcionales (0-2 admisibles según SAT).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..catalogos import validar_config_autotransporte, validar_tipo_permiso


class _StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=False,
    )


class IdentificacionVehicular(_StrictModel):
    """Identificación del vehículo motor (placas, año, configuración)."""

    config_vehicular: str
    peso_bruto_vehicular: Decimal = Field(gt=Decimal("0"))
    placa_vm: str = Field(min_length=5, max_length=7, pattern=r"^[A-Z0-9]+$")
    anio_modelo_vm: int = Field(ge=1900, le=date.today().year + 1)

    @model_validator(mode="after")
    def _validar_config_vehicular(self) -> IdentificacionVehicular:
        validar_config_autotransporte(self.config_vehicular)
        return self


class Seguros(_StrictModel):
    """Pólizas de seguro del autotransporte.

    Reglas SAT:
        - ``responsabilidad civil`` siempre obligatoria.
        - ``medio ambiente`` requerida si se transporta material peligroso
          (validación cruzada en :mod:`~..validadores`, no aquí).
        - ``carga`` opcional (cobertura de mercancía).
    """

    asegura_resp_civil: str = Field(min_length=1, max_length=50)
    poliza_resp_civil: str = Field(min_length=1, max_length=30)
    asegura_med_ambiente: str | None = Field(default=None, min_length=1, max_length=50)
    poliza_med_ambiente: str | None = Field(default=None, min_length=1, max_length=30)
    asegura_carga: str | None = Field(default=None, min_length=1, max_length=50)
    poliza_carga: str | None = Field(default=None, min_length=1, max_length=30)
    prima_seguro: Decimal | None = Field(default=None, gt=Decimal("0"))

    @model_validator(mode="after")
    def _coherencia_aseguradoras(self) -> Seguros:
        # Cada aseguradora va con su póliza — no se admite una sin la otra.
        pares = (
            (self.asegura_med_ambiente, self.poliza_med_ambiente, "medio ambiente"),
            (self.asegura_carga, self.poliza_carga, "carga"),
        )
        for aseguradora, poliza, etiqueta in pares:
            if (aseguradora is None) != (poliza is None):
                raise ValueError(
                    f"Seguros de {etiqueta}: aseguradora y póliza deben declararse juntas"
                )
        return self


class Remolque(_StrictModel):
    """Remolque o semirremolque (0-2 por autotransporte)."""

    sub_tipo_rem: str = Field(min_length=5, max_length=5, pattern=r"^CTR\d{2}$")
    placa: str = Field(min_length=5, max_length=7, pattern=r"^[A-Z0-9]+$")


class Autotransporte(_StrictModel):
    """Bloque ``cartaporte31:Autotransporte`` completo."""

    perm_sct: str
    num_permiso_sct: str = Field(min_length=6, max_length=50)
    identificacion_vehicular: IdentificacionVehicular
    seguros: Seguros
    remolques: list[Remolque] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def _validar_permiso(self) -> Autotransporte:
        validar_tipo_permiso(self.perm_sct)
        return self


__all__ = ["Autotransporte", "IdentificacionVehicular", "Remolque", "Seguros"]
