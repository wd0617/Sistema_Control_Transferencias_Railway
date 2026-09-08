// URL por defecto del sistema. Cada negocio puede cambiarla desde el popup
// (queda guardada en chrome.storage.sync y se sincroniza entre sus navegadores).
const DEFAULT_BASE_URL = 'https://sistemacontroltransferenciasrailway-production.up.railway.app';
let BASE_URL = DEFAULT_BASE_URL;
let NEGOCIO_ID = '';

// Helpers para timeouts
function withTimeout(promise, ms, reason) {
  return Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error(reason || 'Timeout')), ms)
    )
  ]);
}

// Normaliza la URL ingresada: sin espacios, sin barra final, con protocolo
function normalizarBaseUrl(url) {
  let u = (url || '').trim().replace(/\/+$/, '');
  if (u && !/^https?:\/\//i.test(u)) u = 'https://' + u;
  return u;
}

document.addEventListener('DOMContentLoaded', async () => {
  // Pestañas
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      tabPanes.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const target = document.getElementById(btn.dataset.tab);
      if (target) target.classList.add('active');
    });
  });

  // Elementos Barra de Negocio
  const negocioBar = document.getElementById('negocioBar');
  const negocioNombre = document.getElementById('negocioNombre');
  const negocioIdBadge = document.getElementById('negocioIdBadge');
  const negocioDot = document.getElementById('negocioDot');
  const usuarioNombre = document.getElementById('usuarioNombre');

  // Elementos Tab Recibo
  const btnAuto = document.getElementById('btnEnviar');
  const btnManual = document.getElementById('btnEnviarManual');
  const btnToggle = document.getElementById('btnToggleManual');
  const manualBox = document.getElementById('manualBox');
  const manualText = document.getElementById('manualText');
  const status = document.getElementById('status');
  const siteLabel = document.getElementById('site');

  // Elementos Tab Cliente
  const inputBuscar = document.getElementById('inputBuscarCliente');
  const listaClientes = document.getElementById('listaClientes');
  const statusCliente = document.getElementById('statusCliente');

  // Elementos Config
  const btnToggleConfig = document.getElementById('btnToggleConfig');
  const configBox = document.getElementById('configBox');
  const configUrl = document.getElementById('configUrl');
  const configNegocioId = document.getElementById('configNegocioId');
  const btnGuardarConfig = document.getElementById('btnGuardarConfig');
  const configMsg = document.getElementById('configMsg');

  // Cargar configuración guardada
  try {
    const stored = await chrome.storage.sync.get(['baseUrl', 'negocioId']);
    if (stored.baseUrl) BASE_URL = stored.baseUrl;
    if (stored.negocioId) NEGOCIO_ID = stored.negocioId;
  } catch {}

  configUrl.value = BASE_URL;
  configNegocioId.value = NEGOCIO_ID;

  // Verificar conexión con el negocio
  async function verificarConexionNegocio() {
    negocioDot.className = 'dot';
    negocioNombre.textContent = 'Verificando...';
    negocioIdBadge.style.display = 'none';

    try {
      const urlInfo = `${BASE_URL}/transacciones/api/negocio-info${NEGOCIO_ID ? `?negocio_id=${encodeURIComponent(NEGOCIO_ID)}` : ''}`;
      const resp = await withTimeout(fetch(urlInfo, { credentials: 'include' }), 6000, 'Timeout');
      
      if (resp.status === 401 || resp.status === 403) {
        negocioDot.className = 'dot warn';
        negocioNombre.textContent = '⚠️ Sin sesión iniciada';
        negocioIdBadge.style.display = 'inline-block';
        negocioIdBadge.textContent = 'Abrir login';
        negocioBar.style.cursor = 'pointer';
        negocioBar.onclick = () => chrome.tabs.create({ url: `${BASE_URL}/login` });
        return false;
      }

      if (resp.ok) {
        const data = await resp.json();
        if (data.ok && data.negocio) {
          negocioDot.className = 'dot online';
          negocioNombre.textContent = data.negocio.nombre;
          negocioIdBadge.style.display = 'inline-block';
          negocioIdBadge.textContent = `ID: #${data.negocio.id}`;
          usuarioNombre.textContent = `👤 ${data.usuario || ''}`;
          negocioBar.style.cursor = 'pointer';
          negocioBar.onclick = () => chrome.tabs.create({ url: `${BASE_URL}/` });
          return true;
        }
      }
      throw new Error('Respuesta inválida');
    } catch (e) {
      negocioDot.className = 'dot offline';
      negocioNombre.textContent = '❌ Sin conexión con el sistema';
      negocioIdBadge.style.display = 'none';
      return false;
    }
  }

  verificarConexionNegocio();

  // Toggle caja de configuración
  btnToggleConfig.addEventListener('click', () => {
    configBox.classList.toggle('visible');
    if (configBox.classList.contains('visible')) {
      configUrl.focus();
    }
  });

  // Guardar URL e ID del negocio
  btnGuardarConfig.addEventListener('click', async () => {
    const url = normalizarBaseUrl(configUrl.value);
    const nid = configNegocioId.value.trim();
    if (!url) {
      configMsg.textContent = '❌ Ingresá una URL válida.';
      configMsg.className = 'config-msg error';
      return;
    }

    btnGuardarConfig.disabled = true;
    configMsg.textContent = 'Conectando con el negocio...';
    configMsg.className = 'config-msg';

    BASE_URL = url;
    NEGOCIO_ID = nid;
    await chrome.storage.sync.set({ baseUrl: url, negocioId: nid });

    const ok = await verificarConexionNegocio();
    btnGuardarConfig.disabled = false;

    if (ok) {
      configMsg.textContent = '✅ Conectado y guardado con éxito.';
      configMsg.className = 'config-msg success';
    } else {
      configMsg.textContent = '⚠️ Configuración guardada. Asegurate de tener iniciada la sesión en el sistema.';
      configMsg.className = 'config-msg error';
    }
  });

  // Detectar sitio actual
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab && tab.url) {
      const host = new URL(tab.url).hostname;
      siteLabel.textContent = host;
    } else {
      siteLabel.textContent = 'ventana emergente / app';
    }
  } catch {
    siteLabel.textContent = 'desconocido';
  }

  // Toggle modo manual
  btnToggle.addEventListener('click', () => {
    manualBox.classList.toggle('visible');
    if (manualBox.classList.contains('visible')) {
      manualText.focus();
    }
  });

  // Envío automático
  btnAuto.addEventListener('click', async () => {
    await enviarRecibo({ modo: 'auto', btn: btnAuto, status });
  });

  // Envío manual
  btnManual.addEventListener('click', async () => {
    const texto = manualText.value.trim();
    if (!texto) {
      status.textContent = '❌ El campo está vacío. Pegá el texto del recibo.';
      status.className = 'error';
      return;
    }
    await enviarRecibo({ modo: 'manual', texto, btn: btnManual, status });
  });

  // Búsqueda de cliente con debounce
  let searchTimer = null;
  inputBuscar.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const q = inputBuscar.value.trim();
    if (q.length < 2) {
      listaClientes.innerHTML = '<div style="text-align: center; color: var(--text-muted); font-size: 12px; padding: 20px 0;">Escribe al menos 2 caracteres...</div>';
      statusCliente.textContent = '';
      return;
    }
    statusCliente.textContent = 'Buscando...';
    searchTimer = setTimeout(() => buscarClientes(q, listaClientes, statusCliente), 350);
  });
});

// Buscar y renderizar clientes
async function buscarClientes(query, container, statusLabel) {
  try {
    const params = new URLSearchParams();
    params.set('q', query);
    if (NEGOCIO_ID) params.set('negocio_id', NEGOCIO_ID);

    const resp = await fetch(`${BASE_URL}/transacciones/api/verificar-cliente?${params.toString()}`, {
      credentials: 'include'
    });
    if (!resp.ok) {
      if (resp.status === 401 || resp.status === 403) {
        statusLabel.textContent = '⚠️ Iniciá sesión en el sistema para consultar.';
        container.innerHTML = '<div style="text-align:center; padding:15px; color:#b91c1c; font-size:12px;">Debes estar autenticado en el sistema.</div>';
        return;
      }
      throw new Error(`Error ${resp.status}`);
    }

    const data = await resp.json();
    const clientes = data.clientes || [];
    statusLabel.textContent = clientes.length ? `${clientes.length} resultado(s)` : 'Sin resultados';

    if (clientes.length === 0) {
      container.innerHTML = '<div style="text-align: center; color: var(--text-muted); font-size: 12px; padding: 20px 0;">No se encontró ningún cliente registrado.</div>';
      return;
    }

    let html = '';
    clientes.forEach(c => {
      const saldoOk = c.saldo_disponible > 0;
      const saldoCls = saldoOk ? 'badge-ok' : 'badge-limit';
      const docCls = `doc-${c.estado_documento || 'vigente'}`;
      const docLabel = (c.estado_documento || 'vigente').replace('_', ' ').toUpperCase();

      let docsExtrasHtml = '';
      if (c.documentos_adicionales && c.documentos_adicionales.length > 0) {
        docsExtrasHtml = `<div style="font-size: 10px; color: #4b5563; margin-top: 3px;">
          📎 Otros doc: ${c.documentos_adicionales.map(d => `${d.tipo} ${d.numero}`).join(', ')}
        </div>`;
      }

      // Parámetros para Registro Rápido
      const p = new URLSearchParams();
      p.set('doc', c.documento);
      p.set('nom', c.nombre);
      if (c.apellido) p.set('ape', c.apellido);
      if (c.telefono) p.set('tel', c.telefono);
      if (NEGOCIO_ID) p.set('negocio_id', NEGOCIO_ID);
      const urlRapido = `${BASE_URL}/transacciones/registro-rapido?${p.toString()}`;

      html += `
        <div class="client-card">
          <div class="client-header">
            <span class="client-name">${escapeHtml(c.nombre)} ${escapeHtml(c.apellido || '')}</span>
            <span class="balance-badge ${saldoCls}">
              ${c.saldo_disponible.toFixed(2)} € disp.
            </span>
          </div>
          <div class="client-sub">
            <span>🪪 ${escapeHtml(c.tipo_documento)}: <strong>${escapeHtml(c.documento)}</strong></span>
            <span class="badge-doc ${docCls}">${docLabel}</span>
          </div>
          ${docsExtrasHtml}
          ${!saldoOk ? `<div style="font-size:11px; color:#b91c1c; margin-top:2px;">⚠️ Límite de ${c.limite_semanal}€ alcanzado. Reestablece en ${c.dias_reestablecimiento} día(s).</div>` : ''}
          <a href="${urlRapido}" target="_blank" class="btn-send-fast">⚡ Iniciar Registro Rápido</a>
        </div>
      `;
    });

    container.innerHTML = html;

  } catch (err) {
    statusLabel.textContent = '❌ Error al consultar';
    container.innerHTML = `<div style="color:#b91c1c; font-size:11px; padding:10px;">${err.message}</div>`;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[m]);
}

async function enviarRecibo({ modo, texto: textoManual, btn, status }) {
  btn.disabled = true;
  status.textContent = modo === 'auto' ? 'Leyendo recibo...' : 'Analizando...';
  status.className = '';

  try {
    let texto = textoManual || '';

    if (modo === 'auto') {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab) throw new Error('No se encontró la pestaña activa');

      const url = tab.url || '';

      if (url.startsWith('about:') || url.startsWith('chrome://') || url.startsWith('chrome-extension://') || url.startsWith('edge://')) {
        throw new Error('No se puede leer esta pestaña del navegador. Probá seleccionando el texto del recibo y usando "Pegar recibo manualmente".');
      }

      let textoContent = '';
      let textoInyectado = '';

      // Intento 1: preguntar al content script
      try {
        const resp = await withTimeout(
          new Promise((resolve, reject) => {
            chrome.tabs.sendMessage(tab.id, { action: 'extraerRecibo' }, (response) => {
              if (chrome.runtime.lastError) {
                reject(new Error(chrome.runtime.lastError.message));
              } else {
                resolve(response);
              }
            });
          }),
          4000,
          'El content script no respondió'
        );
        if (resp && resp.texto) textoContent = resp.texto;
      } catch (e) {}

      // Intento 2: inyección directa
      if (!textoContent) {
        try {
          const results = await withTimeout(
            chrome.scripting.executeScript({
              target: { tabId: tab.id },
              func: () => {
                const seleccion = window.getSelection ? window.getSelection().toString().trim() : '';
                if (seleccion && seleccion.length > 20) return seleccion;

                const modal = document.querySelector('.modal.show, [role="dialog"]:not([aria-hidden="true"]), .receipt-dialog, .swal2-modal, [class*="modal" i][style*="block"], print-preview-app');
                if (modal && modal.innerText && modal.innerText.length > 50) {
                  return modal.innerText.trim();
                }

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

                return (document.body ? document.body.innerText : '') || '';
              }
            }),
            5000,
            'La pestaña no respondió a tiempo'
          );
          textoInyectado = results[0]?.result || '';
        } catch (e) {}
      }

      texto = textoContent || textoInyectado;
      if (!texto.trim()) {
        throw new Error('No se pudo leer texto del recibo. Probá seleccionando el texto en la página, copiándolo y usando "Pegar recibo manualmente".');
      }
    }

    status.textContent = 'Analizando en el sistema...';

    const apiUrl = `${BASE_URL}/transacciones/api/analizar-recibo${NEGOCIO_ID ? `?negocio_id=${encodeURIComponent(NEGOCIO_ID)}` : ''}`;
    const resp = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(NEGOCIO_ID ? { 'X-Negocio-Id': NEGOCIO_ID } : {})
      },
      credentials: 'include',
      body: JSON.stringify({ texto })
    });

    if (!resp.ok) {
      if (resp.status === 404) throw new Error('Error 404: La URL del servidor no existe. Verificá que el sistema esté en línea.');
      if (resp.status === 401 || resp.status === 403) throw new Error('Error de autenticación: No has iniciado sesión en el sistema. Abrí el sistema en otra pestaña e iniciá sesión.');
      if (resp.status === 400) throw new Error('El servidor rechazó el formato del recibo o falta sesión activa.');
      throw new Error('Error del servidor: ' + resp.status);
    }

    const datos = await resp.json();

    // Construir URL con query params
    const params = new URLSearchParams();
    if (datos.documento) params.set('doc', datos.documento);
    if (datos.nombre) params.set('nom', datos.nombre);
    if (datos.apellido) params.set('ape', datos.apellido);
    if (datos.telefono) params.set('tel', datos.telefono);
    if (datos.monto) params.set('mon', String(datos.monto).replace('.', ','));
    if (datos.servicio_hint) params.set('srv', datos.servicio_hint);
    if (datos.referencia) params.set('ref', datos.referencia);
    if (NEGOCIO_ID) params.set('negocio_id', NEGOCIO_ID);

    const url = BASE_URL + '/transacciones/registro-rapido?' + params.toString();

    status.textContent = '✅ Abriendo sistema...';
    status.className = 'success';

    await chrome.tabs.create({ url });
    window.close();

  } catch (err) {
    status.textContent = '❌ ' + err.message;
    status.className = 'error';
    btn.disabled = false;
  }
}
