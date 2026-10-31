(function(){
  var d = document;
  // Compartir la ficha (o copiar el enlace si el teléfono no puede compartir)
  var aviso = d.querySelector('[data-aviso]');
  Array.prototype.forEach.call(d.querySelectorAll('[data-compartir]'), function(b){
    var datos = {title: d.title, url: location.origin + location.pathname};
    if (!navigator.share && !(navigator.clipboard && window.isSecureContext)) return;
    b.hidden = false;
    b.addEventListener('click', function(){
      if (navigator.share) { navigator.share(datos).catch(function(){}); return; }
      navigator.clipboard.writeText(datos.url).then(function(){
        if (aviso) aviso.textContent = 'Enlace copiado. Pégalo donde quieras.';
      }, function(){});
    });
  });
  // Buscador del índice
  var q = d.querySelector('[data-buscar]');
  if (q) {
    var items = Array.prototype.slice.call(d.querySelectorAll('[data-q]'));
    var grupos = Array.prototype.slice.call(d.querySelectorAll('[data-grupo]'));
    var vacio = d.querySelector('[data-vacio]');
    var norm = function(s){ return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); };
    var filtrar = function(){
      var t = norm(q.value.trim()), n = 0;
      items.forEach(function(li){ var ok = !t || li.getAttribute('data-q').indexOf(t) > -1; li.hidden = !ok; if (ok) n++; });
      grupos.forEach(function(g){ g.hidden = !g.querySelector('[data-q]:not([hidden])'); });
      if (vacio) vacio.hidden = n > 0;
    };
    q.addEventListener('input', filtrar);
    filtrar();
  }
})();
