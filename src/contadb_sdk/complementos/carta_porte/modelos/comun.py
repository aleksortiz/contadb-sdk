"""Modelos compartidos del Complemento Carta Porte 3.1.

``Domicilio`` se reutiliza en :class:`~..ubicaciones.Ubicacion` y
opcionalmente en :class:`~..figura_transporte.TiposFigura`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..catalogos import validar_pais


class _StrictModel(BaseModel):
    """Configuración estricta común para modelos del complemento."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=False,
    )


class Domicilio(_StrictModel):
    """Domicilio postal usado en Ubicacion y opcionalmente en TiposFigura.

    Validaciones Fase 3a:
        - ``pais`` se valida contra catálogo c_Pais (ISO 3166-1 alpha-3).
        - ``codigo_postal`` debe ser 5 dígitos cuando ``pais=MEX``; para
          países extranjeros se acepta cualquier formato razonable.
        - ``estado``, ``municipio``, ``colonia``, ``localidad`` aceptan
          string libre — la validación contra c_Estado/c_Municipio/etc.
          se difiere a Fase 3b (catálogos masivos).
    """

    calle: str | None = Field(default=None, min_length=1, max_length=100)
    numero_exterior: str | None = Field(default=None, min_length=1, max_length=55)
    numero_interior: str | None = Field(default=None, min_length=1, max_length=55)
    colonia: str | None = Field(default=None, min_length=1, max_length=120)
    localidad: str | None = Field(default=None, min_length=1, max_length=120)
    referencia: str | None = Field(default=None, min_length=1, max_length=250)
    municipio: str | None = Field(default=None, min_length=1, max_length=120)
    estado: str = Field(min_length=2, max_length=3)
    pais: str = Field(min_length=3, max_length=3)
    codigo_postal: str = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def _validar_catalogos(self) -> Domicilio:
        validar_pais(self.pais)
        if self.pais == "MEX" and not (
            len(self.codigo_postal) == 5 and self.codigo_postal.isdigit()
        ):
            raise ValueError(
                f"codigo_postal para pais=MEX debe ser 5 dígitos, recibido {self.codigo_postal!r}"
            )
        return self


__all__ = ["Domicilio"]
