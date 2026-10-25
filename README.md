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

## Imágenes

Van en `public/assets/`, en `.webp` y en dos o tres anchos cuando se usan con
`srcset`. Solo fotos reales del vivero y sus productos. Los vídeos van en `.mp4`
(H.264), cortos y comprimidos, y solo se descargan cuando se ven en pantalla.

## Diseño

La web sigue el documento "brief-web" del proyecto Malva: paleta verde bosque,
crema y malva; Cormorant Garamond para títulos y DM Sans para texto.
