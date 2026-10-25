# Web Jardín Malva

Web del vivero boutique Jardín Malva (San Pedro de la Paz, Chile).
Dominio: https://jardinmalva.cl

## Cómo funciona

- La carpeta `public/` es la web publicada: todo lo que hay dentro se sirve tal cual.
  Lo que está fuera de `public/` (como este archivo) no se publica.
- Hosting: Cloudflare Pages, conectado a este repositorio.
  Cada cambio que llega a la rama `main` se publica solo en ~1 minuto.
- Ajustes del proyecto en Cloudflare Pages:
  - Framework: ninguno
  - Comando de compilación: vacío
  - Directorio de salida: `public`
- Alternativa: si se conecta como Cloudflare Worker (importar repositorio),
  `wrangler.jsonc` ya indica que se publique `public/` sin compilación.
  Comando de despliegue: `npx wrangler deploy` (el que propone Cloudflare).

## Datos de contacto

En `public/index.html`, busca `DATOS DE CONTACTO` y edita solo estas líneas:

```js
whatsapp: "",   // con código de país, sin "+" ni espacios. Ej: "56912345678"
email: "",      // Ej: "contacto@jardinmalva.cl"
horario: "Lunes a sábado · 9:30 a 18:30",
```

Mientras `whatsapp` esté vacío, los botones de WhatsApp llevan a Instagram.

## Imágenes

Van en `public/assets/`, en formato `.webp` y en tres anchos (480, 640 y 800 px)
cuando la imagen se usa con `srcset`. Solo fotos reales del vivero y sus productos.
