// Funciones compartidas (index, cliente, surtir, historial).

function cerrarSesion() {
    fetch("/api/logout", { method: "POST" })
        .catch(() => {})
        .finally(() => { window.location.href = "/login"; });
}

// Llena la tabla #Inventario con los datos de MySQL.
// Columnas: ID Inventario | Componente | Categoría | Cantidad | Ubicación | Precio.
function fillTable() {
    return fetch("/inventario")
        .then(response => {
            if (!response.ok) {
                throw new Error("Error al consultar la API");
            }
            return response.json();
        })
        .then(data => {
            const tbody = document.querySelector("#Inventario tbody");
            if (!tbody) return;

            tbody.innerHTML = "";

            data.forEach(componente => {
                const fila = document.createElement("tr");
                if (componente.bajo_stock) {
                    fila.classList.add("bajo-stock");
                }

                const cantidad = componente.bajo_stock
                    ? `${componente.cantidad} (bajo stock)`
                    : `${componente.cantidad}`;

                fila.innerHTML = `
                    <td>${componente.id_inventario ?? "—"}</td>
                    <td>${componente.nombre}</td>
                    <td>${componente.categoria ?? ""}</td>
                    <td>${cantidad}</td>
                    <td>${componente.ubicacion ?? "—"}</td>
                    <td>${componente.precio ?? "0.00"}</td>
                `;

                tbody.appendChild(fila);
            });

            const estado = document.getElementById("estado-inventario");
            if (estado) {
                estado.textContent = `${data.length} componentes en el catálogo`;
            }
        })
        .catch(error => {
            console.error("Error:", error);
            const estado = document.getElementById("estado-inventario");
            if (estado) {
                estado.textContent = "No se pudo cargar el inventario.";
            }
        });
}

function cargarPeticiones() {
    fetch("/api/peticiones")
        .then(response => {
            if (!response.ok) {
                throw new Error("Error al consultar las peticiones");
            }
            return response.json();
        })
        .then(data => {
            const contenedor = document.getElementById("lista-peticiones");
            if (!contenedor) return;

            contenedor.innerHTML = "";

            if (data.length === 0) {
                contenedor.textContent = "No hay peticiones registradas.";
                return;
            }

            data.forEach(peticion => {
                const tarjeta = document.createElement("section");

                const titulo = document.createElement("h3");
                titulo.textContent = `Pedido #${peticion.id_pedido}`;

                const empleado = document.createElement("p");
                empleado.textContent = `Empleado: ${peticion.empleado}`;

                const fecha = document.createElement("p");
                fecha.textContent = `Fecha: ${peticion.fecha_hora}`;

                const estado = document.createElement("p");
                estado.textContent = `Estado: ${peticion.estado}`;

                const lista = document.createElement("ul");

                peticion.componentes.forEach(componente => {
                    const elemento = document.createElement("li");
                    elemento.textContent =
                        `${componente.nombre} - Cantidad: ${componente.cantidad}`;
                    lista.appendChild(elemento);
                });

                const comentarios = document.createElement("p");
                comentarios.textContent =
                    `Comentarios: ${peticion.comentarios || "Ninguno"}`;

                const botonCancelar = document.createElement("button");
                botonCancelar.type = "button";
                botonCancelar.textContent = "Cancelar pedido";
                botonCancelar.addEventListener("click", async () => {
                    if (!confirm(`¿Cancelar el pedido #${peticion.id_pedido}?`)) return;
                    const respuesta = await fetch(
                        `/api/pedidos/${peticion.id_pedido}/cancelar`,
                        { method: "POST" }
                    );
                    if (!respuesta.ok) {
                        const detalle = await respuesta.json().catch(() => ({}));
                        alert(detalle.error || "No se pudo cancelar el pedido.");
                        return;
                    }
                    cargarPeticiones();
                });

                tarjeta.appendChild(titulo);
                tarjeta.appendChild(empleado);
                tarjeta.appendChild(fecha);
                tarjeta.appendChild(estado);
                tarjeta.appendChild(lista);
                tarjeta.appendChild(comentarios);
                tarjeta.appendChild(botonCancelar);

                contenedor.appendChild(tarjeta);
            });
        })
        .catch(error => {
            console.error("Error al cargar peticiones:", error);
        });
}

function cargarHistorial() {
    fetch("/api/historial")
        .then(response => {
            if (!response.ok) {
                throw new Error("Error al consultar el historial");
            }
            return response.json();
        })
        .then(data => {
            const tbody = document.querySelector("#Historial tbody");
            const estado = document.getElementById("estado-historial");
            if (!tbody) return;

            tbody.innerHTML = "";

            if (data.length === 0) {
                if (estado) estado.textContent = "No hay movimientos registrados.";
                return;
            }

            data.forEach(movimiento => {
                const fila = document.createElement("tr");
                fila.innerHTML = `
                    <td>${movimiento.fecha_hora}</td>
                    <td>${movimiento.componente}</td>
                    <td>${movimiento.empleado}</td>
                    <td>${movimiento.cantidad}</td>
                    <td>#${movimiento.id_pedido}</td>
                    <td>${movimiento.recibido ? "Sí" : "No"}</td>
                `;
                tbody.appendChild(fila);
            });

            if (estado) estado.textContent = `${data.length} movimientos (últimos 100).`;
        })
        .catch(error => {
            console.error("Error al cargar el historial:", error);
            const estado = document.getElementById("estado-historial");
            if (estado) estado.textContent = "No se pudo cargar el historial.";
        });
}

// ===== Modal de resultado NFC =====

let ultimoIdNfc = null;

function agregarTexto(contenedor, texto) {
    const p = document.createElement("p");
    p.textContent = texto;
    contenedor.appendChild(p);
}

function mostrarModalNfc(evento) {
    const caja = document.getElementById("modal-nfc-caja");
    const titulo = document.getElementById("modal-nfc-titulo");
    const cuerpo = document.getElementById("modal-nfc-cuerpo");
    const modal = document.getElementById("modal-nfc");

    if (!caja || !titulo || !cuerpo || !modal) return;

    cuerpo.innerHTML = "";

    if (evento.tipo === "retiro_exitoso") {
        caja.className = "modal-caja exito";
        titulo.textContent = "¡Retiro realizado!";

        agregarTexto(cuerpo, `Empleado: ${evento.empleado}`);
        agregarTexto(cuerpo, `Pedidos retirados: ${evento.pedidos_retirados}`);
        agregarTexto(cuerpo, "Componentes retirados:");

        const lista = document.createElement("ul");
        evento.componentes.forEach(componente => {
            const elemento = document.createElement("li");
            elemento.textContent = `${componente.cantidad} × ${componente.nombre}`;
            lista.appendChild(elemento);
        });
        cuerpo.appendChild(lista);

    } else if (evento.tipo === "nfc_no_registrado") {
        caja.className = "modal-caja error";
        titulo.textContent = "NFC no registrado";
        agregarTexto(cuerpo, `El identificador ${evento.nfc_id} no existe en el sistema.`);

    } else if (evento.tipo === "sin_pedidos") {
        caja.className = "modal-caja aviso";
        titulo.textContent = "No hay pedidos asociados al retiro.";
        agregarTexto(cuerpo, "El empleado fue identificado, pero no tiene pedidos pendientes.");
        agregarTexto(cuerpo, `Empleado: ${evento.empleado}`);

    } else if (evento.tipo === "sin_existencias") {
        caja.className = "modal-caja error";
        titulo.textContent = "No hay existencias suficientes";

        agregarTexto(cuerpo, `Empleado: ${evento.empleado}`);
        agregarTexto(cuerpo, "El retiro no se realizó. Faltan:");

        const lista = document.createElement("ul");
        evento.faltantes.forEach(faltante => {
            const elemento = document.createElement("li");
            elemento.textContent = `${faltante.faltan} × ${faltante.nombre}`;
            lista.appendChild(elemento);
        });
        cuerpo.appendChild(lista);
    } else {
        caja.className = "modal-caja error";
        titulo.textContent = "No fue posible procesar el retiro";
        agregarTexto(cuerpo, "Ocurrió un error en el servidor. Intenta de nuevo o avisa al administrador.");
    }

    modal.classList.add("abierto");
}

function cerrarModalNfc() {
    const modal = document.getElementById("modal-nfc");
    if (modal) {
        modal.classList.remove("abierto");
    }
}

function consultarEventosNfc() {
    const parametro = ultimoIdNfc === null ? "" : `?desde=${ultimoIdNfc}`;

    fetch(`/api/nfc-eventos${parametro}`)
        .then(response => {
            if (!response.ok) {
                throw new Error("Error al consultar eventos NFC");
            }
            return response.json();
        })
        .then(data => {
            ultimoIdNfc = data.ultimo_id;

            if (data.eventos.length > 0) {
                mostrarModalNfc(data.eventos[data.eventos.length - 1]);
                cargarPeticiones();
                fillTable();
            }
        })
        .catch(error => {
            console.error("Error al consultar NFC:", error);
        });
}

document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
        cerrarModalNfc();
    }
});

/*===============================================
    Alta de componente desde index.html
    (antes solo agregaba una fila en el navegador
    sin guardar nada en la base de datos)
===============================================*/
document.addEventListener("DOMContentLoaded", () => {
    const formInventario = document.getElementById("for-Inventario");
    if (!formInventario) return;

    formInventario.addEventListener("submit", async (event) => {
        event.preventDefault();
        const errorMsg = document.getElementById("errorMsg");
        const okMsg = document.getElementById("okMsg");
        if (errorMsg) errorMsg.textContent = "";
        if (okMsg) okMsg.textContent = "";

        const payload = {
            nombre: document.getElementById("componente").value.trim(),
            categoria: document.getElementById("categoria").value.trim(),
            descripcion: document.getElementById("descripcion").value.trim(),
            cantidad: Number(document.getElementById("cantidad").value),
            ubicacion: document.getElementById("ubicacion").value.trim(),
            precio: document.getElementById("precio").value || null
        };

        if (!payload.nombre || !payload.ubicacion) {
            if (errorMsg) errorMsg.textContent = "Por favor, complete todos los campos.";
            return;
        }

        try {
            const respuesta = await fetch("/api/componentes", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await respuesta.json();
            if (!respuesta.ok) {
                if (errorMsg) errorMsg.textContent = data.error || "No se pudo agregar el componente.";
                return;
            }
            if (okMsg) okMsg.textContent = data.mensaje + " (ID " + data.id_componente + ")";
            formInventario.reset();
            fillTable();
        } catch (error) {
            if (errorMsg) errorMsg.textContent = "Error al conectar con el servidor.";
        }
    });
});

/*===============================================
    Script para surtir_comp.html
===============================================*/
document.addEventListener("DOMContentLoaded", () => {
    const datalist = document.getElementById("lista_componentes");
    const entrada = document.getElementById("id_comp");
    const entradaCantidad = document.getElementById("cantidad_comp");
    const entradaUbicacion = document.getElementById("ubicacion_comp");
    const listaAnadidos = document.getElementById("lista_añadidos");
    const botonAgregar = document.getElementById("btnAgregarComp");
    const botonConfirmar = document.getElementById("btnConfirmarPet");
    const mensaje = document.getElementById("mensaje_peticion");

    if (!entrada || !entradaCantidad || !listaAnadidos || !botonAgregar || !botonConfirmar || !mensaje) {
        return;
    }

    if (datalist) {
        fetch("/inventario_nombre")
            .then(response => response.json())
            .then(data => {
                data.forEach(item => {
                    const option = document.createElement("option");
                    option.value = item.nombre;
                    datalist.appendChild(option);
                });
            })
            .catch(error => console.error("Error al cargar el inventario:", error));
    }

    const componentes = [];

    function actualizarLista() {
        listaAnadidos.replaceChildren();
        componentes.forEach((componente, indice) => {
            const elemento = document.createElement("li");
            const ubicacion = componente.ubicacion ? ` (${componente.ubicacion})` : "";
            elemento.append(document.createTextNode(`${componente.nombre}${ubicacion} (cantidad: ${componente.cantidad}) `));

            const quitar = document.createElement("button");
            quitar.type = "button";
            quitar.textContent = "Quitar";
            quitar.setAttribute("aria-label", `Quitar ${componente.nombre}`);
            quitar.addEventListener("click", () => {
                componentes.splice(indice, 1);
                actualizarLista();
            });
            elemento.appendChild(quitar);
            listaAnadidos.appendChild(elemento);
        });
        botonConfirmar.disabled = componentes.length === 0;
    }

    botonAgregar.addEventListener("click", () => {
        const componente = entrada.value.trim();
        const cantidad = Number(entradaCantidad.value);
        const ubicacion = entradaUbicacion ? entradaUbicacion.value.trim().toUpperCase() : "";
        if (!componente || !Number.isInteger(cantidad) || cantidad < 1) {
            if (!componente) entrada.focus();
            else entradaCantidad.focus();
            return;
        }
        componentes.push({ nombre: componente, cantidad, ubicacion });
        entrada.value = "";
        entradaCantidad.value = "1";
        if (entradaUbicacion) entradaUbicacion.value = "";
        mensaje.textContent = "";
        actualizarLista();
        entrada.focus();
    });

    botonConfirmar.addEventListener("click", async () => {
        if (!componentes.length) return;

        botonConfirmar.disabled = true;
        mensaje.textContent = "Enviando petición...";

        try {
            const respuesta = await fetch("/surtir_componentes", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ componentes })
            });

            const data = await respuesta.json();

            if (!respuesta.ok) {
                throw new Error(data.error || "No se pudo confirmar la petición.");
            }

            componentes.length = 0;
            actualizarLista();
            mensaje.textContent = data.mensaje || "Petición confirmada y componentes añadidos.";
        } catch (error) {
            mensaje.textContent = error.message || "Error al confirmar la petición.";
            botonConfirmar.disabled = componentes.length === 0;
        }
    });
});
