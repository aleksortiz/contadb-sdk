"""Tests del CartaPorteBuilder — construcción del bloque <cartaporte31:CartaPorte>."""

from __future__ import annotations

from decimal import Decimal

import pytest
from lxml import etree

from contadb_sdk import (
    Autotransporte,
    CartaPorteBuilder,
    Complemento,
    FiguraTransporte,
    Mercancia,
    Ubicacion,
    ValidationError,
)
from contadb_sdk.complementos.carta_porte.tipos import CARTA_PORTE_NS


def _xpath(el: etree._Element, path: str) -> list[etree._Element]:
    return el.xpath(path, namespaces={"cp": CARTA_PORTE_NS})


class TestCartaPorteBuilderBasico:
    def test_root_es_cartaporte(self, carta_porte_builder: CartaPorteBuilder) -> None:
        el = carta_porte_builder.construir_elemento()
        assert el.tag == f"{{{CARTA_PORTE_NS}}}CartaPorte"
        assert el.get("Version") == "3.1"
        assert el.get("TranspInternac") == "No"
        assert el.get("TotalDistRec") == "940.00"

    def test_id_ccp_auto_generado(self, carta_porte_builder: CartaPorteBuilder) -> None:
        el = carta_porte_builder.construir_elemento()
        id_ccp = el.get("IdCCP")
        assert id_ccp is not None
        assert id_ccp.startswith("CCP")
        assert len(id_ccp) == 36

    def test_id_ccp_explicito_se_respeta(
        self,
        origen: Ubicacion,
        destino: Ubicacion,
        mercancia_acero: Mercancia,
        autotransporte: Autotransporte,
        figura_transporte: FiguraTransporte,
    ) -> None:
        custom_id = "CCP" + "A" * 33
        cp = CartaPorteBuilder(
            transp_internac="No",
            total_dist_rec=Decimal("940"),
            id_ccp=custom_id,
        )
        cp.agregar_ubicacion(origen)
        cp.agregar_ubicacion(destino)
        cp.agregar_mercancia(mercancia_acero)
        cp.establecer_autotransporte(autotransporte)
        cp.agregar_figura_transporte(figura_transporte)
        el = cp.construir_elemento()
        assert el.get("IdCCP") == custom_id


class TestEstructuraXML:
    def test_ubicaciones(self, carta_porte_builder: CartaPorteBuilder) -> None:
        el = carta_porte_builder.construir_elemento()
        ubicaciones = _xpath(el, "cp:Ubicaciones/cp:Ubicacion")
        assert len(ubicaciones) == 2
        assert ubicaciones[0].get("TipoUbicacion") == "Origen"
        assert ubicaciones[1].get("TipoUbicacion") == "Destino"
        assert ubicaciones[1].get("DistanciaRecorrida") == "940.00"

    def test_domicilio_anidado(self, carta_porte_builder: CartaPorteBuilder) -> None:
        el = carta_porte_builder.construir_elemento()
        domicilios = _xpath(el, "cp:Ubicaciones/cp:Ubicacion/cp:Domicilio")
        assert len(domicilios) == 2
        assert domicilios[0].get("Pais") == "MEX"
        assert domicilios[0].get("CodigoPostal") == "64000"

    def test_mercancias_calculadas(self, carta_porte_builder: CartaPorteBuilder) -> None:
        el = carta_porte_builder.construir_elemento()
        mercancias = _xpath(el, "cp:Mercancias")[0]
        assert mercancias.get("PesoBrutoTotal") == "5000.00"
        assert mercancias.get("UnidadPeso") == "KGM"
        assert mercancias.get("NumTotalMercancias") == "1"

    def test_autotransporte_dentro_de_mercancias(
        self, carta_porte_builder: CartaPorteBuilder
    ) -> None:
        el = carta_porte_builder.construir_elemento()
        # SAT exige Autotransporte como hijo de Mercancias
        autos = _xpath(el, "cp:Mercancias/cp:Autotransporte")
        assert len(autos) == 1
        assert autos[0].get("PermSCT") == "TPAF01"

    def test_identificacion_vehicular(self, carta_porte_builder: CartaPorteBuilder) -> None:
        el = carta_porte_builder.construir_elemento()
        iv = _xpath(el, "cp:Mercancias/cp:Autotransporte/cp:IdentificacionVehicular")[0]
        assert iv.get("ConfigVehicular") == "T3S2"
        assert iv.get("PlacaVM") == "NLF1234"

    def test_seguros(self, carta_porte_builder: CartaPorteBuilder) -> None:
        el = carta_porte_builder.construir_elemento()
        seg = _xpath(el, "cp:Mercancias/cp:Autotransporte/cp:Seguros")[0]
        assert seg.get("AseguraRespCivil") == "QUALITAS"

    def test_figura_transporte(self, carta_porte_builder: CartaPorteBuilder) -> None:
        el = carta_porte_builder.construir_elemento()
        figuras = _xpath(el, "cp:FiguraTransporte/cp:TiposFigura")
        assert len(figuras) == 1
        assert figuras[0].get("TipoFigura") == "01"
        assert figuras[0].get("NumLicencia") == "A1234567"


class TestValidaciones:
    def test_sin_autotransporte_falla(
        self,
        origen: Ubicacion,
        destino: Ubicacion,
        mercancia_acero: Mercancia,
        figura_transporte: FiguraTransporte,
    ) -> None:
        cp = CartaPorteBuilder(transp_internac="No", total_dist_rec=Decimal("940"))
        cp.agregar_ubicacion(origen)
        cp.agregar_ubicacion(destino)
        cp.agregar_mercancia(mercancia_acero)
        cp.agregar_figura_transporte(figura_transporte)
        with pytest.raises(ValidationError, match="autotransporte"):
            cp.construir_elemento()

    def test_sin_figura_falla(
        self,
        origen: Ubicacion,
        destino: Ubicacion,
        mercancia_acero: Mercancia,
        autotransporte: Autotransporte,
    ) -> None:
        cp = CartaPorteBuilder(transp_internac="No", total_dist_rec=Decimal("940"))
        cp.agregar_ubicacion(origen)
        cp.agregar_ubicacion(destino)
        cp.agregar_mercancia(mercancia_acero)
        cp.establecer_autotransporte(autotransporte)
        with pytest.raises(ValidationError, match="figura_transporte"):
            cp.construir_elemento()

    def test_total_dist_negativo_falla(self) -> None:
        with pytest.raises(ValidationError, match="total_dist_rec"):
            CartaPorteBuilder(transp_internac="No", total_dist_rec=Decimal("-1"))

    def test_agregar_ubicacion_invalida(self) -> None:
        cp = CartaPorteBuilder(transp_internac="No", total_dist_rec=Decimal("100"))
        with pytest.raises(ValidationError):
            cp.agregar_ubicacion("not a ubicacion")  # type: ignore[arg-type]


class TestProtocolCompliance:
    def test_cumple_protocol_complemento(self, carta_porte_builder: CartaPorteBuilder) -> None:
        assert isinstance(carta_porte_builder, Complemento)
        assert CartaPorteBuilder.prefijo_ns == "cartaporte31"
        assert CartaPorteBuilder.uri_ns == CARTA_PORTE_NS
