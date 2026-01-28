# DISPATCHER.
**Powered by Asolf &amp; Co.**

DISPATCHER. es una herramienta de despacho de mensajes por WhatsApp Web diseñada para equipos que necesitan enviar comunicaciones a contactos de forma rápida, organizada y con control sobre el contenido. Incluye un editor global de mensaje, carga de contactos desde CSV/XLSX y gestión de enlaces de archivos.

## Funcionalidades
- Editor global de mensaje con formato básico.
- Tabla de contactos con campos: código de país, teléfono y nombre.
- Importación de contactos desde CSV/XLSX.
- Adjuntos locales (archivos o carpetas) por envío.
- Envío individual o masivo con intervalos aleatorios.
- Banner de estado para errores y confirmaciones.

# DISPATCHER.
**Powered by Asolf &amp; Co.**

DISPATCHER. es una herramienta de despacho de mensajes por WhatsApp Web para equipos que necesitan enviar comunicaciones rápidas y controladas. Incluye editor global de mensaje, carga de contactos desde CSV/XLSX y adjuntos directos desde el navegador.

## Funcionalidades
- Editor global con formato compatible con WhatsApp: **negrita**, _cursiva_, ~tachado~, `monoespaciado`.
- Tabla de contactos con: código de país, teléfono y nombre.
- Importación desde CSV/XLSX.
- Adjuntos locales (archivos o carpetas) para envío individual o masivo.
- Envío individual o masivo con intervalos aleatorios configurables.
- Banner de estado y mensajes localizados (ES/EN).
- Botón para abrir WhatsApp Web y estado de carga visible.

## Cómo funciona
1. Carga contactos (CSV/XLSX) o ingresa manualmente.
2. Escribe el mensaje global en el editor.
3. Adjunta archivos si aplica.
4. Envía a un contacto o usa **Enviar Todo** para una campaña completa.

El envío utiliza **WhatsApp Web** con Selenium, por lo que requiere una sesión autenticada en el navegador del servidor.

## Requisitos
- Python 3.10+
- Google Chrome/Chromium instalado en el servidor (o Chrome for Testing descargado automáticamente si falta).
- Conexión a Internet para cargar WhatsApp Web.

## Inicio rápido
```bash
pip install -r requirements.txt
python app.py
```

# DISPATCHER.
**Powered by Asolf &amp; Co.**

DISPATCHER. es una herramienta de despacho de mensajes por WhatsApp Web para equipos que necesitan enviar comunicaciones rápidas y controladas. Incluye editor global de mensaje, carga de contactos desde CSV/XLSX y envío individual o masivo.

## Funcionalidades
- Editor global con formato compatible con WhatsApp: **negrita**, _cursiva_, ~tachado~, `monoespaciado`.
- Botón **Name** para usar {name} en el mensaje y personalizar cada contacto.
- Tabla de contactos con: código de país, teléfono y nombre.
- Importación desde CSV/XLSX.
- Envío individual o masivo con intervalos aleatorios configurables.
- Barra de estado con progreso y resultados.

## Cómo funciona
1. Carga contactos (CSV/XLSX) o ingresa manualmente.
2. Escribe el mensaje global en el editor.
3. (Opcional) Inserta {name} para personalizar.
4. Envía a un contacto o usa **Enviar Todo** para una campaña completa.

El envío utiliza **WhatsApp Web** con Selenium, por lo que requiere una sesión autenticada en el navegador del servidor.

## Requisitos
- Python 3.10+
- Google Chrome/Chromium instalado en el servidor (o Chrome for Testing descargado automáticamente si falta).
- Conexión a Internet para cargar WhatsApp Web.

## Inicio rápido
```bash
pip install -r requirements.txt
python app.py
```

Abrir en el navegador:
```
http://localhost:5000
```

## Autenticación de WhatsApp Web
Para enviar mensajes, se debe **vincular la sesión** de WhatsApp Web desde el servidor. Si el servidor no tiene interfaz gráfica, usa un entorno con GUI para escanear el QR.

## Configuración (opcional)
- `DISPATCHER_AUTO_OPEN=1` abre la UI al iniciar.
- `DISPATCHER_AUTO_OPEN_SELENIUM=1` abre WhatsApp Web automáticamente.
- `WHATSAPP_HEADLESS=1` fuerza modo headless.
- `WHATSAPP_PROFILE_DIR=/ruta/perfil` para reutilizar sesión.

## Notas importantes
- WhatsApp puede limitar el enlace de nuevos dispositivos. Si ocurre, espera y reintenta.
- El envío masivo respeta intervalos configurables para evitar bloqueos.

---
© 2026 Asolf &amp; Co.
