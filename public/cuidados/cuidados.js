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
  // ¿Aún no la tienes?: copia la consulta para pegarla en Instagram
  Array.prototype.forEach.call(d.querySelectorAll('[data-stock]'), function(a){
    a.addEventListener('click', function(){
      var av = a.parentNode.querySelector('[data-stock-aviso]');
      if (!(navigator.clipboard && window.isSecureContext)) return;
      navigator.clipboard.writeText(a.getAttribute('data-stock')).then(function(){
        if (av) av.textContent = 'Copiamos tu consulta: pégala en el chat de Instagram.';
      }, function(){});
    });
  });
  // Buscador del índice
  var q = d.querySelector('[data-buscar]');
  if (q) {
    var items = Array.prototype.slice.call(d.querySelectorAll('[data-q]'));
    var grupos = Array.prototype.slice.call(d.querySelectorAll('[data-grupo]'));
    var vacio = d.querySelector('[data-vacio]');
    var accesos = d.querySelector('[data-accesos]');
    var norm = function(s){ return s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, ''); };
    var filtrar = function(){
      var ps = norm(q.value.trim()).split(/\s+/).filter(Boolean), n = 0;
      items.forEach(function(li){
        var h = li.getAttribute('data-q');
        var ok = ps.every(function(w){ return h.indexOf(w) > -1; });
        li.hidden = !ok; if (ok) n++;
      });
      grupos.forEach(function(g){ g.hidden = !g.querySelector('[data-q]:not([hidden])'); });
      if (vacio) vacio.hidden = n > 0;
      if (accesos) accesos.hidden = ps.length > 0;
    };
    q.addEventListener('input', filtrar);
    filtrar();
  }
})();
