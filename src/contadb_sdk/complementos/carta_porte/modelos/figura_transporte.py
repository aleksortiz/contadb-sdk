"""FiguraTransporte y TiposFigura (``cartaporte31:FiguraTransporte``).

Reglas SAT clave:
    - Mínimo una ``TiposFigura`` por bloque FiguraTransporte.
    - ``tipo_figura="01"`` (Operador) requiere ``num_licencia``.
    - Operador no admite Domicilio (lo prohíbe el SAT).
    - Las demás figuras (02 Propietario, 03 Arrendatario, 04 Notificado)
      pueden declarar Domicilio opcional.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..catalogos import validar_tipo_figura
from ..tipos import TipoFiguraStr
from .comun import Domicilio


class _StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=False,
    )


class TiposFigura(_StrictModel):
    """Una figura del transporte (operador, propietario, etc.)."""

    tipo_figura: TipoFiguraStr
    rfc_figura: str = Field(pattern=r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$|^XEXX010101000$")
    num_licencia: str | None = Field(default=None, min_length=1, max_length=16)
    nombre_figura: str | None = Field(default=None, min_length=1, max_length=300)
    num_reg_id_trib_figura: str | None = Field(default=None, min_length=6, max_length=40)
    residencia_fiscal_figura: str | None = Field(default=None, min_length=3, max_length=3)
    domicilio: Domicilio | None = None

    @model_validator(mode="after")
    def _validar_tipo_figura(self) -> TiposFigura:
        validar_tipo_figura(self.tipo_figura)
        if self.tipo_figura == "01" and self.num_licencia is None:
            raise ValueError("tipo_figura='01' (Operador) requiere num_licencia")
        if self.tipo_figura == "01" and self.domicilio is not None:
            raise ValueError("tipo_figura='01' (Operador) no admite domicilio")
        return self


class FiguraTransporte(_StrictModel):
    """Contenedor de figuras (``cartaporte31:FiguraTransporte``).

    Implementado como modelo Pydantic para validación uniforme; en uso
    típico se construye con :meth:`agregar_figura` y se entrega al
    builder.
    """

    figuras: list[TiposFigura] = Field(default_factory=list)

    def agregar_figura(self, figura: TiposFigura) -> FiguraTransporte:
        if not isinstance(figura, TiposFigura):
            raise TypeError("figura debe ser una instancia de TiposFigura")
        self.figuras.append(figura)
        return self


__all__ = ["FiguraTransporte", "TiposFigura"]
