"""Mercancia transportada (``cartaporte31:Mercancia``).

Fase 3a — campos directos solamente. Diferidos a Fase 3b:
    - ``DocumentacionAduanera``, ``GuiasIdentificacion``, ``Pedimentos``
    - ``CantidadTransporta`` (cuando se reparte entre destinos)
    - ``DetalleMercancia`` (peso/volumen/dimensiones detalladas)
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..tipos import MaterialPeligrosoStr


class _StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=False,
    )


class Mercancia(_StrictModel):
    """Una línea de mercancía transportada.

    Validaciones intra-modelo:
        - Si ``material_peligroso="Sí"``: ``cve_material_peligroso``,
          ``embalaje`` y ``descrip_embalaje`` son obligatorios.
        - Si ``material_peligroso="No"`` u omitido: esos campos deben ser None.
    """

    bienes_transp: str = Field(min_length=8, max_length=8, pattern=r"^\d{8}$")
    descripcion: str = Field(min_length=1, max_length=300)
    cantidad: Decimal = Field(gt=Decimal("0"))
    clave_unidad: str = Field(min_length=1, max_length=20)
    unidad: str | None = Field(default=None, min_length=1, max_length=50)
    dimensiones: str | None = Field(default=None, min_length=1, max_length=50)
    material_peligroso: MaterialPeligrosoStr | None = None
    cve_material_peligroso: str | None = Field(default=None, min_length=1, max_length=10)
    embalaje: str | None = Field(default=None, min_length=1, max_length=10)
    descrip_embalaje: str | None = Field(default=None, min_length=1, max_length=300)
    sector_cofepris: str | None = Field(default=None, min_length=1, max_length=10)
    peso_en_kg: Decimal = Field(gt=Decimal("0"))
    valor_mercancia: Decimal | None = Field(default=None, ge=Decimal("0"))
    moneda: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    fraccion_arancelaria: str | None = Field(default=None, pattern=r"^\d{8,10}$")
    uuid_comercio_ext: str | None = Field(
        default=None,
        pattern=(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
        ),
    )

    @model_validator(mode="after")
    def _coherencia_material_peligroso(self) -> Mercancia:
        es_peligroso = self.material_peligroso == "Sí"
        campos_peligroso = (self.cve_material_peligroso, self.embalaje, self.descrip_embalaje)
        if es_peligroso and not all(campos_peligroso):
            raise ValueError(
                "material_peligroso='Sí' requiere cve_material_peligroso, "
                "embalaje y descrip_embalaje"
            )
        if not es_peligroso and any(campos_peligroso):
            raise ValueError(
                "cve_material_peligroso/embalaje/descrip_embalaje solo son válidos "
                "cuando material_peligroso='Sí'"
            )
        return self

    @model_validator(mode="after")
    def _coherencia_valor_moneda(self) -> Mercancia:
        if self.valor_mercancia is not None and self.moneda is None:
            raise ValueError("valor_mercancia requiere declarar moneda")
        if self.moneda is not None and self.valor_mercancia is None:
            raise ValueError("moneda requiere declarar valor_mercancia")
        return self


__all__ = ["Mercancia"]
