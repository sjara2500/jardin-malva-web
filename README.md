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
El cliente la abre escaneando el QR de la tarjeta que se entrega con la planta.
El índice con buscador está en `jardinmalva.cl/cuidados/`.

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
pon la toxicidad solo si está en la ASPCA (con su enlace; si no, quita `mascotas`),
ejecuta los dos scripts y sube los cambios.

Cuando haya WhatsApp o enlace de reseñas de Google, ponlos en `contacto` de
`datos/cuidados.json` y vuelve a generar. Mientras `whatsapp` esté vacío, el botón
lleva a los mensajes de Instagram, y la reseña al perfil de Google Maps.

Las fichas llevan `noindex` mientras `"indexar": false`. Cámbialo a `true` cuando
estén revisadas para que aparezcan en Google.

## Imágenes

Van en `public/assets/`, en `.webp` y en dos o tres anchos cuando se usan con
`srcset`. Solo fotos reales del vivero y sus productos. Los vídeos van en `.mp4`
(H.264), cortos y comprimidos, y solo se descargan cuando se ven en pantalla.

## Diseño

La web sigue el documento "brief-web" del proyecto Malva: paleta verde bosque,
crema y malva; Cormorant Garamond para títulos y DM Sans para texto.
