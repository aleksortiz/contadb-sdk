"""Tests de generación de la cadena original vía XSLT del SAT."""

from __future__ import annotations

import pytest
from lxml import etree

from contadb_sdk import CFDIBuilder
from contadb_sdk.cadena import cadena_original
from contadb_sdk.exceptions import BuildError


def test_cadena_arranca_con_separadores(builder: CFDIBuilder) -> None:
    cadena = cadena_original(builder.construir_xml())
    assert cadena.startswith("||4.0|")
    assert cadena.endswith("||")


def test_cadena_contiene_campos_esperados(builder: CFDIBuilder) -> None:
    cadena = cadena_original(builder.construir_xml())
    # Serie, folio, RFC emisor/receptor, descripción del concepto
    assert "|A|1|" in cadena
    assert "EKU9003173C9" in cadena
    assert "URE180429TM6" in cadena
    assert "Servicios de consultoría en sistemas" in cadena


def test_cadena_acepta_string(builder: CFDIBuilder) -> None:
    xml_str = builder.construir_xml().decode("utf-8")
    cadena = cadena_original(xml_str)
    assert "|4.0|" in cadena


def test_cadena_acepta_element(builder: CFDIBuilder) -> None:
    root = etree.fromstring(builder.construir_xml())
    cadena = cadena_original(root)
    assert "|4.0|" in cadena


def test_xml_invalido_falla() -> None:
    with pytest.raises(BuildError, match="mal formado"):
        cadena_original("<comprobante incompleto")
