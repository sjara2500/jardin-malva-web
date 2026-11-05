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
  // Buscador y filtros del índice
  var q = d.querySelector('[data-buscar]');
  if (q) {
    var items = Array.prototype.slice.call(d.querySelectorAll('[data-q]'));
    var grupos = Array.prototype.slice.call(d.querySelectorAll('[data-grupo]'));
    var vacio = d.querySelector('[data-vacio]');
    var accesos = d.querySelector('[data-accesos]');
    var filtros = d.querySelector('[data-filtros]');
    var cuenta = d.querySelector('[data-cuenta]');
    var total = cuenta ? cuenta.getAttribute('data-total') : '';
    var textoCuenta = cuenta ? cuenta.textContent : '';
    var NIVEL = {'1': 'facil', '2': 'medio', '3': 'atencion'};
    var norm = function(s){ return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); };
    var cuidado = function(){ var r = d.querySelector('input[name="cuidado"]:checked'); return r ? r.value : ''; };
    var soloOk = function(){ var c = d.querySelector('input[name="mascotas"]'); return !!(c && c.checked); };
    var filtrar = function(){
      var ps = norm(q.value.trim()).split(/\s+/).filter(Boolean), dif = cuidado(), pet = soloOk(), n = 0;
      items.forEach(function(li){
        var h = li.getAttribute('data-q');
        var ok = ps.every(function(w){ return h.indexOf(w) > -1; })
          && (!dif || li.getAttribute('data-dif') === dif)
          && (!pet || li.getAttribute('data-pet') === 'ok');
        li.hidden = !ok; if (ok) n++;
      });
      grupos.forEach(function(g){
        var vis = g.querySelectorAll('[data-q]:not([hidden])').length;
        g.hidden = !vis;
        var acc = accesos && accesos.querySelector('[data-acceso="' + g.id + '"]');
        if (acc) { acc.hidden = !vis; acc.querySelector('[data-n]').textContent = vis; }
      });
      var activo = ps.length > 0 || dif || pet;
      if (vacio) {
        vacio.hidden = n > 0;
        vacio.querySelector('[data-vacio-busca]').hidden = !ps.length;
        vacio.querySelector('[data-vacio-filtro]').hidden = !!ps.length;
      }
      if (accesos) accesos.hidden = ps.length > 0;
      if (cuenta) cuenta.textContent = activo ? (n === 1 ? 'Mostrando 1 de ' : 'Mostrando ' + n + ' de ') + total + ' fichas.' : textoCuenta;
    };
    var guardar = function(){
      if (!window.history || !history.replaceState) return;
      var u = new URL(location.href), dif = cuidado();
      if (dif) u.searchParams.set('cuidado', NIVEL[dif]); else u.searchParams.delete('cuidado');
      if (soloOk()) u.searchParams.set('mascotas', 'no-toxicas'); else u.searchParams.delete('mascotas');
      history.replaceState(null, '', u.pathname + u.search + u.hash);
    };
    if (filtros) {
      filtros.hidden = false;
      var params = new URLSearchParams(location.search);
      var pedido = params.get('cuidado');
      Object.keys(NIVEL).forEach(function(k){
        if (NIVEL[k] === pedido) { var r = filtros.querySelector('input[name="cuidado"][value="' + k + '"]'); if (r) r.checked = true; }
      });
      if (params.get('mascotas') === 'no-toxicas') { var c = filtros.querySelector('input[name="mascotas"]'); if (c) c.checked = true; }
      filtros.addEventListener('change', function(){ filtrar(); guardar(); });
    }
    q.addEventListener('input', filtrar);
    filtrar();
  }
})();
