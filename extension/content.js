// Content script: ayuda a extraer texto de recibos e inyecta botón flotante de 1-clic.

function extraerTextoRecibo() {
  // 1) Si el usuario tiene texto seleccionado, usar eso
  const seleccion = window.getSelection ? window.getSelection().toString().trim() : '';
  if (seleccion && seleccion.length > 20) {
    return seleccion;
  }

  // 2) Buscar si hay un modal abierto o área de impresión
  const modal = document.querySelector('.modal.show, [role="dialog"]:not([aria-hidden="true"]), .receipt-dialog, .swal2-modal, [class*="modal" i][style*="block"], print-preview-app');
  if (modal && modal.innerText && modal.innerText.length > 50) {
    return modal.innerText.trim();
  }

  // 3) Buscar contenedores que contengan TANTO remitente COMO monto/transacción
  const contenedores = document.querySelectorAll(
    '[class*="receipt" i], [class*="recibo" i], [class*="ticket" i], ' +
    '[id*="receipt" i], [id*="recibo" i], [id*="ticket" i], ' +
    'main, article, .content, .container, body'
  );

  let mejorTexto = '';
  for (const el of contenedores) {
    const t = el.innerText || '';
    const tieneRemitente = /mittente|sender|ordinante|cliente|customer|nominativo|nome/i.test(t);
    const tieneMonto = /importo|totale|amount|total|mtcn|pin|riferimento/i.test(t);
    if (tieneRemitente && tieneMonto) {
      if (!mejorTexto || t.length < mejorTexto.length) {
        mejorTexto = t;
      }
    }
  }

  if (mejorTexto && mejorTexto.length > 80) {
    return mejorTexto.trim();
  }

  // 4) Si no hay un contenedor único que tenga ambos, tomar todo el texto de la pantalla
  return (document.body ? document.body.innerText : '') || '';
}

// Inyectar botón flotante de 1-clic en la página
function inyectarBotonFlotante() {
  if (document.getElementById('sct-floating-container')) return;
  if (!document.body) return;

  const container = document.createElement('div');
  container.id = 'sct-floating-container';
  container.style.cssText = `
    position: fixed !important;
    bottom: 24px !important;
    right: 24px !important;
    z-index: 2147483647 !important;
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    user-select: none !important;
  `;

  const btn = document.createElement('button');
  btn.id = 'sct-floating-btn';
  btn.innerHTML = '⚡ <span>Registrar en Sistema</span>';
  btn.title = 'Capturar recibo y abrir Registro Rápido (o presiona Alt + R)';
  btn.style.cssText = `
    display: inline-flex !important;
    align-items: center !important;
    gap: 8px !important;
    padding: 10px 18px !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    color: #111 !important;
    background: linear-gradient(135deg, #ff8c00, #ffb700) !important;
    border: none !important;
    border-radius: 50px !important;
    box-shadow: 0 4px 15px rgba(0,0,0,0.25), 0 1px 3px rgba(0,0,0,0.15) !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
    outline: none !important;
  `;

  btn.addEventListener('mouseenter', () => {
    btn.style.transform = 'translateY(-2px)';
    btn.style.boxShadow = '0 6px 20px rgba(255, 140, 0, 0.45)';
  });
  btn.addEventListener('mouseleave', () => {
    btn.style.transform = 'none';
    btn.style.boxShadow = '0 4px 15px rgba(0,0,0,0.25)';
  });

  const btnClose = document.createElement('button');
  btnClose.innerHTML = '&times;';
  btnClose.title = 'Ocultar botón';
  btnClose.style.cssText = `
    width: 24px !important;
    height: 24px !important;
    background: rgba(0, 0, 0, 0.6) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 50% !important;
    font-size: 14px !important;
    line-height: 22px !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    opacity: 0.6 !important;
    transition: opacity 0.2s ease !important;
    padding: 0 !important;
  `;
  btnClose.addEventListener('mouseenter', () => { btnClose.style.opacity = '1'; });
  btnClose.addEventListener('mouseleave', () => { btnClose.style.opacity = '0.6'; });
  btnClose.addEventListener('click', () => {
    container.remove();
  });

  btn.addEventListener('click', async () => {
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ <span>Analizando...</span>';
    btn.disabled = true;
    btn.style.opacity = '0.8';

    const texto = extraerTextoRecibo();
    chrome.runtime.sendMessage({ action: 'procesarRecibo', texto }, (resp) => {
      if (chrome.runtime.lastError || !resp || !resp.ok) {
        const errorMsg = resp?.error || chrome.runtime.lastError?.message || 'Error al conectar';
        btn.innerHTML = '⚠️ <span>' + errorMsg + '</span>';
        btn.style.background = '#dc3545';
        btn.style.color = '#fff';
        setTimeout(() => {
          btn.innerHTML = originalText;
          btn.style.background = 'linear-gradient(135deg, #ff8c00, #ffb700)';
          btn.style.color = '#111';
          btn.disabled = false;
          btn.style.opacity = '1';
        }, 4000);
      } else {
        btn.innerHTML = '✅ <span>¡Abriendo pestaña!</span>';
        btn.style.background = '#198754';
        btn.style.color = '#fff';
        setTimeout(() => {
          btn.innerHTML = originalText;
          btn.style.background = 'linear-gradient(135deg, #ff8c00, #ffb700)';
          btn.style.color = '#111';
          btn.disabled = false;
          btn.style.opacity = '1';
        }, 3000);
      }
    });
  });

  container.appendChild(btn);
  container.appendChild(btnClose);
  document.body.appendChild(container);
}

// Escuchar mensajes del popup o background
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extraerRecibo') {
    const texto = extraerTextoRecibo();
    sendResponse({ texto });
  }
  return true; // async
});

// Auto-detectar si parece recibo y activar badge + botón flotante
function verificarReciboEnPagina() {
  const texto = document.body ? (document.body.innerText || '') : '';
  const pareceRecibo = /Mittente|Importo|Totale|MTCN|Reference|Amount|Sender|Ordinante|Beneficiario/i.test(texto);
  if (pareceRecibo) {
    chrome.runtime.sendMessage({ action: 'reciboDetectado' }).catch(() => {});
    inyectarBotonFlotante();
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', verificarReciboEnPagina);
} else {
  verificarReciboEnPagina();
}

// En aplicaciones de una sola página (SPA) o DOM dinámico, observar cambios breves
let debounceTimer = null;
const observer = new MutationObserver(() => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    verificarReciboEnPagina();
  }, 1200);
});
if (document.body) {
  observer.observe(document.body, { childList: true, subtree: true });
}
