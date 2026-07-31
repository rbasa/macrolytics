document.addEventListener('DOMContentLoaded', () => {

  const links = [
    { label: 'Inicio', href: '/index.html' },
    { label: 'Precios', href: '/inflacion/inflacion.html' },
    { label: 'Actividad Económica', href: '/actividad_economica/actividad_economica.html' },
    { label: 'Análisis UVA', href: '/uva/uva.html' }
  ];

  const nav = document.createElement('nav');
  nav.className = 'navbar';

  const brand = document.createElement('a');
  brand.className = 'brand';
  brand.href = '/index.html';
  brand.innerHTML = '📈 Macro';
  nav.appendChild(brand);

  const navLinks = document.createElement('div');
  navLinks.className = 'nav-links';

  links.map((l) => {
    const a = document.createElement('a');
    a.className = 'nav-link';
    a.textContent = l.label;
    a.href = l.href;
    if (l.disabled) {
      a.style.opacity = '0.6';
      a.style.pointerEvents = 'none';
    }
    navLinks.appendChild(a);
  });

  nav.appendChild(navLinks);

  // Insert the navbar before the first .container element if present,
  // otherwise prepend to body
  const container = document.querySelector('.container');
  if (container && container.parentNode) {
    container.parentNode.insertBefore(nav, container);
  } else {
    document.body.insertBefore(nav, document.body.firstChild);
  }
});
