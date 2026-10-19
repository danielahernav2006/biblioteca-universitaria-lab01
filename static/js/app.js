/* Interacciones del frontend para las páginas nuevas (layout.html).
   Solo mejora la experiencia: todas las validaciones y permisos se comprueban en el servidor. */
(function () {
  "use strict";

  // Confirmación antes de acciones sensibles: <form data-confirmar="¿Seguro?">
  document.addEventListener("submit", function (e) {
    var form = e.target;
    var mensaje = form.getAttribute("data-confirmar");
    if (mensaje && !window.confirm(mensaje)) {
      e.preventDefault();
      return;
    }
    // Evita envíos dobles mientras el servidor responde
    if ((form.method || "").toLowerCase() === "post") {
      form.querySelectorAll("button").forEach(function (b) { b.disabled = true; });
    }
  });

  // La carrera es obligatoria para estudiantes y no aplica a bibliotecarios
  var rol = document.getElementById("rol");
  var carrera = document.getElementById("id_carrera");
  var ayudaCarrera = document.getElementById("ayuda-carrera");
  function actualizarCarrera() {
    if (!rol || !carrera || rol.tagName !== "SELECT") return;
    var valor = rol.value;
    carrera.required = valor === "ESTUDIANTE";
    carrera.disabled = valor === "BIBLIOTECARIO";
    if (ayudaCarrera) {
      ayudaCarrera.textContent = valor === "ESTUDIANTE" ? "Obligatoria para estudiantes."
        : valor === "BIBLIOTECARIO" ? "No aplica al personal de la biblioteca." : "Opcional.";
    }
  }
  if (rol) {
    rol.addEventListener("change", actualizarCarrera);
    actualizarCarrera();
  }

  // Aviso inmediato si la confirmación de contraseña no coincide
  var clave = document.getElementById("contrasena");
  var confirmacion = document.getElementById("confirmacion");
  function revisarClaves() {
    confirmacion.setCustomValidity(
      confirmacion.value && confirmacion.value !== clave.value ? "Las contraseñas no coinciden." : "");
  }
  if (clave && confirmacion) {
    clave.addEventListener("input", revisarClaves);
    confirmacion.addEventListener("input", revisarClaves);
  }
})();
