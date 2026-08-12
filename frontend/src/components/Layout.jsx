import { Outlet } from 'react-router-dom'

import Navbar from './Navbar.jsx'
import Footer from './Footer.jsx'

function Layout() {
  return (
    <>
      <Navbar />

      <div className="container">
        <Outlet />
      </div>
      <Footer />
    </>
  )
}

export default Layout