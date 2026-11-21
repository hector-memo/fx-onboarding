/* FX Onboarding: comportamiento de la interfaz.
   - Formularios de alta y cambio de permisos: consulta del contrato en el padrón,
     modo "usuario nuevo en contrato existente" y comparación actual vs. solicitado.
   - Confirmaciones, selección múltiple y filas dinámicas.
   El servidor vuelve a validar todo; esto solo mejora la captura. */
(function () {
  "use strict";

  var PERMISOS = ["grupo_spot", "multiaprobacion", "multiabono", "divisas", "limite_operacion", "limite_diario"];
  var EMPRESA = ["nombre_cliente", "rfc", "region", "segmento", "zona"];
  var ETIQUETAS = {
    grupo_spot: "Grupo de parametrización spot",
    multiaprobacion: "Multiaprobación",
    multiabono: "Multiabono",
    divisas: "Divisas autorizadas",
    limite_operacion: "Límite por operación (USD)",
    limite_diario: "Límite diario (USD)"
  };

  function formatear(campo, valor) {
    if (valor === null || valor === undefined || valor === "") return "—";
    if (campo.indexOf("limite_") === 0) {
      var n = Number(String(valor).replace(/,/g, ""));
      return isNaN(n) ? String(valor) : n.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    if (campo === "divisas") return String(valor).split(",").filter(Boolean).join(", ");
    return String(valor);
  }

  function normal(campo, valor) {
    if (valor === null || valor === undefined) return "";
    if (campo.indexOf("limite_") === 0) {
      var n = parseFloat(String(valor).replace(/,/g, ""));
      return isNaN(n) ? String(valor).trim() : n.toFixed(2);
    }
    if (campo === "divisas") {
      return String(valor).split(",").map(function (s) { return s.trim().toUpperCase(); }).filter(Boolean).sort().join(",");
    }
    return String(valor).trim();
  }

  function iniciarFormulario(form) {
    var tipo = form.dataset.tipo;
    var api = form.dataset.api;
    var repost = form.dataset.repost === "1";
    var contrato = form.querySelector("#contrato");
    var aviso = document.getElementById("aviso-contrato");
    var enviar = form.querySelector('button[type="submit"]');
    var seccionesPadron = ["seccion-empresa", "seccion-permisos"]
      .map(function (id) { return document.getElementById(id); }).filter(Boolean);
    var seccionNuevos = document.getElementById("seccion-nuevos");
    var panel = document.getElementById("panel-vigente");
    var bloqueDiff = document.getElementById("bloque-diff");
    var primeraConsulta = true;
    var rellenado = false;
    var vigentes = null;
    var bloqueoContrato = false;
    var temporizador = null;

    if (!contrato) return;

    function mostrarAviso(texto, clase) {
      if (!aviso) return;
      aviso.textContent = texto || "";
      aviso.className = "alerta " + (clase || "info");
      aviso.hidden = !texto;
    }

    function bloquear(si) { if (enviar) enviar.disabled = !!si; }

    function getValor(nombre) {
      if (nombre === "divisas") {
        return Array.prototype.map.call(form.querySelectorAll('input[name="divisas"]:checked'), function (c) { return c.value; }).sort().join(",");
      }
      var el = form.querySelector('[name="' + nombre + '"]');
      return el ? el.value.trim() : "";
    }

    function setValor(nombre, valor) {
      if (nombre === "divisas") {
        var elegidas = String(valor || "").split(",").filter(Boolean);
        form.querySelectorAll('input[name="divisas"]').forEach(function (c) { c.checked = elegidas.indexOf(c.value) !== -1; });
        return;
      }
      var el = form.querySelector('[name="' + nombre + '"]');
      if (el) el.value = (valor === null || valor === undefined) ? "" : valor;
    }

    function limpiarRelleno() {
      if (!rellenado) return;
      EMPRESA.concat(PERMISOS).forEach(function (c) { setValor(c, ""); });
      rellenado = false;
    }

    // ---- Alta nueva
    function modoAlta(r) {
      if (r.estado === "propio") {
        EMPRESA.concat(PERMISOS).forEach(function (c) { setValor(c, r.cliente[c]); });
        seccionesPadron.forEach(function (s) { s.disabled = true; });
        rellenado = true;
        mostrarAviso(r.mensaje, "info");
        bloquear(false);
        return;
      }
      seccionesPadron.forEach(function (s) { s.disabled = false; });
      limpiarRelleno();
      mostrarAviso(r.mensaje, r.estado === "nuevo" ? "info" : "error");
      bloquear(r.estado !== "nuevo");
    }

    // ---- Cambio de permisos
    function actualizarDiff() {
      if (!bloqueDiff) return;
      if (!vigentes) { bloqueDiff.hidden = true; bloquear(true); return; }
      var cuerpo = bloqueDiff.querySelector("tbody");
      cuerpo.innerHTML = "";
      var cambios = 0;
      PERMISOS.forEach(function (c) {
        var actual = vigentes[c];
        var solicitado = getValor(c);
        if (normal(c, actual) === normal(c, solicitado)) return;
        cambios += 1;
        var tr = document.createElement("tr");
        tr.className = "cambio";
        [ETIQUETAS[c], formatear(c, actual), formatear(c, solicitado)].forEach(function (texto) {
          var td = document.createElement("td");
          td.textContent = texto;
          tr.appendChild(td);
        });
        cuerpo.appendChild(tr);
      });
      if (!cambios) {
        var tr = document.createElement("tr");
        var td = document.createElement("td");
        td.colSpan = 3;
        td.className = "muted";
        td.textContent = "Sin cambios: los permisos solicitados son iguales a los vigentes.";
        tr.appendChild(td);
        cuerpo.appendChild(tr);
      }
      bloqueDiff.hidden = false;
      bloquear(bloqueoContrato || cambios === 0);
    }

    function modoCambio(r) {
      if (r.cliente) {
        vigentes = r.cliente;
        panel.querySelectorAll("[data-campo]").forEach(function (el) {
          el.textContent = formatear(el.dataset.campo, r.cliente[el.dataset.campo]);
        });
        panel.hidden = false;
        seccionNuevos.disabled = false;
        if (!(repost && primeraConsulta)) PERMISOS.forEach(function (c) { setValor(c, r.cliente[c]); });
      } else {
        vigentes = null;
        panel.hidden = true;
        seccionNuevos.disabled = true;
      }
      bloqueoContrato = r.estado !== "propio";
      mostrarAviso(r.mensaje, bloqueoContrato ? "error" : "info");
      actualizarDiff();
    }

    function reiniciar() {
      mostrarAviso("", "info");
      if (tipo === "alta") {
        seccionesPadron.forEach(function (s) { s.disabled = false; });
        limpiarRelleno();
        bloquear(false);
      } else {
        vigentes = null;
        if (panel) panel.hidden = true;
        if (seccionNuevos) seccionNuevos.disabled = true;
        if (bloqueDiff) bloqueDiff.hidden = true;
        bloquear(true);
      }
    }

    function consultar() {
      var valor = contrato.value.replace(/\D/g, "");
      if (valor.length !== 11) { reiniciar(); return; }
      fetch(api + encodeURIComponent(valor) + "?para=" + tipo, {
        headers: { Accept: "application/json" },
        credentials: "same-origin"
      }).then(function (resp) {
        if (resp.status === 401) {
          mostrarAviso("Tu sesión expiró. Vuelve a iniciar sesión.", "error");
          bloquear(true);
          return null;
        }
        return resp.json();
      }).then(function (r) {
        if (!r) return;
        if (tipo === "alta") modoAlta(r); else modoCambio(r);
        primeraConsulta = false;
      }).catch(function () {
        mostrarAviso("No se pudo consultar el contrato. Intenta de nuevo.", "error");
      });
    }

    contrato.addEventListener("input", function () {
      var limpio = contrato.value.replace(/\D/g, "").slice(0, 11);
      if (limpio !== contrato.value) contrato.value = limpio;
      clearTimeout(temporizador);
      temporizador = setTimeout(consultar, 250);
    });

    if (tipo === "cambio") {
      ["input", "change"].forEach(function (evento) {
        form.addEventListener(evento, function (e) {
          if (e.target.name && PERMISOS.indexOf(e.target.name) !== -1) actualizarDiff();
        });
      });
    }

    if (contrato.value.replace(/\D/g, "").length === 11) consultar();
    else if (tipo === "cambio") reiniciar();
  }

  document.querySelectorAll("form[data-tipo]").forEach(iniciarFormulario);

  // Confirmación antes de enviar acciones delicadas.
  document.querySelectorAll("form[data-confirmar]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!window.confirm(f.dataset.confirmar)) e.preventDefault();
    });
  });

  // Seleccionar todas las solicitudes pendientes.
  document.querySelectorAll("[data-seleccionar-todo]").forEach(function (maestro) {
    maestro.addEventListener("change", function () {
      maestro.form.querySelectorAll('input[name="ids"]').forEach(function (c) { c.checked = maestro.checked; });
    });
  });

  // Captura manual: agregar filas de usuarios.
  document.querySelectorAll("[data-agregar-fila]").forEach(function (boton) {
    boton.addEventListener("click", function () {
      var tabla = document.getElementById(boton.dataset.agregarFila);
      var fila = tabla.querySelector("tbody tr");
      var nueva = fila.cloneNode(true);
      nueva.querySelectorAll("input").forEach(function (i) { i.value = ""; });
      nueva.querySelectorAll(".error-campo").forEach(function (e) { e.remove(); });
      tabla.querySelector("tbody").appendChild(nueva);
    });
  });
})();
