import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { CssBaseline, ThemeProvider } from '@mui/material'
import App from './App.tsx'
import { Viewport } from './Viewport'
import { theme } from './theme'
import './styles.css'

/*
 * El piso de ancho se resuelve acá afuera y no adentro de `App`: abajo de 768
 * px la aplicación entera **no se monta**, así que la simulación no sigue
 * corriendo detrás de un aviso y no queda nada oculto en el árbol de
 * accesibilidad. Va bajo el `ThemeProvider` porque consulta el tema.
 */
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Viewport>
        <App />
      </Viewport>
    </ThemeProvider>
  </StrictMode>,
)
