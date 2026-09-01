/**
 * Tema MUI alineado a la paleta del concepto.
 *
 * MUI viene con Material por defecto —esquinas redondeadas, sombras, azul— y
 * este panel es una pantalla de muro de boxes. El tema aplana todo eso: sin
 * radio, sin sombras, tipografía condensada y los mismos tokens que usa el CSS
 * propio, para que los componentes de MUI y los hechos a mano no se noten
 * distintos.
 */

import { createTheme } from '@mui/material/styles'

export const PALETTE = {
  bg0: '#0f0e0d',
  bg1: '#131211',
  bg2: '#171615',
  bg3: '#1c1a19',
  bg4: '#201e1d',
  bg5: '#232120',
  line: '#302c2a',
  lineSoft: '#232120',
  lineStrong: '#3d3936',
  txt0: '#f4f3f2',
  txt1: '#c9c5c2',
  txt2: '#8f8b88',
  txt3: '#6b6764',
  txt4: '#56524f',
  red: '#ec3013',
  green: '#35c46f',
  yellow: '#f5c518',
  blue: '#3671c6',
} as const

export const theme = createTheme({
  palette: {
    mode: 'dark',
    background: { default: PALETTE.bg0, paper: PALETTE.bg1 },
    text: { primary: PALETTE.txt0, secondary: PALETTE.txt2, disabled: PALETTE.txt4 },
    primary: { main: PALETTE.red },
    success: { main: PALETTE.green },
    warning: { main: PALETTE.yellow },
    divider: PALETTE.line,
  },
  typography: {
    fontFamily: "'Archivo', 'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif",
    fontSize: 12,
  },
  shape: { borderRadius: 2 },
  components: {
    // Material apila sombras por todos lados; acá estorban.
    MuiPaper: { defaultProps: { elevation: 0 } },
  },
})
