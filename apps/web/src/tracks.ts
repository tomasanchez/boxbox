/**
 * Geometría del circuito, tomada tal cual del concepto de diseño.
 *
 * El path es exactamente el que trae `Simulador F1.dc.html`, que a su vez
 * proviene de f1-circuits (GeoJSON sobre OpenStreetMap, ODbL). Se copia literal
 * en lugar de reproyectarlo: cualquier proyección propia da un trazado
 * parecido pero no idéntico, y acá el objetivo es que coincida con el diseño.
 *
 * El viewBox también es el del concepto; las coordenadas del path y de la
 * línea de meta están en ese sistema.
 */

export interface Track {
  name: string
  location: string
  /** Longitud oficial de la vuelta, en metros. */
  lengthM: number
  /** viewBox del SVG en el que están expresadas las coordenadas. */
  viewBox: string
  /** Path cerrado del trazado. */
  path: string
  /** Línea de meta, perpendicular a la recta principal. */
  startLine: { x1: number; y1: number; x2: number; y2: number }
}

export const ZANDVOORT: Track = {
  name: 'Circuit Zandvoort',
  location: 'Zandvoort',
  lengthM: 4259,
  viewBox: '-40 -40 1080 932',
  startLine: { x1: 106, y1: 386, x2: 139, y2: 393 },
  path:
    "M122.1 389.4L234.2 118.4L276.8 19L286.5 8L299.5 1.8L313.8 0L327 2.7L339.4 11.2L348.1 21.9L352.7 35.1L353 49.9L340.7 78.6L305.1 165.1L293.7 205.4L289.1 247.4L291.5 286.8L287.8 302.8L279.1 313.5L261.6 327.7L242.8 335.2L190.9 355.4L177.6 365.5L174 380.4L173.5 393.7L178.9 407.4L188.9 417.1L201.5 422.2L220.8 421.8L315.8 391.5L359.9 383.2L398 382L431.7 384.5L463.5 389.9L486.2 396.8L523.4 404.7L557.7 407.7L582 402.7L611.2 395L646.4 377.3L687.8 350.3L715.8 337L740.7 329.8L773.6 326.1L799.5 326.7L907.5 333.3L932.5 339.1L955.6 350.6L972 364.7L982.5 379.7L992.8 396.8L998.3 416.6L1000 437.6L998 458.1L992 478.9L979 501.5L929.4 569.3L911.1 599.4L869.6 689L849.7 696L825.1 698.8L801.6 697.7L773.9 693L745.1 683.1L714.3 668.4L683.8 646.6L664.9 625.7L661.5 612.9L664.5 599.4L676.2 582.4L693 571.7L717.6 562.6L759.8 556L800.3 545.8L837.3 531.6L857.8 517.2L865.6 499.9L866.6 481.1L860 462.3L842.9 445.2L827.5 439.9L747.7 430.1L667.3 430.4L581.9 440.7L509.7 458.9L465 472.9L415.7 491.2L368.5 511.3L330.1 534L316 540.1L306 538.2L296.5 525.1L286.5 506.1L272.6 497.5L254.9 496.8L237.6 505L228.4 517.4L224.1 530.8L228.4 558.1L267.1 783.9L267.9 799.1L263.6 814.5L256.8 827.5L250.2 835.9L233.7 847L216.2 851L141.9 852.3L126.8 851.5L104.7 848L81.8 840.6L63.1 832L38.1 812.3L21.8 790.6L10.7 771.9L2.6 746.8L0 724.7L2.3 688.6L9.1 663L116.3 402.9L122.1 389.4Z",
}

export const TRACKS: Record<string, Track> = { zandvoort: ZANDVOORT }
