# DISPATCHER.
**Powered by Asolf &amp; Co.**

DISPATCHER. es una herramienta de despacho de mensajes por WhatsApp Web diseñada para equipos que necesitan enviar comunicaciones a contactos de forma rápida, organizada y con control sobre el contenido. Incluye un editor global de mensaje, carga de contactos desde CSV/XLSX y gestión de enlaces de archivos.

## Funcionalidades
- Editor global de mensaje con formato básico.
- Tabla de contactos con campos: código de país, teléfono y nombre.
- Importación de contactos desde CSV/XLSX.
- Enlaces de archivos múltiples por envío.
- Envío individual o masivo con intervalos aleatorios.
- Banner de estado para errores y confirmaciones.

## Cómo funciona
1. Carga contactos (CSV/XLSX) o ingresa manualmente.
2. Escribe el mensaje global en el editor.
3. Agrega uno o más enlaces de archivo si aplica.
4. Envía a un contacto o usa **Enviar Todo** para una campaña completa.

El envío utiliza **WhatsApp Web** con Selenium, por lo que requiere una sesión autenticada en el navegador del servidor.

## Requisitos
- Python 3.10+
- Google Chrome/Chromium instalado en el servidor.
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
Para enviar mensajes, se debe **vincular la sesión** de WhatsApp Web desde el servidor. Si el servidor no tiene interfaz gráfica, se puede generar un QR desde modo headless y escanearlo desde el móvil.

## Notas importantes
- WhatsApp puede limitar el enlace de nuevos dispositivos. Si ocurre, espera y reintenta.
- El envío masivo respeta intervalos configurables para evitar bloqueos.

---
© 2026 Asolf &amp; Co.
