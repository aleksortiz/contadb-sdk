"""Tests del modelo Mercancia."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from contadb_sdk import Mercancia


class TestMercancia:
    def test_mercancia_no_peligrosa(self) -> None:
        m = Mercancia(
            bienes_transp="11161703",
            descripcion="Acero",
            cantidad=Decimal("100"),
            clave_unidad="KGM",
            peso_en_kg=Decimal("100"),
            material_peligroso="No",
        )
        assert m.material_peligroso == "No"

    def test_peligrosa_requiere_cve_embalaje(self) -> None:
        with pytest.raises(PydanticValidationError, match="material_peligroso='Sí' requiere"):
            Mercancia(
                bienes_transp="11161703",
                descripcion="Material",
                cantidad=Decimal("1"),
                clave_unidad="KGM",
                peso_en_kg=Decimal("1"),
                material_peligroso="Sí",
            )

    def test_no_peligrosa_no_admite_cve(self) -> None:
        with pytest.raises(PydanticValidationError, match="solo son válidos"):
            Mercancia(
                bienes_transp="11161703",
                descripcion="Acero",
                cantidad=Decimal("1"),
                clave_unidad="KGM",
                peso_en_kg=Decimal("1"),
                material_peligroso="No",
                cve_material_peligroso="UN1234",
                embalaje="4G",
                descrip_embalaje="Caja de cartón",
            )

    def test_peligrosa_completa(self) -> None:
        m = Mercancia(
            bienes_transp="11161703",
            descripcion="Material peligroso",
            cantidad=Decimal("1"),
            clave_unidad="KGM",
            peso_en_kg=Decimal("1"),
            material_peligroso="Sí",
            cve_material_peligroso="UN1234",
            embalaje="4G",
            descrip_embalaje="Caja de cartón",
        )
        assert m.cve_material_peligroso == "UN1234"

    def test_valor_requiere_moneda(self) -> None:
        with pytest.raises(PydanticValidationError, match="valor_mercancia requiere"):
            Mercancia(
                bienes_transp="11161703",
                descripcion="X",
                cantidad=Decimal("1"),
                clave_unidad="KGM",
                peso_en_kg=Decimal("1"),
                valor_mercancia=Decimal("1000"),
            )

    def test_clave_prod_serv_invalida(self) -> None:
        with pytest.raises(PydanticValidationError):
            Mercancia(
                bienes_transp="123",  # debe ser 8 dígitos
                descripcion="X",
                cantidad=Decimal("1"),
                clave_unidad="KGM",
                peso_en_kg=Decimal("1"),
            )
