// Script principal para el Sistema de Control de Transferencias

document.addEventListener('DOMContentLoaded', function() {
    // Inicializar tooltips de Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Inicializar popovers de Bootstrap
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto ocultar alertas después de 5 segundos
    setTimeout(function() {
        $('.alert').alert('close');
    }, 5000);
    
    // Función para la calculadora de comisiones
    const calculadoraComisiones = () => {
        const montoInput = document.getElementById('monto-transferencia');
        const servicioSelect = document.getElementById('servicio-select');
        const resultadoElement = document.getElementById('resultado-comision');
        
        if (montoInput && servicioSelect && resultadoElement) {
            const calcular = () => {
                const monto = parseFloat(montoInput.value) || 0;
                const comision = parseFloat(servicioSelect.options[servicioSelect.selectedIndex].dataset.comision) || 0;
                
                const montoComision = monto * (comision / 100);
                const montoTotal = monto + montoComision;
                
                resultadoElement.innerHTML = `
                    <div class="alert alert-info">
                        <p><strong>Monto de transferencia:</strong> ${monto.toFixed(2)}€</p>
                        <p><strong>Comisión (${comision}%):</strong> ${montoComision.toFixed(2)}€</p>
                        <p><strong>Total a cobrar:</strong> ${montoTotal.toFixed(2)}€</p>
                    </div>
                `;
            };
            
            montoInput.addEventListener('input', calcular);
            servicioSelect.addEventListener('change', calcular);
        }
    };
    
    // Inicializar calculadora si estamos en la página correspondiente
    calculadoraComisiones();
    
    // Validación de formulario de cliente
    const formCliente = document.getElementById('form-cliente');
    if (formCliente) {
        formCliente.addEventListener('submit', function(event) {
            const fotoDocumento = document.getElementById('foto-documento');
            if (fotoDocumento && fotoDocumento.files.length > 0) {
                const fileSize = fotoDocumento.files[0].size / 1024 / 1024; // en MB
                if (fileSize > 5) {
                    event.preventDefault();
                    alert('La imagen del documento es demasiado grande. El tamaño máximo es 5MB.');
                }
            }
        });
    }
    
    // Confirmación para eliminar
    const botonesEliminar = document.querySelectorAll('.btn-eliminar');
    botonesEliminar.forEach(boton => {
        boton.addEventListener('click', function(event) {
            if (!confirm('¿Estás seguro de que deseas eliminar este elemento? Esta acción no se puede deshacer.')) {
                event.preventDefault();
            }
        });
    });
    
    // Verificación de límite en tiempo real para nueva transacción
    const clienteSelect = document.getElementById('cliente-select');
    const montoTransferencia = document.getElementById('monto-transferencia');
    const saldoInfo = document.getElementById('saldo-disponible-info');
    
    if (clienteSelect && montoTransferencia && saldoInfo) {
        clienteSelect.addEventListener('change', function() {
            const clienteId = this.value;
            if (clienteId) {
                fetch(`/api/cliente/${clienteId}/saldo`)
                    .then(response => response.json())
                    .then(data => {
                        saldoInfo.innerHTML = `
                            <div class="alert ${data.saldo < 100 ? 'alert-danger' : data.saldo < 300 ? 'alert-warning' : 'alert-success'}">
                                <strong>Saldo disponible:</strong> ${data.saldo}€
                                <br>
                                <strong>Días para reestablecimiento:</strong> ${data.dias_reestablecimiento}
                            </div>
                        `;
                        
                        montoTransferencia.setAttribute('max', data.saldo);
                    })
                    .catch(error => {
                        console.error('Error al obtener el saldo:', error);
                        saldoInfo.innerHTML = '<div class="alert alert-danger">Error al obtener información del saldo.</div>';
                    });
            } else {
                saldoInfo.innerHTML = '';
            }
        });
        
        montoTransferencia.addEventListener('input', function() {
            const monto = parseFloat(this.value) || 0;
            const saldoMax = parseFloat(this.getAttribute('max')) || 0;
            
            if (monto > saldoMax) {
                this.setCustomValidity(`El monto excede el saldo disponible (${saldoMax}€)`);
            } else {
                this.setCustomValidity('');
            }
        });
    }
});
