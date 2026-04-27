"""Tests del modelo Ubicacion."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from contadb_sdk import Ubicacion


class TestUbicacion:
    def test_origen_basico(self) -> None:
        u = Ubicacion(
            tipo_ubicacion="Origen",
            rfc_remitente_destinatario="EKU9003173C9",
            fecha_hora_salida_llegada=datetime(2026, 4, 26, 6, 0, 0),
        )
        assert u.tipo_ubicacion == "Origen"
        assert u.distancia_recorrida is None

    def test_destino_requiere_distancia(self) -> None:
        with pytest.raises(PydanticValidationError, match="Destino' requiere distancia_recorrida"):
            Ubicacion(
                tipo_ubicacion="Destino",
                rfc_remitente_destinatario="URE180429TM6",
                fecha_hora_salida_llegada=datetime(2026, 4, 27, 14, 0, 0),
            )

    def test_origen_no_admite_distancia(self) -> None:
        with pytest.raises(PydanticValidationError, match="Origen' no debe declarar distancia"):
            Ubicacion(
                tipo_ubicacion="Origen",
                rfc_remitente_destinatario="EKU9003173C9",
                fecha_hora_salida_llegada=datetime(2026, 4, 26, 6, 0, 0),
                distancia_recorrida=Decimal("100"),
            )

    def test_id_ubicacion_pattern(self) -> None:
        # Origen debe empezar con OR; Destino con DE.
        with pytest.raises(PydanticValidationError):
            Ubicacion(
                tipo_ubicacion="Origen",
                id_ubicacion="XX123456",
                rfc_remitente_destinatario="EKU9003173C9",
                fecha_hora_salida_llegada=datetime(2026, 4, 26),
            )

    def test_rfc_publico_general_aceptado(self) -> None:
        u = Ubicacion(
            tipo_ubicacion="Origen",
            rfc_remitente_destinatario="XAXX010101000",
            fecha_hora_salida_llegada=datetime(2026, 4, 26),
        )
        assert u.rfc_remitente_destinatario == "XAXX010101000"
