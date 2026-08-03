const navbarScriptUrl = document.currentScript.src;

document.addEventListener('DOMContentLoaded', () => {
  const siteRoot = new URL('../', navbarScriptUrl);

  const links = [
    { label: 'Inicio', path: 'index.html' },
    { label: 'Precios', path: 'inflacion/inflacion.html' },
    {
      label: 'Actividad Económica',
      path: 'actividad_economica/actividad_economica.html'
    },
    { label: 'Análisis UVA', path: 'uva/uva.html' }
  ];

  const nav = document.createElement('nav');
  nav.className = 'navbar';

  const brand = document.createElement('a');
  brand.className = 'brand';
  brand.href = new URL('index.html', siteRoot).href;
  brand.innerHTML = '📈 Macrolytics';

  nav.appendChild(brand);

  const navLinks = document.createElement('div');
  navLinks.className = 'nav-links';

  links.forEach(({ label, path }) => {
    const anchor = document.createElement('a');

    anchor.className = 'nav-link';
    anchor.textContent = label;
    anchor.href = new URL(path, siteRoot).href;

    navLinks.appendChild(anchor);
  });

  nav.appendChild(navLinks);

  const container = document.querySelector('.container');

  if (container?.parentNode) {
    container.parentNode.insertBefore(nav, container);
  } else {
    document.body.prepend(nav);
  }
});