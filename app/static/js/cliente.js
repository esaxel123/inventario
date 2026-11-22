(() => {
  "use strict";

  // Endpoint POST que recibe las solicitudes en el backend Flask.
  const ENDPOINT_SOLICITUD = "/api/solicitudes";

  const $ = (selector) => document.querySelector(selector);
  const state = { inventario: [], seleccion: new Map(), empleado: null, revisando: false };

  async function verificarEmpleado() {
    try {
      const respuesta = await fetch("/api/me");
      if (!respuesta.ok) {
        window.location.href = "/login";
        return false;
      }
      const data = await respuesta.json();
      state.empleado = data.empleado;
      const saludo = document.querySelector('#user');
      if (saludo) saludo.textContent = state.empleado.nombre;
      return true;
    } catch (_) {
      window.location.href = "/login";
      return false;
    }
  }

  function textoSeguro(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[char]);
  }

  function notificar(message) {
    const toast = $("#mensaje");
    toast.textContent = message;
    toast.classList.add("visible");
    clearTimeout(notificar.timer);
    notificar.timer = setTimeout(() => toast.classList.remove("visible"), 3000);
  }

  function leerFilasTabla() {
    return [...document.querySelectorAll("#Inventario tbody tr")].map((row) => {
      const cells = [...row.cells].map((cell) => cell.textContent.trim());
      if (cells.length < 6) return null;
      return {
        id: cells[0], componente: cells[1], categoria: cells[2],
        disponible: Number(String(cells[3]).replace(/[^\d.-]/g, "")) || 0,
        ubicacion: cells[4], precio: cells[5]
      };
    }).filter(Boolean);
  }

  async function cargarInventario() {
    // Igual que index.html: se ejecuta fillTable() una sola vez.
    // No observamos el tbody porque esta misma vista lo vuelve a dibujar.
    try {
      if (typeof window.fillTable === "function") {
        const resultado = window.fillTable();
        // Si la función existente devuelve una promesa, esperamos su finalización.
        if (resultado && typeof resultado.then === "function") {
          await resultado;
        }
      } else {
        $("#estado-inventario").textContent =
          "No se encontró fillTable(). Comprueba que script.js esté cargado correctamente.";
        return;
      }

      // Compatibilidad con fillTable() que carga datos de forma asíncrona
      // pero no devuelve una promesa. Son reintentos limitados, no un observer.
      let filas = leerFilasTabla();
      for (let intento = 0; !filas.length && intento < 5; intento++) {
        await new Promise((resolve) => setTimeout(resolve, 300));
        filas = leerFilasTabla();
      }

      if (!filas.length) {
        $("#estado-inventario").textContent =
          "No hay componentes para mostrar. Verifica la carga del inventario en script.js.";
        return;
      }

      // Guardamos los datos una sola vez. A partir de aquí la tabla es solo presentación.
      // Las filas sin ID de inventario no tienen existencias (cantidad 0).
      state.inventario = filas.filter((fila) => fila.id !== "—");
      $("#estado-inventario").textContent = `${state.inventario.length} componentes disponibles`;
      renderInventario();
    } catch (error) {
      console.error("Error al cargar el inventario:", error);
      $("#estado-inventario").textContent =
        "Ocurrió un problema al cargar el inventario. Recarga la página o revisa la consola.";
    }
  }

  function renderInventario() {
    const query = $("#buscar-componente").value.trim().toLocaleLowerCase("es");
    const items = state.inventario.filter((item) =>
      [item.id, item.componente, item.categoria, item.ubicacion].join(" ").toLocaleLowerCase("es").includes(query)
    );

    $("#inventario-body").innerHTML = items.map((item) => {
      const qty = state.seleccion.get(item.id)?.cantidad || 0;
      const disabled = item.disponible <= qty;
      return `<tr>
        <td>${textoSeguro(item.id)}</td><td>${textoSeguro(item.componente)}</td>
        <td>${textoSeguro(item.categoria)}</td><td>${textoSeguro(item.disponible)}</td>
        <td>${textoSeguro(item.ubicacion)}</td><td>${textoSeguro(item.precio)}</td>
        <td><button class="btn-agregar" data-add="${textoSeguro(item.id)}" ${disabled ? "disabled" : ""}>${qty ? "Agregar otro" : "Agregar"}</button></td>
      </tr>`;
    }).join("");

    $("#inventario-movil").innerHTML = items.map((item) => {
      const qty = state.seleccion.get(item.id)?.cantidad || 0;
      const disabled = item.disponible <= qty;
      return `<article class="inventario-card">
        <h3>${textoSeguro(item.componente)}</h3>
        <p>${textoSeguro(item.categoria)}</p>
        <p><b>Disponible:</b> ${textoSeguro(item.disponible)} · <b>Ubicación:</b> ${textoSeguro(item.ubicacion)}</p>
        <div class="card-pie"><span>${textoSeguro(item.precio)}</span>
        <button class="btn-agregar" data-add="${textoSeguro(item.id)}" ${disabled ? "disabled" : ""}>${qty ? "Agregar otro" : "Agregar"}</button></div>
      </article>`;
    }).join("");

    if (!items.length) $("#inventario-movil").innerHTML = '<p class="estado">No hay coincidencias.</p>';
  }

  function agregar(id) {
    const item = state.inventario.find((entry) => entry.id === id);
    if (!item) return;
    const current = state.seleccion.get(id)?.cantidad || 0;
    if (current >= item.disponible) return notificar("No hay más existencias disponibles.");
    state.seleccion.set(id, { ...item, cantidad: current + 1 });
    renderInventario(); renderSolicitud();
  }

  function cambiarCantidad(id, delta) {
    const item = state.seleccion.get(id);
    if (!item) return;
    const next = item.cantidad + delta;
    if (next <= 0) state.seleccion.delete(id);
    else if (next <= item.disponible) item.cantidad = next;
    else return notificar("La cantidad supera las existencias disponibles.");
    renderInventario(); renderSolicitud();
  }

  function renderSolicitud() {
    const items = [...state.seleccion.values()];
    const total = items.reduce((sum, item) => sum + item.cantidad, 0);
    $("#contador-items").textContent = items.length;
    $("#resumen-seleccion").textContent = items.length
      ? `${total} unidades seleccionadas` : "Aún no has agregado componentes.";
    $("#barra-cantidad").textContent = `${total} ${total === 1 ? "unidad" : "unidades"} · ${items.length} componentes`;
    $("#enviar-solicitud").disabled = !items.length;
    if (!items.length) cerrarRevision();

    $("#lista-solicitud").innerHTML = items.length ? items.map((item) => `
      <article class="item-solicitud">
        <div><strong>${textoSeguro(item.componente)}</strong><small>ID: ${textoSeguro(item.id)} · Disponible: ${item.disponible}</small></div>
        <div class="controles-cantidad">
          <button class="btn-cantidad" data-minus="${textoSeguro(item.id)}" aria-label="Quitar una unidad">−</button>
          <span class="valor-cantidad">${item.cantidad}</span>
          <button class="btn-cantidad" data-plus="${textoSeguro(item.id)}" aria-label="Agregar una unidad" ${item.cantidad >= item.disponible ? "disabled" : ""}>+</button>
        </div>
        <button class="btn-quitar" data-remove="${textoSeguro(item.id)}">Quitar componente</button>
      </article>`).join("") : `
      <div class="solicitud-vacia"><span aria-hidden="true">＋</span>
      <strong>Tu lista está vacía</strong><p>Agrega componentes desde el inventario.</p></div>`;
  }

  function abrirRevision() {
    state.revisando = true;
    $("#solicitud-detalle").hidden = false;
    $("#toggle-solicitud").textContent = "Ocultar lista";
    $("#toggle-solicitud").setAttribute("aria-expanded", "true");
    $("#enviar-solicitud").textContent = "Confirmar y enviar";
    $("#titulo-solicitud").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function cerrarRevision() {
    state.revisando = false;
    $("#solicitud-detalle").hidden = true;
    $("#toggle-solicitud").textContent = "Ver lista";
    $("#toggle-solicitud").setAttribute("aria-expanded", "false");
    $("#enviar-solicitud").textContent = "Revisar solicitud";
  }

  async function enviarSolicitud() {
    const items = [...state.seleccion.values()];
    if (!items.length) return;
    const button = $("#enviar-solicitud");
    // El empleado ya no se manda en el cuerpo: el servidor lo toma de
    // la sesión iniciada (antes cualquiera podía suplantar a otro).
    const payload = {
      componentes: items.map(({ id, componente, cantidad }) => ({
        id_inventario: Number(id),
        componente,
        cantidad
    })),
      comentarios: $("#notas-solicitud").value.trim()
    };
    button.disabled = true;
    button.textContent = "Enviando…";
    try {
      const response = await fetch(ENDPOINT_SOLICITUD, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        const detail = await response.json();
        throw new Error(detail.error || `Error HTTP ${response.status}`);
    }
      notificar("¡Solicitud enviada correctamente!");
      state.seleccion.clear();
      $("#notas-solicitud").value = "";
      cerrarRevision();
      renderInventario(); renderSolicitud();
    } catch (error) {
      console.error("No se pudo enviar la solicitud:", error);
      notificar("No se pudo enviar. Revisa la ruta del servidor y vuelve a intentar.");
    } finally {
      button.textContent = state.revisando ? "Confirmar y enviar" : "Revisar solicitud";
      button.disabled = state.seleccion.size === 0;
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    if (!await verificarEmpleado()) return;
    $("#buscar-componente").addEventListener("input", renderInventario);
    $("#inventario-body").addEventListener("click", (event) => {
      const button = event.target.closest("[data-add]");
      if (button) agregar(button.dataset.add);
    });
    $("#inventario-movil").addEventListener("click", (event) => {
      const button = event.target.closest("[data-add]");
      if (button) agregar(button.dataset.add);
    });
    $("#lista-solicitud").addEventListener("click", (event) => {
      const target = event.target.closest("button");
      if (!target) return;
      if (target.dataset.minus) cambiarCantidad(target.dataset.minus, -1);
      if (target.dataset.plus) cambiarCantidad(target.dataset.plus, 1);
      if (target.dataset.remove) {
        state.seleccion.delete(target.dataset.remove);
        renderInventario(); renderSolicitud();
      }
    });
    $("#toggle-solicitud").addEventListener("click", () => {
      if (state.revisando) cerrarRevision();
      else abrirRevision();
    });
    $("#enviar-solicitud").addEventListener("click", () => {
      if (!state.seleccion.size) return;
      if (!state.revisando) abrirRevision();
      else enviarSolicitud();
    });
    renderSolicitud();
    cargarInventario();
  });
})();
