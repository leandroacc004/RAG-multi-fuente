# Manual de la API de NimbusDocs

## Autenticación

Todas las peticiones a la API requieren un token de acceso en la cabecera `Authorization: Bearer <token>`. Los tokens se crean en Configuración > Integraciones > Tokens de API. Cada token tiene un alcance (lectura, escritura o administración) y vence a los 90 días. Un administrador puede revocar cualquier token en cualquier momento.

La API está disponible solo en los planes Equipo y Empresa. Las cuentas del plan Gratis reciben un error 403 al intentar usarla.

## Límites de uso

El límite es de 100 peticiones por minuto por token en el plan Equipo y de 1.000 peticiones por minuto en el plan Empresa. Si se supera el límite, la API responde con el código 429 y la cabecera `Retry-After`, que indica cuántos segundos esperar antes de reintentar.

Las subidas de archivos tienen un tamaño máximo de 50 MB por archivo en el plan Equipo y de 500 MB en el plan Empresa.

## Documentos

- `GET /v2/documentos` lista los documentos del espacio de trabajo, con paginación de 50 resultados por página.
- `GET /v2/documentos/{id}` devuelve el contenido y los metadatos de un documento.
- `POST /v2/documentos` crea un documento nuevo. El cuerpo debe incluir `titulo` y, opcionalmente, `contenido` en Markdown.
- `DELETE /v2/documentos/{id}` envía el documento a la papelera; se puede restaurar durante 30 días.

## Webhooks

Los webhooks avisan a tu sistema cuando ocurre un evento: documento creado, editado, compartido o eliminado. Se configuran en Configuración > Integraciones > Webhooks. NimbusDocs reintenta la entrega hasta 5 veces con espera exponencial si tu servidor no responde con un código 2xx. Cada envío incluye la cabecera `X-Nimbus-Firma`, una firma HMAC-SHA256 que debes verificar con el secreto del webhook.

## Errores comunes

- 401: el token no es válido o venció.
- 403: el token no tiene el alcance necesario o el plan no incluye la API.
- 404: el documento no existe o no tienes permiso para verlo.
- 429: se superó el límite de peticiones; espera lo que indica `Retry-After`.
