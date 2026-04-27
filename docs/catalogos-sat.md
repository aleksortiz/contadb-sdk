# Catálogos SAT — claves comunes

Lista de las claves más usadas. Para los catálogos completos consulta el
[portal del SAT](https://www.sat.gob.mx/consultas/35025/formato-de-factura-electronica-(anexo-20)).

## TipoDeComprobante

| Clave | Descripción |
|-------|-------------|
| `I` | Ingreso |
| `E` | Egreso (notas de crédito) |
| `T` | Traslado |
| `P` | Pago (CFDI Pagos 2.0) |
| `N` | Nómina |

## MetodoPago

| Clave | Descripción |
|-------|-------------|
| `PUE` | Pago en una sola exhibición |
| `PPD` | Pago en parcialidades o diferido |

## FormaPago (más usadas)

| Clave | Descripción |
|-------|-------------|
| `01` | Efectivo |
| `02` | Cheque nominativo |
| `03` | Transferencia electrónica de fondos |
| `04` | Tarjeta de crédito |
| `05` | Monedero electrónico |
| `06` | Dinero electrónico |
| `08` | Vales de despensa |
| `28` | Tarjeta de débito |
| `29` | Tarjeta de servicios |
| `30` | Aplicación de anticipos |
| `99` | Por definir (solo PPD) |

## Exportacion

| Clave | Descripción |
|-------|-------------|
| `01` | No aplica |
| `02` | Definitiva |
| `03` | Temporal |
| `04` | Definitiva sin enajenación |

## ObjetoImp

| Clave | Descripción |
|-------|-------------|
| `01` | No objeto de impuesto |
| `02` | Sí objeto, con desglose |
| `03` | Sí objeto, sin desglose |

## UsoCFDI (más usadas)

| Clave | Descripción | Aplica a |
|-------|-------------|----------|
| `G01` | Adquisición de mercancías | PM/PF |
| `G02` | Devoluciones, descuentos o bonificaciones | PM/PF |
| `G03` | Gastos en general | PM/PF |
| `I01` | Construcciones | PM/PF |
| `I02` | Mobiliario y equipo de oficina | PM/PF |
| `I03` | Equipo de transporte | PM/PF |
| `I04` | Equipo de cómputo y accesorios | PM/PF |
| `I05` | Dados, troqueles, moldes y herramientas | PM/PF |
| `I06` | Comunicaciones telefónicas | PM/PF |
| `I07` | Comunicaciones satelitales | PM/PF |
| `I08` | Otra maquinaria y equipo | PM/PF |
| `D01` | Honorarios médicos, dentales, hospitalarios | PF |
| `D02` | Gastos médicos por incapacidad o discapacidad | PF |
| `D03` | Gastos funerales | PF |
| `D04` | Donativos | PF |
| `D05` | Intereses reales por créditos hipotecarios | PF |
| `D06` | Aportaciones voluntarias al SAR | PF |
| `D07` | Primas por seguros de gastos médicos | PF |
| `D08` | Gastos de transportación escolar | PF |
| `D09` | Depósitos en cuentas para el ahorro | PF |
| `D10` | Pagos por servicios educativos (colegiaturas) | PF |
| `S01` | Sin efectos fiscales (público en general) | Genérico |
| `CP01` | Pagos | Solo CFDI Pagos |
| `CN01` | Nómina | Solo CFDI Nómina |

## RegimenFiscal (Emisor)

| Clave | Descripción |
|-------|-------------|
| `601` | General de Ley Personas Morales |
| `603` | Personas Morales con Fines no Lucrativos |
| `605` | Sueldos y Salarios e Ingresos Asimilados |
| `606` | Arrendamiento |
| `607` | Régimen de Enajenación o Adquisición de Bienes |
| `608` | Demás ingresos |
| `610` | Residentes en el Extranjero sin Establecimiento Permanente |
| `611` | Ingresos por Dividendos (socios y accionistas) |
| `612` | Personas Físicas con Actividades Empresariales y Profesionales |
| `614` | Ingresos por intereses |
| `615` | Régimen de los ingresos por obtención de premios |
| `616` | Sin obligaciones fiscales (genérico, receptor "público en general") |
| `620` | Sociedades Cooperativas de Producción |
| `621` | Incorporación Fiscal (RIF — eliminado 2022) |
| `622` | Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras |
| `623` | Opcional para Grupos de Sociedades |
| `624` | Coordinados |
| `625` | Plataformas Tecnológicas |
| `626` | Régimen Simplificado de Confianza (RESICO) |

## Periodicidad (InformacionGlobal)

| Clave | Descripción |
|-------|-------------|
| `01` | Diario |
| `02` | Semanal |
| `03` | Quincenal |
| `04` | Mensual |
| `05` | Bimestral |

## Impuestos

| Clave | Descripción |
|-------|-------------|
| `001` | ISR |
| `002` | IVA |
| `003` | IEPS |

## ClaveProdServ y ClaveUnidad

Estos catálogos tienen miles de entradas. Consulta:

- **ClaveProdServ** (8 dígitos): https://www.sat.gob.mx/consulta/53693/catalogo-de-productos-y-servicios
- **ClaveUnidad**: https://www.sat.gob.mx/consulta/27015/catalogo-de-unidades-de-medida

Las más comunes:

| ClaveProdServ | Descripción |
|---------------|-------------|
| `01010101` | No existe en el catálogo (placeholder/genérico) |
| `43232408` | Software de aplicaciones (consultoría) |
| `80111501` | Servicios profesionales temporales |
| `80111601` | Outsourcing de personal |
| `84111506` | Servicios de facturación |

| ClaveUnidad | Descripción |
|-------------|-------------|
| `H87` | Pieza |
| `E48` | Unidad de servicio |
| `XBX` | Caja |
| `KGM` | Kilogramo |
| `MTR` | Metro |
| `LTR` | Litro |
| `HUR` | Hora |
| `DAY` | Día |
| `MON` | Mes |
| `ACT` | Actividad |
