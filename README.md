# Web Jardín Malva

Web del vivero boutique Jardín Malva (San Pedro de la Paz, Chile).
Dominio: https://jardinmalva.cl

## Cómo funciona

- La carpeta `public/` es la web publicada: todo lo que hay dentro se sirve tal cual.
  Lo que está fuera de `public/` (como este archivo) no se publica.
- Hosting: Cloudflare, conectado a este repositorio.
  Cada cambio que llega a la rama `main` se publica solo en ~1 minuto.
- Ajustes del proyecto en Cloudflare Pages:
  - Framework: ninguno
  - Comando de compilación: vacío
  - Directorio de salida: `public`
- Alternativa: si se conecta como Cloudflare Worker (importar repositorio),
  `wrangler.jsonc` ya indica que se publique `public/` sin compilación.
  Comando de despliegue: `npx wrangler deploy` (el que propone Cloudflare).

## Qué se publica ahora

- `public/index.html` — página de "en construcción". Es lo que ve quien entra a
  jardinmalva.cl. Lleva `noindex` para que Google no la registre.
- `public/sitio.html` — la web completa, para revisarla antes de publicarla.
  Está en jardinmalva.cl/sitio.html y no se enlaza desde ninguna parte.

Para publicar la web de verdad: borrar `public/index.html`, renombrar
`public/sitio.html` como `public/index.html` y subir el cambio a `main`.

## Datos de contacto

En `public/index.html` y en `public/sitio.html`, busca `DATOS DE CONTACTO`
(en la página de espera, "pon aquí el número") y edita solo estas líneas:

```js
whatsapp: "",   // con código de país, sin "+" ni espacios. Ej: "56912345678"
email: "",      // Ej: "contacto@jardinmalva.cl"
horario: "Lunes a sábado · 9:30 a 18:30",
```

Mientras `whatsapp` esté vacío, en la página de espera no aparece el botón de
WhatsApp y en la web completa los botones llevan a Instagram.

## Fichas de cuidado con QR (`/cuidados`)

Cada planta tiene su ficha en `jardinmalva.cl/cuidados/<planta>` (luz, riego por
estación, abono, señales de alerta y toxicidad para mascotas con fuente ASPCA).
El índice con buscador está en `jardinmalva.cl/cuidados/`: desde noviembre de 2026 se usa
**un solo QR, el del índice** (cartel y QR `imprimibles/qr/`), y el cliente busca su planta
por nombre común, científico o variedad. Las tarjetas con un QR por planta siguen
funcionando para las que ya se imprimieron, pero no se hacen para las fichas nuevas.

**Una ficha por especie.** Las variedades no tienen ficha propia: van en `variedades`
(texto que se muestra en la ficha) y en `alias`, para que el buscador las encuentre
(p. ej. buscar "Lapins" lleva a Cerezo). En pantalla, "Otros nombres" solo muestra los alias
que no repiten el nombre botánico ni una variedad ya nombrada.

El índice se ordena por categorías (`categorias` en `datos/cuidados.json`: interior, flores,
aromáticas, arbustos, frutales, árboles, coníferas, nativas y suculentas). Cada planta lleva
`"categoria"`; si no la tiene, va a interior o a flores según su `tipo`.

Cada ficha tiene arriba el botón "¿Aún no la tienes? Consulta el stock por Instagram":
abre los mensajes de Instagram y copia una consulta con el nombre de la planta para pegarla
(Instagram no permite dejar el texto escrito). El icono, un globo de conversación con una
hoja, es `consulta` en `ICONOS` del generador.

- `datos/cuidados.json` — los textos de todas las fichas y los datos de contacto.
- `herramientas/generar_cuidados.py` — crea `public/cuidados/` (solo Python 3).
- `herramientas/generar_tarjetas.py` — crea los PDF y los QR de `imprimibles/`
  (`pip install reportlab segno pillow`).
- `imprimibles/tarjetas-cuidados.pdf` — una hoja A4 por planta con 10 tarjetas de 85 × 55 mm.
  `tarjetas-surtidas.pdf` — una de cada planta. `cartel-cuidados-A5.pdf` — cartel para la caja.
  Imprimir al 100 % (tamaño real), en cartulina, y cortar por las marcas.

**Regla de oro: nunca borrar ni renombrar una ficha.** Hay QR impresos que apuntan a ella.
`datos/slugs-publicados.txt` las registra y el generador se detiene si falta alguna.

Para añadir una planta: copia un bloque en `datos/cuidados.json` con un `slug` nuevo,
pon la toxicidad solo si está en la ASPCA (con su enlace), ejecuta los dos scripts y sube los cambios.
Si la ASPCA no tiene ficha de la planta, usa `"toxica": null` con un texto que lo diga:
la ficha muestra "Sin dato verificado" y la tarjeta "Toxicidad sin verificar".

Lotes del inventario: `datos/lotes/*.json` (`tomo1-interior.json`, las plantas de interior
del Tomo I con su código JM-T1, y los cinco `inventario-*.json` del inventario de noviembre
de 2026: interior, flores-aromáticas-suculentas, arbustos, árboles-frutales-coníferas y nativas).
Los perfiles son comunes a todos los lotes. Cada lote puede definir `perfiles` (cuidados comunes,
p. ej. calatheas o ficus) y plantas con `"base": "<perfil o ficha>"`, que heredan esos cuidados;
lo que pongas en la planta manda sobre lo heredado (`consejos_extra` y `alertas_extra` se suman).
`equivalencias` asigna un código del inventario a una ficha que ya existía. Cada lote genera
`imprimibles/tarjetas-<lote>.pdf`, con una tarjeta por planta en orden de código.

Cuando haya WhatsApp o enlace de reseñas de Google, ponlos en `contacto` de
`datos/cuidados.json` y vuelve a generar. Mientras `whatsapp` esté vacío, el botón
lleva a los mensajes de Instagram, y la reseña al perfil de Google Maps.

### Plantas para casas con mascotas (`/mascotas`)

`public/mascotas.html` (jardinmalva.cl/mascotas) y el bloque "Plantas para casas con
mascotas" de la sección Pet friendly de `public/sitio.html` los genera el mismo script a
partir de las fichas: entran solo las plantas que la ASPCA clasifica como no tóxicas
(`"toxica": false`); las tóxicas y las "sin dato" quedan fuera. Las variedades de una misma
base se agrupan (p. ej. "Calatheas"). En `sitio.html` el bloque va entre las marcas
`PLANTAS-MASCOTAS:INICIO` y `PLANTAS-MASCOTAS:FIN`: no lo edites a mano, se reescribe
cada vez que se ejecuta el script. Si se rediseña `sitio.html`, conserva esas marcas.

Las fichas llevan `noindex` mientras `"indexar": false` (también `/mascotas`). Cámbialo a `true` cuando
estén revisadas para que aparezcan en Google.

### Colores de "Lo esencial"

Los cuadros de luz, riego y temperatura tienen tres intensidades según cuánta luz, agua o
calor necesita la planta (1 poca · 2 media · 3 mucha): paja para la luz, azul grisáceo para
el riego y terracota para la temperatura. El nivel sale del texto corto de la ficha
(tabla `NIVELES` en `generar_cuidados.py`; la temperatura "Entre X y Y °C" va por la
mínima). Si una ficha nueva trae un texto que no está en la tabla, el script se detiene y
lo dice: añádelo a la tabla o pon `"nivel": 1`, `2` o `3` dentro de `luz`, `riego` o
`temperatura`. El cuadro de mascotas va en verde suave si la ASPCA la da como no tóxica,
rojo suave si es tóxica y neutro si no hay dato.

### Logo del herbario

`herramientas/generar_logo_herbario.py` dibuja el logo de la guía (arco de invernadero con
una fronda y la flor malva, más el nombre y "JARDÍN MALVA") y lo guarda en
`public/assets/herbario-*.svg`. Es una submarca: no toca el logo oficial. Si cambia el
nombre de la guía, basta con `python3 herramientas/generar_logo_herbario.py "Otro nombre"`
y cambiar el texto "Herbario" en `sitio.html` (menú, bloque y pie) y en `index.html`.
La web enlaza a la guía desde el bloque "Cuida lo que te llevas" (tras "Lo que
encontrarás"), el menú y el pie; la página de espera, con un botón bajo los demás.

## Imágenes

Van en `public/assets/`, en `.webp` y en dos o tres anchos cuando se usan con
`srcset`. Solo fotos reales del vivero y sus productos. Los vídeos van en `.mp4`
(H.264), cortos y comprimidos, y solo se descargan cuando se ven en pantalla.

## Diseño

La web sigue el documento "brief-web" del proyecto Malva: paleta verde bosque,
crema y malva; Cormorant Garamond para títulos y DM Sans para texto.
