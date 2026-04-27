"""Constructor de CFDI 4.0 con cálculo automático de impuestos y firma.

Uso típico::

    builder = (
        CFDIBuilder(emisor=..., receptor=..., serie="A", folio="1",
                    forma_pago="03", metodo_pago="PUE", lugar_expedicion="64000")
        .agregar_concepto(Concepto(...))
    )
    xml = builder.construir_y_firmar(certificate)

El builder calcula automáticamente:
    - Importe = Cantidad * ValorUnitario por concepto
    - Base = Importe - Descuento por concepto
    - Importe del traslado/retención = Base * TasaOCuota (redondeado a 2 dec)
    - SubTotal, Descuento, totales de impuestos y Total del comprobante
    - Bloque cfdi:Impuestos consolidado por impuesto/tipo_factor/tasa
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import cast

from lxml import etree

from .cadena import cadena_original
from .catalogs import (
    CFDI_VERSION,
    IMPUESTO_IEPS,
    IMPUESTO_ISR,
    IMPUESTO_IVA,
    MONEDA_MXN,
)
from .complementos.base import Complemento
from .exceptions import ValidationError
from .models import (
    Concepto,
    Emisor,
    ExportacionStr,
    InformacionGlobal,
    MetodoPagoStr,
    Receptor,
    TipoComprobanteStr,
)
from .signer import Certificado
from .xml_utils import (
    NSMAP,
    SCHEMA_LOCATION,
    cfdi,
    cuantizar_dinero,
    fmt_cantidad,
    fmt_dinero,
    fmt_tasa,
)

NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"


class _ConceptoCalculado:
    """Concepto con sus importes ya calculados."""

    def __init__(self, c: Concepto) -> None:
        self.input = c
        self.importe: Decimal = cuantizar_dinero(c.cantidad * c.valor_unitario)
        self.descuento: Decimal | None = (
            cuantizar_dinero(c.descuento) if c.descuento is not None else None
        )
        self.base: Decimal = self.importe - (self.descuento or Decimal("0"))
        self.traslados: list[_ImpuestoCalculado] = []
        self.retenciones: list[_ImpuestoCalculado] = []
        self._calcular_impuestos()

    def _calcular_impuestos(self) -> None:
        c = self.input
        if c.objeto_imp not in ("02", "03"):
            return

        # Traslados
        if c.iva_exento:
            self.traslados.append(
                _ImpuestoCalculado(
                    impuesto=IMPUESTO_IVA,
                    tipo_factor="Exento",
                    base=self.base,
                    tasa=None,
                    importe=None,
                )
            )
        elif c.tasa_iva is not None:
            self.traslados.append(
                _ImpuestoCalculado(
                    impuesto=IMPUESTO_IVA,
                    tipo_factor="Tasa",
                    base=self.base,
                    tasa=c.tasa_iva,
                    importe=cuantizar_dinero(self.base * c.tasa_iva),
                )
            )
        if c.tasa_ieps is not None and c.tasa_ieps > 0:
            self.traslados.append(
                _ImpuestoCalculado(
                    impuesto=IMPUESTO_IEPS,
                    tipo_factor="Tasa",
                    base=self.base,
                    tasa=c.tasa_ieps,
                    importe=cuantizar_dinero(self.base * c.tasa_ieps),
                )
            )

        # Retenciones
        if c.tasa_retencion_isr is not None and c.tasa_retencion_isr > 0:
            self.retenciones.append(
                _ImpuestoCalculado(
                    impuesto=IMPUESTO_ISR,
                    tipo_factor="Tasa",
                    base=self.base,
                    tasa=c.tasa_retencion_isr,
                    importe=cuantizar_dinero(self.base * c.tasa_retencion_isr),
                )
            )
        if c.tasa_retencion_iva is not None and c.tasa_retencion_iva > 0:
            self.retenciones.append(
                _ImpuestoCalculado(
                    impuesto=IMPUESTO_IVA,
                    tipo_factor="Tasa",
                    base=self.base,
                    tasa=c.tasa_retencion_iva,
                    importe=cuantizar_dinero(self.base * c.tasa_retencion_iva),
                )
            )
        if c.tasa_retencion_ieps is not None and c.tasa_retencion_ieps > 0:
            self.retenciones.append(
                _ImpuestoCalculado(
                    impuesto=IMPUESTO_IEPS,
                    tipo_factor="Tasa",
                    base=self.base,
                    tasa=c.tasa_retencion_ieps,
                    importe=cuantizar_dinero(self.base * c.tasa_retencion_ieps),
                )
            )


class _ImpuestoCalculado:
    __slots__ = ("base", "importe", "impuesto", "tasa", "tipo_factor")

    def __init__(
        self,
        *,
        impuesto: str,
        tipo_factor: str,
        base: Decimal,
        tasa: Decimal | None,
        importe: Decimal | None,
    ) -> None:
        self.impuesto = impuesto
        self.tipo_factor = tipo_factor
        self.base = base
        self.tasa = tasa
        self.importe = importe


class CFDIBuilder:
    """Constructor fluido de CFDI 4.0."""

    def __init__(
        self,
        *,
        emisor: Emisor,
        receptor: Receptor,
        lugar_expedicion: str,
        serie: str | None = None,
        folio: str | None = None,
        fecha: datetime | None = None,
        forma_pago: str | None = None,
        metodo_pago: MetodoPagoStr | None = "PUE",
        moneda: str = MONEDA_MXN,
        tipo_cambio: Decimal | None = None,
        tipo_comprobante: TipoComprobanteStr = "I",
        exportacion: ExportacionStr = "01",
        condiciones_pago: str | None = None,
        informacion_global: InformacionGlobal | None = None,
    ) -> None:
        if not isinstance(emisor, Emisor):
            raise ValidationError("emisor debe ser una instancia de Emisor")
        if not isinstance(receptor, Receptor):
            raise ValidationError("receptor debe ser una instancia de Receptor")
        if not lugar_expedicion or len(lugar_expedicion) != 5 or not lugar_expedicion.isdigit():
            raise ValidationError("lugar_expedicion debe ser CP de 5 dígitos")
        if moneda != MONEDA_MXN and moneda != "XXX" and tipo_cambio is None:
            raise ValidationError(f"tipo_cambio es obligatorio cuando moneda no es {MONEDA_MXN}")
        if moneda == MONEDA_MXN and tipo_cambio is not None:
            raise ValidationError(f"tipo_cambio no debe declararse cuando moneda={MONEDA_MXN}")
        if tipo_comprobante in ("I", "E") and not forma_pago:
            raise ValidationError(f"forma_pago es obligatorio para CFDI tipo '{tipo_comprobante}'")
        if tipo_comprobante in ("I", "E") and metodo_pago is None:
            raise ValidationError(f"metodo_pago es obligatorio para CFDI tipo '{tipo_comprobante}'")
        if tipo_comprobante == "P":
            self._validar_reglas_tipo_pago(
                moneda=moneda,
                metodo_pago=metodo_pago,
                forma_pago=forma_pago,
                condiciones_pago=condiciones_pago,
                tipo_cambio=tipo_cambio,
            )
        if tipo_comprobante == "T":
            self._validar_reglas_tipo_traslado(
                moneda=moneda,
                metodo_pago=metodo_pago,
                forma_pago=forma_pago,
                condiciones_pago=condiciones_pago,
                tipo_cambio=tipo_cambio,
            )

        self.emisor = emisor
        self.receptor = receptor
        self.serie = serie
        self.folio = folio
        self.fecha = fecha or datetime.now().replace(microsecond=0)
        self.forma_pago = forma_pago
        self.metodo_pago = metodo_pago
        self.moneda = moneda
        self.tipo_cambio = tipo_cambio
        self.tipo_comprobante = tipo_comprobante
        self.exportacion = exportacion
        self.condiciones_pago = condiciones_pago
        self.lugar_expedicion = lugar_expedicion
        self.informacion_global = informacion_global

        self._conceptos: list[Concepto] = []
        self._complementos: list[Complemento] = []

    @staticmethod
    def _validar_reglas_tipo_pago(
        *,
        moneda: str,
        metodo_pago: MetodoPagoStr | None,
        forma_pago: str | None,
        condiciones_pago: str | None,
        tipo_cambio: Decimal | None,
    ) -> None:
        """SAT: en CFDI tipo 'P' la moneda es XXX y no aplican forma/método/condiciones de pago."""
        if moneda != "XXX":
            raise ValidationError("CFDI tipo 'P' requiere moneda='XXX'")
        if metodo_pago is not None:
            raise ValidationError("CFDI tipo 'P' no admite metodo_pago")
        if forma_pago is not None:
            raise ValidationError("CFDI tipo 'P' no admite forma_pago")
        if condiciones_pago is not None:
            raise ValidationError("CFDI tipo 'P' no admite condiciones_pago")
        if tipo_cambio is not None:
            raise ValidationError("CFDI tipo 'P' no admite tipo_cambio")

    @staticmethod
    def _validar_reglas_tipo_traslado(
        *,
        moneda: str,
        metodo_pago: MetodoPagoStr | None,
        forma_pago: str | None,
        condiciones_pago: str | None,
        tipo_cambio: Decimal | None,
    ) -> None:
        """SAT: en CFDI tipo 'T' (Traslado) la moneda es XXX y no aplica método/forma de pago."""
        if moneda != "XXX":
            raise ValidationError("CFDI tipo 'T' requiere moneda='XXX'")
        if metodo_pago is not None:
            raise ValidationError("CFDI tipo 'T' no admite metodo_pago")
        if forma_pago is not None:
            raise ValidationError("CFDI tipo 'T' no admite forma_pago")
        if condiciones_pago is not None:
            raise ValidationError("CFDI tipo 'T' no admite condiciones_pago")
        if tipo_cambio is not None:
            raise ValidationError("CFDI tipo 'T' no admite tipo_cambio")

    # -- Factories ---------------------------------------------------------

    @classmethod
    def para_pago(
        cls,
        *,
        emisor: Emisor,
        receptor: Receptor,
        lugar_expedicion: str,
        serie: str | None = None,
        folio: str | None = None,
        fecha: datetime | None = None,
        exportacion: ExportacionStr = "01",
    ) -> CFDIBuilder:
        """Constructor para un CFDI tipo 'P' (Recepción de Pagos).

        Pre-configura los valores que el SAT exige para este tipo y agrega
        el concepto único requerido (clave 84111506, valor 0). El llamador
        solo debe agregar el complemento de Pagos vía
        :meth:`agregar_complemento`.
        """
        from .complementos.pagos.tipos import (
            CLAVE_PROD_SERV_PAGO,
            CLAVE_UNIDAD_PAGO,
            DESCRIPCION_PAGO,
            MONEDA_COMPROBANTE_PAGO,
        )

        builder = cls(
            emisor=emisor,
            receptor=receptor,
            lugar_expedicion=lugar_expedicion,
            serie=serie,
            folio=folio,
            fecha=fecha,
            forma_pago=None,
            metodo_pago=None,
            moneda=MONEDA_COMPROBANTE_PAGO,
            tipo_cambio=None,
            tipo_comprobante="P",
            exportacion=exportacion,
        )
        builder.agregar_concepto(
            Concepto(
                clave_prod_serv=CLAVE_PROD_SERV_PAGO,
                clave_unidad=CLAVE_UNIDAD_PAGO,
                descripcion=DESCRIPCION_PAGO,
                cantidad=Decimal("1"),
                valor_unitario=Decimal("0"),
                objeto_imp="01",
            )
        )
        return builder

    @classmethod
    def para_traslado(
        cls,
        *,
        emisor: Emisor,
        receptor: Receptor,
        lugar_expedicion: str,
        serie: str | None = None,
        folio: str | None = None,
        fecha: datetime | None = None,
        exportacion: ExportacionStr = "01",
    ) -> CFDIBuilder:
        """Constructor para un CFDI tipo 'T' (Traslado de mercancía).

        Pre-configura los valores que el SAT exige para este tipo y agrega
        el concepto único requerido (clave 78101803, valor 0). El llamador
        solo debe agregar el complemento de Carta Porte vía
        :meth:`agregar_complemento`.
        """
        from .complementos.carta_porte.tipos import (
            CLAVE_PROD_SERV_TRASLADO,
            CLAVE_UNIDAD_TRASLADO,
            DESCRIPCION_TRASLADO,
        )

        builder = cls(
            emisor=emisor,
            receptor=receptor,
            lugar_expedicion=lugar_expedicion,
            serie=serie,
            folio=folio,
            fecha=fecha,
            forma_pago=None,
            metodo_pago=None,
            moneda="XXX",
            tipo_cambio=None,
            tipo_comprobante="T",
            exportacion=exportacion,
        )
        builder.agregar_concepto(
            Concepto(
                clave_prod_serv=CLAVE_PROD_SERV_TRASLADO,
                clave_unidad=CLAVE_UNIDAD_TRASLADO,
                descripcion=DESCRIPCION_TRASLADO,
                cantidad=Decimal("1"),
                valor_unitario=Decimal("0"),
                objeto_imp="01",
            )
        )
        return builder

    # -- API fluida --------------------------------------------------------

    def agregar_concepto(self, concepto: Concepto) -> CFDIBuilder:
        if not isinstance(concepto, Concepto):
            raise ValidationError("concepto debe ser una instancia de Concepto")
        self._conceptos.append(concepto)
        return self

    def agregar_conceptos(self, conceptos: Iterable[Concepto]) -> CFDIBuilder:
        for c in conceptos:
            self.agregar_concepto(c)
        return self

    def agregar_complemento(self, complemento: Complemento) -> CFDIBuilder:
        """Agrega un complemento (ej. Pagos 2.0) al comprobante.

        Acepta cualquier objeto que cumpla el Protocol
        :class:`~contadb_sdk.complementos.base.Complemento`.
        """
        if not isinstance(complemento, Complemento):
            raise ValidationError(
                "complemento debe cumplir el Protocol Complemento "
                "(prefijo_ns, uri_ns, schema_location, construir_elemento)"
            )
        self._complementos.append(complemento)
        return self

    # -- Construcción ------------------------------------------------------

    def construir_xml(self) -> bytes:
        """Construye el XML CFDI **sin sello ni certificado** (útil para inspección)."""
        return self._construir_raiz(cert=None)

    def construir_y_firmar(self, cert: Certificado) -> str:
        """Construye, firma y devuelve el XML CFDI listo para timbrar.

        El proceso:
            1. Construye el XML con NoCertificado y Certificado del CSD.
            2. Genera la cadena original vía XSLT del SAT.
            3. Firma con la llave privada (RSA-SHA256, PKCS#1 v1.5).
            4. Inyecta el atributo Sello.
            5. Devuelve el XML como string UTF-8.
        """
        if not isinstance(cert, Certificado):
            raise ValidationError("cert debe ser una instancia de Certificado")
        if cert.rfc is not None and cert.rfc.upper() != self.emisor.rfc.upper():
            raise ValidationError(
                f"El RFC del certificado ({cert.rfc}) no coincide con el del emisor "
                f"({self.emisor.rfc})"
            )
        xml_bytes = self._construir_raiz(cert=cert)
        root = etree.fromstring(xml_bytes)
        cadena = cadena_original(root)
        sello = cert.firmar(cadena)
        root.set("Sello", sello)
        result_bytes = cast(bytes, etree.tostring(root, encoding="UTF-8", xml_declaration=True))
        return result_bytes.decode("utf-8")

    # -- Internos ----------------------------------------------------------

    def _construir_raiz(self, *, cert: Certificado | None) -> bytes:
        if not self._conceptos:
            raise ValidationError("El comprobante debe tener al menos un concepto")

        calculados = [_ConceptoCalculado(c) for c in self._conceptos]

        sub_total = sum((c.importe for c in calculados), Decimal("0"))
        descuento_total = sum(
            (c.descuento for c in calculados if c.descuento is not None),
            Decimal("0"),
        )

        total_traslados = sum(
            (t.importe for c in calculados for t in c.traslados if t.importe is not None),
            Decimal("0"),
        )
        total_retenciones = sum(
            (r.importe for c in calculados for r in c.retenciones if r.importe is not None),
            Decimal("0"),
        )

        total = sub_total - descuento_total + total_traslados - total_retenciones

        attrs: dict[str, str] = {
            "Version": CFDI_VERSION,
            "Fecha": self.fecha.strftime("%Y-%m-%dT%H:%M:%S"),
            "SubTotal": fmt_dinero(sub_total),
            "Moneda": self.moneda,
            "Total": fmt_dinero(total),
            "TipoDeComprobante": self.tipo_comprobante,
            "Exportacion": self.exportacion,
            "LugarExpedicion": self.lugar_expedicion,
        }
        if cert is not None:
            attrs["NoCertificado"] = cert.no_certificado
            attrs["Certificado"] = cert.certificado_b64
            attrs["Sello"] = ""
        if self.serie is not None:
            attrs["Serie"] = self.serie
        if self.folio is not None:
            attrs["Folio"] = self.folio
        if self.forma_pago is not None:
            attrs["FormaPago"] = self.forma_pago
        if self.metodo_pago is not None:
            attrs["MetodoPago"] = self.metodo_pago
        if self.condiciones_pago is not None:
            attrs["CondicionesDePago"] = self.condiciones_pago
        if descuento_total > 0:
            attrs["Descuento"] = fmt_dinero(descuento_total)
        if self.tipo_cambio is not None:
            attrs["TipoCambio"] = fmt_tasa(self.tipo_cambio)

        # nsmap y schemaLocation incluyen los complementos registrados.
        nsmap = dict(NSMAP)
        schema_locs = [SCHEMA_LOCATION]
        for comp in self._complementos:
            if comp.prefijo_ns in nsmap and nsmap[comp.prefijo_ns] != comp.uri_ns:
                raise ValidationError(f"Conflicto de prefijo de namespace '{comp.prefijo_ns}'")
            nsmap[comp.prefijo_ns] = comp.uri_ns
            schema_locs.append(comp.schema_location)

        root = etree.Element(cfdi("Comprobante"), nsmap=nsmap)
        root.set(f"{{{NS_XSI}}}schemaLocation", " ".join(schema_locs))
        for k, v in attrs.items():
            root.set(k, v)

        # cfdi:InformacionGlobal (si aplica) — debe ir antes de Emisor
        if self.informacion_global is not None:
            info = etree.SubElement(root, cfdi("InformacionGlobal"))
            info.set("Periodicidad", self.informacion_global.periodicidad)
            info.set("Meses", self.informacion_global.meses)
            info.set("Año", str(self.informacion_global.año))

        # cfdi:Emisor
        emisor_el = etree.SubElement(root, cfdi("Emisor"))
        emisor_el.set("Rfc", self.emisor.rfc)
        emisor_el.set("Nombre", self.emisor.nombre)
        emisor_el.set("RegimenFiscal", self.emisor.regimen_fiscal)

        # cfdi:Receptor
        receptor_el = etree.SubElement(root, cfdi("Receptor"))
        receptor_el.set("Rfc", self.receptor.rfc)
        receptor_el.set("Nombre", self.receptor.nombre)
        receptor_el.set("DomicilioFiscalReceptor", self.receptor.domicilio_fiscal_receptor)
        if self.receptor.residencia_fiscal:
            receptor_el.set("ResidenciaFiscal", self.receptor.residencia_fiscal)
        if self.receptor.num_reg_id_trib:
            receptor_el.set("NumRegIdTrib", self.receptor.num_reg_id_trib)
        receptor_el.set("RegimenFiscalReceptor", self.receptor.regimen_fiscal_receptor)
        receptor_el.set("UsoCFDI", self.receptor.uso_cfdi)

        # cfdi:Conceptos
        conceptos_el = etree.SubElement(root, cfdi("Conceptos"))
        for c in calculados:
            self._agregar_concepto_xml(conceptos_el, c)

        # cfdi:Impuestos consolidado — incluye también el caso "todo exento",
        # donde no hay total trasladado pero el SAT exige el bloque con los
        # traslados Exento listados.
        hay_traslados_exentos = any(
            t.tipo_factor == "Exento" for c in calculados for t in c.traslados
        )
        if total_traslados > 0 or total_retenciones > 0 or hay_traslados_exentos:
            self._agregar_impuestos_resumen(root, calculados, total_traslados, total_retenciones)

        # cfdi:Complemento (si hay complementos registrados)
        if self._complementos:
            comp_el = etree.SubElement(root, cfdi("Complemento"))
            for comp in self._complementos:
                comp_el.append(comp.construir_elemento())

        return cast(bytes, etree.tostring(root, encoding="UTF-8", xml_declaration=True))

    def _agregar_concepto_xml(self, parent: etree._Element, c: _ConceptoCalculado) -> None:
        ci = c.input
        el = etree.SubElement(parent, cfdi("Concepto"))
        el.set("ClaveProdServ", ci.clave_prod_serv)
        if ci.no_identificacion:
            el.set("NoIdentificacion", ci.no_identificacion)
        el.set("Cantidad", fmt_cantidad(ci.cantidad))
        el.set("ClaveUnidad", ci.clave_unidad)
        if ci.unidad:
            el.set("Unidad", ci.unidad)
        el.set("Descripcion", ci.descripcion)
        el.set("ValorUnitario", fmt_dinero(ci.valor_unitario))
        el.set("Importe", fmt_dinero(c.importe))
        if c.descuento is not None:
            el.set("Descuento", fmt_dinero(c.descuento))
        el.set("ObjetoImp", ci.objeto_imp)

        if c.traslados or c.retenciones:
            imp_el = etree.SubElement(el, cfdi("Impuestos"))
            if c.traslados:
                tras_el = etree.SubElement(imp_el, cfdi("Traslados"))
                for t in c.traslados:
                    self._agregar_traslado_concepto(tras_el, t)
            if c.retenciones:
                ret_el = etree.SubElement(imp_el, cfdi("Retenciones"))
                for r in c.retenciones:
                    self._agregar_retencion_concepto(ret_el, r)

    def _agregar_traslado_concepto(self, parent: etree._Element, t: _ImpuestoCalculado) -> None:
        el = etree.SubElement(parent, cfdi("Traslado"))
        el.set("Base", fmt_dinero(t.base))
        el.set("Impuesto", t.impuesto)
        el.set("TipoFactor", t.tipo_factor)
        if t.tasa is not None:
            el.set("TasaOCuota", fmt_tasa(t.tasa))
        if t.importe is not None:
            el.set("Importe", fmt_dinero(t.importe))

    def _agregar_retencion_concepto(self, parent: etree._Element, r: _ImpuestoCalculado) -> None:
        el = etree.SubElement(parent, cfdi("Retencion"))
        el.set("Base", fmt_dinero(r.base))
        el.set("Impuesto", r.impuesto)
        el.set("TipoFactor", r.tipo_factor)
        if r.tasa is not None:
            el.set("TasaOCuota", fmt_tasa(r.tasa))
        if r.importe is not None:
            el.set("Importe", fmt_dinero(r.importe))

    def _agregar_impuestos_resumen(
        self,
        parent: etree._Element,
        calculados: list[_ConceptoCalculado],
        total_traslados: Decimal,
        total_retenciones: Decimal,
    ) -> None:
        imp_el = etree.SubElement(parent, cfdi("Impuestos"))
        if total_retenciones > 0:
            imp_el.set("TotalImpuestosRetenidos", fmt_dinero(total_retenciones))
        if total_traslados > 0:
            imp_el.set("TotalImpuestosTrasladados", fmt_dinero(total_traslados))

        # Retenciones consolidadas por impuesto
        retenciones_por_imp: dict[str, Decimal] = {}
        for c in calculados:
            for r in c.retenciones:
                if r.importe is None:
                    continue
                retenciones_por_imp[r.impuesto] = (
                    retenciones_por_imp.get(r.impuesto, Decimal("0")) + r.importe
                )
        if retenciones_por_imp:
            ret_el = etree.SubElement(imp_el, cfdi("Retenciones"))
            for impuesto, importe in sorted(retenciones_por_imp.items()):
                r = etree.SubElement(ret_el, cfdi("Retencion"))
                r.set("Impuesto", impuesto)
                r.set("Importe", fmt_dinero(importe))

        # Traslados consolidados por (Impuesto, TipoFactor, Tasa)
        traslados_grouped: dict[tuple[str, str, str], tuple[Decimal, Decimal]] = {}
        # value: (base_total, importe_total)
        for c in calculados:
            for t in c.traslados:
                tasa_str = fmt_tasa(t.tasa) if t.tasa is not None else ""
                key = (t.impuesto, t.tipo_factor, tasa_str)
                base_acc, imp_acc = traslados_grouped.get(key, (Decimal("0"), Decimal("0")))
                base_acc += t.base
                if t.importe is not None:
                    imp_acc += t.importe
                traslados_grouped[key] = (base_acc, imp_acc)

        if traslados_grouped:
            tras_el = etree.SubElement(imp_el, cfdi("Traslados"))
            for (impuesto, tipo_factor, tasa_str), (base, importe) in sorted(
                traslados_grouped.items()
            ):
                t = etree.SubElement(tras_el, cfdi("Traslado"))
                t.set("Base", fmt_dinero(base))
                t.set("Impuesto", impuesto)
                t.set("TipoFactor", tipo_factor)
                if tasa_str:
                    t.set("TasaOCuota", tasa_str)
                    t.set("Importe", fmt_dinero(importe))


__all__ = ["CFDIBuilder"]
