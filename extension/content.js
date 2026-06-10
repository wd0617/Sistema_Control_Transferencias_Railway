// Content script: ayuda a extraer texto de recibos en cualquier pestaña, incluidos popups.

function extraerTextoRecibo() {
  // 1) Si el usuario tiene texto seleccionado, usar eso (muy útil en popups)
  const seleccion = window.getSelection ? window.getSelection().toString().trim() : '';
  if (seleccion && seleccion.length > 20) {
    return seleccion;
  }

  // 2) Intentar encontrar el contenedor del recibo
  const posibles = document.querySelectorAll(
    '[class*="receipt" i], [class*="recibo" i], [class*="ticket" i], ' +
    '[id*="receipt" i], [id*="recibo" i], ' +
    'table, .container, .content, main, article, [role="dialog"]'
  );

  let mejor = document.body;
  for (const el of posibles) {
    const texto = el.innerText || '';
    if (/Mittente|Importo|Totale|MTCN|Reference|Amount|Sender|Ordinante|Beneficiario/i.test(texto)) {
      if (texto.length < 8000) {
        mejor = el;
        break; // el primero pequeño que tenga keywords
      }
    }
  }

  // 3) Si body entero es muy corto (popups suelen ser < 3000 chars), devolver todo
  const texto = mejor.innerText || '';
  return texto;
}

// Escuchar mensajes del popup o background
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extraerRecibo') {
    const texto = extraerTextoRecibo();
    sendResponse({ texto });
  }
  return true; // async
});

// Auto-detectar si parece recibo y notificar (opcional, para futuro badge)
const pareceRecibo = /Mittente|Importo|Totale|MTCN|Reference|Amount|Sender|Ordinante|Beneficiario/i.test(document.body.innerText || '');
if (pareceRecibo) {
  chrome.runtime.sendMessage({ action: 'reciboDetectado' }).catch(() => {});
}
