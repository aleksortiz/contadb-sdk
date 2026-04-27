"""Constructor del XML del Complemento Carta Porte 3.1.

Este módulo solo ensambla ``lxml._Element``s — la lógica de validación
intra-modelo vive en los Pydantic de :mod:`.modelos` y las cruzadas en
:mod:`.validadores`.

API pública: :class:`CartaPorteBuilder` cumple el Protocol
:class:`~contadb_sdk.complementos.base.Complemento`, así que se inserta
en un CFDI vía ``CFDIBuilder.agregar_complemento(builder)``.

Diseño SRP: cada método ``_construir_*`` es responsable de un solo nodo
XML; las decisiones de cálculo (peso_bruto_total automático, IdCCP
auto-generado) son responsabilidad del builder, no de los modelos.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from decimal import Decimal
from typing import ClassVar

from lxml import etree

from ...exceptions import ValidationError
from ...xml_utils import fmt_dinero, fmt_tasa
from ..base import qname
from . import validadores
from .modelos import (
    Autotransporte,
    Domicilio,
    FiguraTransporte,
    IdentificacionVehicular,
    Mercancia,
    Remolque,
    Seguros,
    TiposFigura,
    Ubicacion,
)
from .tipos import (
    CARTA_PORTE_NS,
    CARTA_PORTE_PREFIJO,
    CARTA_PORTE_SCHEMA_LOCATION,
    CARTA_PORTE_VERSION,
    TranspInternacStr,
)


def _cp(tag: str) -> str:
    """Tag con namespace de Carta Porte 3.1 en notación Clark."""
    return qname(CARTA_PORTE_NS, tag)


def _generar_id_ccp() -> str:
    """Genera un IdCCP válido: 'CCP' + 33 chars hex en mayúsculas."""
    raw = (uuid.uuid4().hex + uuid.uuid4().hex)[:33].upper()
    return f"CCP{raw}"


class CartaPorteBuilder:
    """Constructor del bloque ``<cartaporte31:CartaPorte>``.

    El builder calcula automáticamente:
        - ``IdCCP`` (si no se pasa explícito).
        - ``PesoBrutoTotal`` y ``NumTotalMercancias`` desde la lista de
          mercancías.
        - El bloque ``<cartaporte31:Autotransporte>`` se inserta DENTRO
          de ``<cartaporte31:Mercancias>`` (así lo exige el XSD del SAT).

    Limitaciones Fase 3a:
        - Solo soporta autotransporte (no marítimo/aéreo/ferroviario).
        - ``transp_internac="No"`` por default; cuando se requiera "Sí"
          con campos aduaneros completos, ver Fase 3b.
    """

    # Cumplimiento del Protocol Complemento -------------------------------
    prefijo_ns: ClassVar[str] = CARTA_PORTE_PREFIJO
    uri_ns: ClassVar[str] = CARTA_PORTE_NS
    schema_location: ClassVar[str] = CARTA_PORTE_SCHEMA_LOCATION

    def __init__(
        self,
        *,
        transp_internac: TranspInternacStr = "No",
        total_dist_rec: Decimal,
        id_ccp: str | None = None,
        unidad_peso: str = "KGM",
    ) -> None:
        if total_dist_rec <= 0:
            raise ValidationError("total_dist_rec debe ser mayor a 0")
        self.transp_internac = transp_internac
        self.total_dist_rec = total_dist_rec
        self.id_ccp = id_ccp if id_ccp is not None else _generar_id_ccp()
        self.unidad_peso = unidad_peso

        self._ubicaciones: list[Ubicacion] = []
        self._mercancias: list[Mercancia] = []
        self._autotransporte: Autotransporte | None = None
        self._figura_transporte: FiguraTransporte | None = None

    # -- API fluida --------------------------------------------------------

    def agregar_ubicacion(self, ubicacion: Ubicacion) -> CartaPorteBuilder:
        if not isinstance(ubicacion, Ubicacion):
            raise ValidationError("ubicacion debe ser una instancia de Ubicacion")
        self._ubicaciones.append(ubicacion)
        return self

    def agregar_ubicaciones(self, ubicaciones: Iterable[Ubicacion]) -> CartaPorteBuilder:
        for u in ubicaciones:
            self.agregar_ubicacion(u)
        return self

    def agregar_mercancia(self, mercancia: Mercancia) -> CartaPorteBuilder:
        if not isinstance(mercancia, Mercancia):
            raise ValidationError("mercancia debe ser una instancia de Mercancia")
        self._mercancias.append(mercancia)
        return self

    def agregar_mercancias(self, mercancias: Iterable[Mercancia]) -> CartaPorteBuilder:
        for m in mercancias:
            self.agregar_mercancia(m)
        return self

    def establecer_autotransporte(self, autotransporte: Autotransporte) -> CartaPorteBuilder:
        if not isinstance(autotransporte, Autotransporte):
            raise ValidationError("autotransporte debe ser una instancia de Autotransporte")
        self._autotransporte = autotransporte
        return self

    def agregar_figura_transporte(self, figura_transporte: FiguraTransporte) -> CartaPorteBuilder:
        if not isinstance(figura_transporte, FiguraTransporte):
            raise ValidationError("figura_transporte debe ser una instancia de FiguraTransporte")
        self._figura_transporte = figura_transporte
        return self

    # -- Construcción del elemento ----------------------------------------

    def construir_elemento(self) -> etree._Element:
        if self._autotransporte is None:
            raise ValidationError(
                "CartaPorteBuilder requiere autotransporte (usa establecer_autotransporte)"
            )
        if self._figura_transporte is None:
            raise ValidationError(
                "CartaPorteBuilder requiere figura_transporte (usa agregar_figura_transporte)"
            )

        # Validaciones cruzadas
        validadores.validar_ubicaciones(self._ubicaciones)
        validadores.validar_distancia_total(self.total_dist_rec, self._ubicaciones)
        peso_bruto_total = sum((m.peso_en_kg for m in self._mercancias), Decimal("0"))
        num_total_mercancias = len(self._mercancias)
        validadores.validar_mercancias(self._mercancias, peso_bruto_total, num_total_mercancias)
        validadores.validar_seguros_material_peligroso(self._mercancias, self._autotransporte)
        validadores.validar_figura_transporte(self._figura_transporte)

        # Construir XML
        nsmap = {CARTA_PORTE_PREFIJO: CARTA_PORTE_NS}
        root = etree.Element(_cp("CartaPorte"), nsmap=nsmap)
        root.set("Version", CARTA_PORTE_VERSION)
        root.set("IdCCP", self.id_ccp)
        root.set("TranspInternac", self.transp_internac)
        root.set("TotalDistRec", fmt_dinero(self.total_dist_rec))

        self._construir_ubicaciones(root)
        self._construir_mercancias(root, peso_bruto_total, num_total_mercancias)
        self._construir_figura_transporte(root, self._figura_transporte)

        return root

    # -- Internos: cada método un solo nodo XML ---------------------------

    def _construir_ubicaciones(self, parent: etree._Element) -> None:
        ubicaciones_el = etree.SubElement(parent, _cp("Ubicaciones"))
        for ubicacion in self._ubicaciones:
            self._construir_ubicacion(ubicaciones_el, ubicacion)

    def _construir_ubicacion(self, parent: etree._Element, u: Ubicacion) -> None:
        el = etree.SubElement(parent, _cp("Ubicacion"))
        el.set("TipoUbicacion", u.tipo_ubicacion)
        if u.id_ubicacion is not None:
            el.set("IDUbicacion", u.id_ubicacion)
        el.set("RFCRemitenteDestinatario", u.rfc_remitente_destinatario)
        if u.nombre_remitente_destinatario is not None:
            el.set("NombreRemitenteDestinatario", u.nombre_remitente_destinatario)
        if u.num_reg_id_trib is not None:
            el.set("NumRegIdTrib", u.num_reg_id_trib)
        if u.residencia_fiscal is not None:
            el.set("ResidenciaFiscal", u.residencia_fiscal)
        el.set("FechaHoraSalidaLlegada", u.fecha_hora_salida_llegada.strftime("%Y-%m-%dT%H:%M:%S"))
        if u.distancia_recorrida is not None:
            el.set("DistanciaRecorrida", fmt_dinero(u.distancia_recorrida))
        if u.domicilio is not None:
            self._construir_domicilio(el, u.domicilio)

    @staticmethod
    def _construir_domicilio(parent: etree._Element, d: Domicilio) -> None:
        el = etree.SubElement(parent, _cp("Domicilio"))
        if d.calle is not None:
            el.set("Calle", d.calle)
        if d.numero_exterior is not None:
            el.set("NumeroExterior", d.numero_exterior)
        if d.numero_interior is not None:
            el.set("NumeroInterior", d.numero_interior)
        if d.colonia is not None:
            el.set("Colonia", d.colonia)
        if d.localidad is not None:
            el.set("Localidad", d.localidad)
        if d.referencia is not None:
            el.set("Referencia", d.referencia)
        if d.municipio is not None:
            el.set("Municipio", d.municipio)
        el.set("Estado", d.estado)
        el.set("Pais", d.pais)
        el.set("CodigoPostal", d.codigo_postal)

    def _construir_mercancias(
        self,
        parent: etree._Element,
        peso_bruto_total: Decimal,
        num_total_mercancias: int,
    ) -> None:
        # SAT exige que Autotransporte vaya dentro del nodo Mercancias.
        el = etree.SubElement(parent, _cp("Mercancias"))
        el.set("PesoBrutoTotal", fmt_dinero(peso_bruto_total))
        el.set("UnidadPeso", self.unidad_peso)
        el.set("NumTotalMercancias", str(num_total_mercancias))

        for mercancia in self._mercancias:
            self._construir_mercancia(el, mercancia)

        assert self._autotransporte is not None  # ya validado
        self._construir_autotransporte(el, self._autotransporte)

    @staticmethod
    def _construir_mercancia(parent: etree._Element, m: Mercancia) -> None:
        el = etree.SubElement(parent, _cp("Mercancia"))
        el.set("BienesTransp", m.bienes_transp)
        el.set("Descripcion", m.descripcion)
        el.set("Cantidad", fmt_tasa(m.cantidad))
        el.set("ClaveUnidad", m.clave_unidad)
        if m.unidad is not None:
            el.set("Unidad", m.unidad)
        if m.dimensiones is not None:
            el.set("Dimensiones", m.dimensiones)
        if m.material_peligroso is not None:
            el.set("MaterialPeligroso", m.material_peligroso)
        if m.cve_material_peligroso is not None:
            el.set("CveMaterialPeligroso", m.cve_material_peligroso)
        if m.embalaje is not None:
            el.set("Embalaje", m.embalaje)
        if m.descrip_embalaje is not None:
            el.set("DescripEmbalaje", m.descrip_embalaje)
        if m.sector_cofepris is not None:
            el.set("SectorCOFEPRIS", m.sector_cofepris)
        el.set("PesoEnKg", fmt_dinero(m.peso_en_kg))
        if m.valor_mercancia is not None:
            el.set("ValorMercancia", fmt_dinero(m.valor_mercancia))
        if m.moneda is not None:
            el.set("Moneda", m.moneda)
        if m.fraccion_arancelaria is not None:
            el.set("FraccionArancelaria", m.fraccion_arancelaria)
        if m.uuid_comercio_ext is not None:
            el.set("UUIDComercioExt", m.uuid_comercio_ext)

    def _construir_autotransporte(self, parent: etree._Element, a: Autotransporte) -> None:
        el = etree.SubElement(parent, _cp("Autotransporte"))
        el.set("PermSCT", a.perm_sct)
        el.set("NumPermisoSCT", a.num_permiso_sct)
        self._construir_identificacion_vehicular(el, a.identificacion_vehicular)
        self._construir_seguros(el, a.seguros)
        if a.remolques:
            self._construir_remolques(el, a.remolques)

    @staticmethod
    def _construir_identificacion_vehicular(
        parent: etree._Element, iv: IdentificacionVehicular
    ) -> None:
        el = etree.SubElement(parent, _cp("IdentificacionVehicular"))
        el.set("ConfigVehicular", iv.config_vehicular)
        el.set("PesoBrutoVehicular", fmt_dinero(iv.peso_bruto_vehicular))
        el.set("PlacaVM", iv.placa_vm)
        el.set("AnioModeloVM", str(iv.anio_modelo_vm))

    @staticmethod
    def _construir_seguros(parent: etree._Element, s: Seguros) -> None:
        el = etree.SubElement(parent, _cp("Seguros"))
        el.set("AseguraRespCivil", s.asegura_resp_civil)
        el.set("PolizaRespCivil", s.poliza_resp_civil)
        if s.asegura_med_ambiente is not None:
            el.set("AseguraMedAmbiente", s.asegura_med_ambiente)
        if s.poliza_med_ambiente is not None:
            el.set("PolizaMedAmbiente", s.poliza_med_ambiente)
        if s.asegura_carga is not None:
            el.set("AseguraCarga", s.asegura_carga)
        if s.poliza_carga is not None:
            el.set("PolizaCarga", s.poliza_carga)
        if s.prima_seguro is not None:
            el.set("PrimaSeguro", fmt_dinero(s.prima_seguro))

    @staticmethod
    def _construir_remolques(parent: etree._Element, remolques: list[Remolque]) -> None:
        el = etree.SubElement(parent, _cp("Remolques"))
        for r in remolques:
            r_el = etree.SubElement(el, _cp("Remolque"))
            r_el.set("SubTipoRem", r.sub_tipo_rem)
            r_el.set("Placa", r.placa)

    def _construir_figura_transporte(self, parent: etree._Element, ft: FiguraTransporte) -> None:
        el = etree.SubElement(parent, _cp("FiguraTransporte"))
        for figura in ft.figuras:
            self._construir_tipos_figura(el, figura)

    def _construir_tipos_figura(self, parent: etree._Element, f: TiposFigura) -> None:
        el = etree.SubElement(parent, _cp("TiposFigura"))
        el.set("TipoFigura", f.tipo_figura)
        el.set("RFCFigura", f.rfc_figura)
        if f.num_licencia is not None:
            el.set("NumLicencia", f.num_licencia)
        if f.nombre_figura is not None:
            el.set("NombreFigura", f.nombre_figura)
        if f.num_reg_id_trib_figura is not None:
            el.set("NumRegIdTribFigura", f.num_reg_id_trib_figura)
        if f.residencia_fiscal_figura is not None:
            el.set("ResidenciaFiscalFigura", f.residencia_fiscal_figura)
        if f.domicilio is not None:
            self._construir_domicilio(el, f.domicilio)


__all__ = ["CartaPorteBuilder"]
