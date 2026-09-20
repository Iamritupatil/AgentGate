import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import ControlRoom from './ControlRoom'
import Landing from './Landing'
import './theme.css'
import './landing.css'
import './styles.css'

/** Hash routing: the site is static, so `#/control` works on any host without
 *  server rewrites. `/` is the product site; `#/control` is the live demo. */
function Router() {
  const [route, setRoute] = useState(() => window.location.hash)

  useEffect(() => {
    const onHash = () => {
      setRoute(window.location.hash)
      // A hash change is a page change here, not a jump to an anchor.
      if (window.location.hash.startsWith('#/')) window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return route.startsWith('#/control') ? <ControlRoom /> : <Landing />
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Router />
  </StrictMode>,
)
