"""Ubicaciones (Origen / Destino) del traslado.

Reglas SAT clave:
    - Mínimo 1 Ubicacion con TipoUbicacion="Origen" y 1 con "Destino".
    - El Destino debe declarar ``distancia_recorrida`` (km).
    - Las fechas/horas son obligatorias (salida del Origen, llegada del
      Destino).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..tipos import TipoUbicacionStr
from .comun import Domicilio


class _StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=False,
    )


class Ubicacion(_StrictModel):
    """Punto de origen o destino del traslado (``cartaporte31:Ubicacion``).

    Validaciones intra-modelo:
        - Si ``tipo_ubicacion="Origen"``: ``distancia_recorrida`` debe ser None.
        - Si ``tipo_ubicacion="Destino"``: ``distancia_recorrida`` es obligatorio.
        - El RFC es opcional pero, si se provee, debe seguir el patrón SAT
          (12-13 chars, formato persona física o moral).
    """

    tipo_ubicacion: TipoUbicacionStr
    id_ubicacion: str | None = Field(
        default=None,
        # IDOrigen: OR + 6 alfanuméricos. IDDestino: DE + 6 alfanuméricos.
        pattern=r"^(OR|DE)[A-Z0-9]{6}$",
    )
    rfc_remitente_destinatario: str = Field(
        pattern=r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$|^XEXX010101000$|^XAXX010101000$"
    )
    nombre_remitente_destinatario: str | None = Field(default=None, min_length=1, max_length=300)
    num_reg_id_trib: str | None = Field(default=None, min_length=6, max_length=40)
    residencia_fiscal: str | None = Field(default=None, min_length=3, max_length=3)
    fecha_hora_salida_llegada: datetime
    distancia_recorrida: Decimal | None = Field(default=None, ge=Decimal("0"))
    domicilio: Domicilio | None = None

    @model_validator(mode="after")
    def _validar_tipo_y_distancia(self) -> Ubicacion:
        if self.tipo_ubicacion == "Origen" and self.distancia_recorrida is not None:
            raise ValueError("Ubicacion 'Origen' no debe declarar distancia_recorrida")
        if self.tipo_ubicacion == "Destino" and self.distancia_recorrida is None:
            raise ValueError("Ubicacion 'Destino' requiere distancia_recorrida (km)")
        return self


__all__ = ["Ubicacion"]
